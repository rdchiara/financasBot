import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, timezone
import difflib
import schedule
import time
import threading

import config

# =========================================================
# ⚙️ CONFIGURAÇÕES INICIAIS E SEGURANÇA
# =========================================================
TOKEN = config.TELEGRAM_TOKEN
bot = telebot.TeleBot(TOKEN)

# Apenas este ID pode usar o bot (puxando direto do config.py)
MEU_ID_AUTORIZADO = config.MEU_ID_AUTORIZADO

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('credenciais.json', scope)
client = gspread.authorize(creds)

SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1_aUXNG1Hayddu72Hklq4CEi6hn9SO6G7B39oySVzwRg/edit'

NOME_MES_BOTAO = {1:"Jan", 2:"Fev", 3:"Mar", 4:"Abr", 5:"Mai", 6:"Jun", 
                  7:"Jul", 8:"Ago", 9:"Set", 10:"Out", 11:"Nov", 12:"Dez"}
NOME_MES_ABA = {1:"jan", 2:"fev", 3:"mar", 4:"abr", 5:"mai", 6:"jun", 
                7:"jul", 8:"ago", 9:"set", 10:"out", 11:"nov", 12:"dez"}

# =========================================================
# ⚙️ CONFIGURAÇÃO DAS COLUNAS (FATURA DO CARTÃO)
# =========================================================
FATURA_COL_DATA = 1
FATURA_LETRAS = ('A', 'D') 

dados_temporarios = {}


# ---------------------------------------------------------------------------------
# FUNÇÕES DE APOIO E SEGURANÇA
# ---------------------------------------------------------------------------------
def checar_autorizacao(message_or_call):
    chat_id = message_or_call.chat.id if hasattr(message_or_call, 'chat') else message_or_call.message.chat.id
    if chat_id != MEU_ID_AUTORIZADO:
        if hasattr(message_or_call, 'id') and hasattr(message_or_call, 'data'):
            bot.answer_callback_query(message_or_call.id, "⛔ Acesso negado!", show_alert=True)
        else:
            bot.reply_to(message_or_call, "⛔ Acesso negado. Este bot é de uso pessoal e restrito.")
        return False
    return True


def formatar_brl(valor):
    sinal = "-" if valor < 0 else ""
    val_abs = abs(valor)
    return f"{sinal}{val_abs:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def obter_categorias_validas(planilha):
    for nome_aba in ['Sumário', 'Sumario']:
        try:
            aba_sumario = planilha.worksheet(nome_aba)
            valores = aba_sumario.get('A16:A46')
            return [str(v[0]).strip() for v in valores if v and str(v[0]).strip()]
        except gspread.exceptions.WorksheetNotFound:
            continue
    return []


def gerar_relatorio_fatura(nome_aba_alvo):
    planilha = client.open_by_url(SPREADSHEET_URL)
    
    aba_sumario = None
    for nome in ['Sumário', 'Sumario']:
        try:
            aba_sumario = planilha.worksheet(nome)
            break
        except gspread.exceptions.WorksheetNotFound:
            continue
            
    if not aba_sumario:
        return "❌ Erro: Aba Sumário não encontrada."
        
    dados_sumario = aba_sumario.get('A15:P47')
    if not dados_sumario:
        return "❌ O intervalo A15:P47 da aba Sumário está vazio."

    cabecalho_meses = dados_sumario[0]
    col_alvo_idx = None
    for idx, texto_celula in enumerate(cabecalho_meses):
        texto_limpo = str(texto_celula).lower().replace('.', '').replace('/', '').replace(' ', '')
        nome_alvo_limpo = nome_aba_alvo.lower().replace('.', '').replace(' ', '')
        if nome_alvo_limpo in texto_limpo:
            col_alvo_idx = idx
            break
            
    if col_alvo_idx is None:
        return f"❌ Não achei a coluna correspondente a `{nome_aba_alvo}` na linha 15 do Sumário."

    total_geral = 0.0
    valores_brutos = []
    
    # Linha 16 (Cartão crédito)
    if len(dados_sumario) > 1:
        linha_total = dados_sumario[1]
        if len(linha_total) > col_alvo_idx:
            val_total_str = str(linha_total[col_alvo_idx]).replace('R$', '').strip().replace('.', '').replace(',', '.')
            try:
                total_geral = float(val_total_str)
            except ValueError:
                total_geral = 0.0

    maior_tamanho_cat = 0
    for linha in dados_sumario[2:]:
        if len(linha) > 0 and str(linha[0]).strip():
            cat_nome = str(linha[0]).strip()
            if len(linha) > col_alvo_idx:
                val_str = str(linha[col_alvo_idx]).replace('R$', '').strip().replace('.', '').replace(',', '.')
                try:
                    val_float = float(val_str)
                    if val_float > 0:
                        if len(cat_nome) > maior_tamanho_cat:
                            maior_tamanho_cat = len(cat_nome)
                        valores_brutos.append((cat_nome, val_float))
                except ValueError:
                    continue
                    
    total_formatado = formatar_brl(total_geral)
    msg_resposta = f"📊 *Fatura {nome_aba_alvo.upper()} - Total = R$ {total_formatado}*\n\n"
    
    if valores_brutos:
        linhas_formatadas = []
        for cat, val in valores_brutos:
            val_fmt = formatar_brl(val)
            espacos = " " * (maior_tamanho_cat - len(cat))
            linhas_formatadas.append(f"• {cat}{espacos}  ➔  R$ {val_fmt}")
        msg_resposta += "\n".join(linhas_formatadas)
    else:
        msg_resposta += "_Nenhum gasto registrado em categorias para este período._"
        
    return msg_resposta


# ---------------------------------------------------------------------------------
# DISPARO DIÁRIO AUTOMÁTICO MATINAL
# ---------------------------------------------------------------------------------
def enviar_resumo_matinal():
    try:
        hoje = datetime.now(timezone.utc) - timedelta(hours=3)
        aba_atual = f"{NOME_MES_ABA[hoje.month]}{hoje.year}"
        
        texto_fatura = gerar_relatorio_fatura(aba_atual)
        mensagem = f"☀️ *Bom dia! Resumo matinal da fatura:*\n\n{texto_fatura}"
        
        bot.send_message(MEU_ID_AUTORIZADO, mensagem, parse_mode="Markdown")
    except Exception as e:
        print(f"Erro ao disparar resumo matinal: {e}")


def thread_agendador():
    schedule.every().day.at("08:00").do(enviar_resumo_matinal)
    while True:
        schedule.run_pending()
        time.sleep(30)


# ---------------------------------------------------------------------------------
# FLUXO DE GASTOS NO CARTÃO (COM CATEGORIA)
# ---------------------------------------------------------------------------------
def enviar_menu_fatura(message, chat_id):
    dados = dados_temporarios[chat_id]
    hoje = datetime.now(timezone.utc) - timedelta(hours=3)
    mes_atual = hoje.month
    ano_atual = hoje.year
    mes_prox = mes_atual + 1
    ano_prox = ano_atual
    if mes_prox > 12:
        mes_prox = 1
        ano_prox += 1

    aba_atual = f"{NOME_MES_ABA[mes_atual]}{ano_atual}"
    aba_prox = f"{NOME_MES_ABA[mes_prox]}{ano_prox}"

    markup = InlineKeyboardMarkup(row_width=1)
    btn_fat_atual = InlineKeyboardButton(f"💳 Fatura Atual ({NOME_MES_BOTAO[mes_atual]})", callback_data=f"pag_Fatura_{aba_atual}")
    btn_fat_prox = InlineKeyboardButton(f"💳 Próxima Fatura ({NOME_MES_BOTAO[mes_prox]})", callback_data=f"pag_Fatura_{aba_prox}")
    markup.add(btn_fat_atual, btn_fat_prox)
    
    val_fmt = formatar_brl(dados['valor'])
    texto = (f"Registrando R$ {val_fmt} em *{dados['estabelecimento']}*.\n"
             f"Categoria validada: *{dados['categoria']}*\n\n"
             f"*Em qual fatura do cartão devo lançar?*")
    
    try:
        if hasattr(message, 'message_id'):
            bot.edit_message_text(texto, chat_id, message.message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")
    except telebot.apihelper.ApiTelegramException:
        bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")


def validar_categoria_gasto(message, categoria_digitada):
    chat_id = message.chat.id
    planilha = client.open_by_url(SPREADSHEET_URL)
    categorias_validas = obter_categorias_validas(planilha)
    
    cat_lower = categoria_digitada.lower()
    cats_validas_lower = [c.lower() for c in categorias_validas]
    
    if cat_lower in cats_validas_lower:
        index = cats_validas_lower.index(cat_lower)
        dados_temporarios[chat_id]['categoria'] = categorias_validas[index]
        enviar_menu_fatura(message, chat_id)
    else:
        matches = difflib.get_close_matches(categoria_digitada, categorias_validas, n=3, cutoff=0.3)
        markup = InlineKeyboardMarkup(row_width=1)
        if matches:
            dados_temporarios[chat_id]['matches'] = matches
            for i, match in enumerate(matches):
                markup.add(InlineKeyboardButton(f"👉 {match}", callback_data=f"cat_{i}"))
        markup.add(InlineKeyboardButton("✏️ Digitar Novamente", callback_data="cat_retry"))
        texto = f"⚠️ A categoria *{categoria_digitada}* não foi encontrada.\n"
        texto += "Você quis dizer alguma destas?" if matches else "Não encontrei nenhuma palavra parecida."
        bot.send_message(chat_id, texto, reply_markup=markup, parse_mode="Markdown")


def receber_nova_categoria(message):
    if not checar_autorizacao(message): return
    chat_id = message.chat.id
    if chat_id not in dados_temporarios:
        bot.reply_to(message, "Sessão expirada. Envie o comando novamente.")
        return
    validar_categoria_gasto(message, message.text.strip())


# ---------------------------------------------------------------------------------
# HANDLERS DE COMANDOS DE AJUDA E STATUS
# ---------------------------------------------------------------------------------
@bot.message_handler(commands=['start', 'ping'])
def comando_start(message):
    if not checar_autorizacao(message): return
    bot.reply_to(message, "🤖 Bot online no Raspberry Pi!\n\nUse:\n*gasto [local] [valor] [categoria]* (Cartão)\n*debito [local] [valor]* (Conta/Débito)\n*receita [origem] [valor]* (Entrada na Conta)\n*/fatura* - Resumo das faturas\n*/help* - Comandos\n*/how* - Como usar", parse_mode="Markdown")


@bot.message_handler(commands=['help', 'ajuda'])
def comando_ajuda(message):
    if not checar_autorizacao(message): return
    texto_ajuda = (
        "🤖 *Painel de Ajuda - Bot de Finanças*\n\n"
        "• `/fatura` - Menu com 5 botões de faturas para consultar o detalhamento.\n"
        "• `/how` - Guia detalhado dos formatos de mensagens para lançar despesas e receitas.\n"
        "• `/ping` ou `/start` - Verifica se o bot está online no Raspberry Pi.\n\n"
        "⏰ *Rotina Matinal:* Todo dia às 08:00 você recebe automaticamente o resumo da fatura do mês atual.\n"
        "🔒 *Segurança:* Acesso restrito ao seu ID de usuário."
    )
    bot.reply_to(message, texto_ajuda, parse_mode="Markdown")


@bot.message_handler(commands=['how'])
def comando_how(message):
    if not checar_autorizacao(message): return
    texto_how = (
        "📖 *Guia de Como Imputar Dados*\n\n"
        "💳 *1. Gasto no Cartão de Crédito (com categoria):*\n"
        "`gasto [local] [valor] [categoria]`\n"
        "• _Exemplo:_ `gasto Mercado 150,50 Mercado`\n"
        "• O bot valida a categoria na aba *Sumário* e pergunta em qual fatura lançar (*Atual* ou *Próxima*).\n\n"
        "🏦 *2. Gasto no Débito (sem categoria):*\n"
        "`debito [local] [valor]`\n"
        "• _Exemplo:_ `debito Padaria 25,00`\n"
        "• Registrado direto na aba *Receitas* com valor **negativo**, abatendo na hora do saldo da sua conta.\n\n"
        "📥 *3. Receita / Entrada de Dinheiro (sem categoria):*\n"
        "`receita [origem] [valor]`\n"
        "• _Exemplo:_ `receita Salario 5000`\n"
        "• Registrado direto na aba *Receitas* com valor **positivo**, somando no saldo da sua conta."
    )
    bot.reply_to(message, texto_how, parse_mode="Markdown")


@bot.message_handler(commands=['fatura'])
def comando_fatura(message):
    if not checar_autorizacao(message): return
    try:
        chat_id = message.chat.id
        hoje = datetime.now(timezone.utc) - timedelta(hours=3)
        markup = InlineKeyboardMarkup(row_width=1)
        
        for i in range(-2, 3):
            mes_alvo = hoje.month + i
            ano_alvo = hoje.year
            while mes_alvo > 12:
                mes_alvo -= 12
                ano_alvo += 1
            while mes_alvo < 1:
                mes_alvo += 12
                ano_alvo -= 1
                
            nome_aba = f"{NOME_MES_ABA[mes_alvo]}{ano_alvo}"
            rotulo_botao = f"{NOME_MES_BOTAO[mes_alvo]} / {ano_alvo}"
            if i == 0:
                rotulo_botao += " 🟢 (Atual)"
            markup.add(InlineKeyboardButton(rotulo_botao, callback_data=f"fat_{nome_aba}"))
            
        bot.send_message(chat_id, "📊 *Selecione qual fatura/mês você deseja consultar:*", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Erro ao gerar menu de faturas: {e}")


# ---------------------------------------------------------------------------------
# REGISTRO DE GASTO NO CARTÃO
# ---------------------------------------------------------------------------------
@bot.message_handler(func=lambda message: message.text.lower().startswith('gasto'))
def iniciar_registro_gasto(message):
    if not checar_autorizacao(message): return
    try:
        partes = message.text.strip().split()
        if len(partes) < 4:
            bot.reply_to(message, "⚠️ Use: *gasto [estabelecimento] [valor] [categoria]*", parse_mode="Markdown")
            return

        categoria = partes[-1]
        valor_str = partes[-2]
        estabelecimento = " ".join(partes[1:-2]) 

        valor_limpo = valor_str.replace('R$', '').strip()
        if '.' in valor_limpo and ',' in valor_limpo:
            valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
        elif ',' in valor_limpo:
            valor_limpo = valor_limpo.replace(',', '.')
        valor_float = float(valor_limpo)

        chat_id = message.chat.id
        dados_temporarios[chat_id] = {
            'estabelecimento': estabelecimento,
            'valor': valor_float,
            'categoria': categoria,
            'tipo': 'gasto'
        }

        bot.send_message(chat_id, "⏳ Verificando categoria do gasto...")
        validar_categoria_gasto(message, categoria)
    except Exception as e:
        bot.reply_to(message, f"❌ *Erro:* {e}", parse_mode="Markdown")


# ---------------------------------------------------------------------------------
# REGISTRO DE GASTO NO DÉBITO (SEM CATEGORIA, VALOR NEGATIVO NA CONTA)
# ---------------------------------------------------------------------------------
@bot.message_handler(func=lambda message: message.text.lower().startswith(('debito', 'débito')))
def registrar_debito_direto(message):
    if not checar_autorizacao(message): return
    try:
        partes = message.text.strip().split()
        if len(partes) < 3:
            bot.reply_to(message, "⚠️ Use: *debito [local] [valor]*\n_Exemplo:_ `debito Padaria 25,00`", parse_mode="Markdown")
            return

        valor_str = partes[-1]
        local = " ".join(partes[1:-1]) 

        valor_limpo = valor_str.replace('R$', '').strip()
        if '.' in valor_limpo and ',' in valor_limpo:
            valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
        elif ',' in valor_limpo:
            valor_limpo = valor_limpo.replace(',', '.')
        valor_float = float(valor_limpo)

        hoje = datetime.now(timezone.utc) - timedelta(hours=3)
        data_formatada = hoje.strftime('%d/%m/%Y')
        
        planilha = client.open_by_url(SPREADSHEET_URL)
        try:
            aba = planilha.worksheet("Receitas")
        except gspread.exceptions.WorksheetNotFound:
            aba = planilha.add_worksheet(title="Receitas", rows="1000", cols="10")

        coluna_dados = aba.col_values(1)
        if len(coluna_dados) == 0 or coluna_dados[0].strip().lower() != 'date':
            linha_header = len(coluna_dados) + 1 if len(coluna_dados) > 0 else 1
            range_header = f"A{linha_header}:C{linha_header}"
            lista_cabecalho = aba.range(range_header)
            lista_cabecalho[0].value = 'date'
            lista_cabecalho[1].value = 'title'
            lista_cabecalho[2].value = 'amount'
            aba.update_cells(lista_cabecalho, value_input_option='USER_ENTERED')
            aba.format(range_header, {'textFormat': {'bold': True}})
            coluna_dados.append('date')

        proxima_linha = len(coluna_dados) + 1
        range_alvo = f"A{proxima_linha}:C{proxima_linha}"
        lista_celulas = aba.range(range_alvo)
        lista_celulas[0].value = data_formatada
        lista_celulas[1].value = local
        lista_celulas[2].value = -abs(valor_float)  # Gravado como negativo
        aba.update_cells(lista_celulas, value_input_option='USER_ENTERED')

        val_fmt = formatar_brl(-abs(valor_float))
        texto_sucesso = (f"✅ *Gasto no Débito Registrado!*\n\n"
                         f"🛒 *Local:* {local}\n"
                         f"💰 *Valor:* R$ {val_fmt}\n"
                         f"📁 *Aba:* Receitas (Descontado do Saldo)")
        
        bot.reply_to(message, texto_sucesso, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Erro ao registrar débito: {e}", parse_mode="Markdown")


# ---------------------------------------------------------------------------------
# REGISTRO DE RECEITAS (SEM CATEGORIA, VALOR POSITIVO NA CONTA)
# ---------------------------------------------------------------------------------
@bot.message_handler(func=lambda message: message.text.lower().startswith('receita'))
def iniciar_registro_receita(message):
    if not checar_autorizacao(message): return
    try:
        partes = message.text.strip().split()
        if len(partes) < 3:
            bot.reply_to(message, "⚠️ Use: *receita [origem] [valor]*\n_Exemplo:_ `receita Salario 5000`", parse_mode="Markdown")
            return

        valor_str = partes[-1]
        origem = " ".join(partes[1:-1]) 

        valor_limpo = valor_str.replace('R$', '').strip()
        if '.' in valor_limpo and ',' in valor_limpo:
            valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
        elif ',' in valor_limpo:
            valor_limpo = valor_limpo.replace(',', '.')
        valor_float = float(valor_limpo)

        hoje = datetime.now(timezone.utc) - timedelta(hours=3)
        data_formatada = hoje.strftime('%d/%m/%Y')
        
        planilha = client.open_by_url(SPREADSHEET_URL)
        try:
            aba = planilha.worksheet("Receitas")
        except gspread.exceptions.WorksheetNotFound:
            aba = planilha.add_worksheet(title="Receitas", rows="1000", cols="10")
        
        coluna_dados = aba.col_values(1)
        
        if len(coluna_dados) == 0 or coluna_dados[0].strip().lower() != 'date':
            linha_header = len(coluna_dados) + 1 if len(coluna_dados) > 0 else 1
            range_header = f"A{linha_header}:C{linha_header}"
            lista_cabecalho = aba.range(range_header)
            lista_cabecalho[0].value = 'date'
            lista_cabecalho[1].value = 'title'
            lista_cabecalho[2].value = 'amount'
            aba.update_cells(lista_cabecalho, value_input_option='USER_ENTERED')
            aba.format(range_header, {'textFormat': {'bold': True}})
            coluna_dados.append('date')
            
        proxima_linha = len(coluna_dados) + 1
        range_alvo = f"A{proxima_linha}:C{proxima_linha}"
        lista_celulas = aba.range(range_alvo)
        lista_celulas[0].value = data_formatada
        lista_celulas[1].value = origem
        lista_celulas[2].value = abs(valor_float)
        aba.update_cells(lista_celulas, value_input_option='USER_ENTERED')
        
        val_fmt = formatar_brl(abs(valor_float))
        texto_sucesso = (f"✅ *Receita Registrada!*\n\n"
                         f"📥 *Origem:* {origem}\n"
                         f"💰 *Valor:* R$ {val_fmt}\n"
                         f"📁 *Aba:* Receitas")
        
        bot.reply_to(message, texto_sucesso, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, f"❌ Erro ao salvar receita: {e}", parse_mode="Markdown")


# ---------------------------------------------------------------------------------
# CALLBACKS DOS BOTÕES
# ---------------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def processar_escolha_categoria_gasto(call):
    if not checar_autorizacao(call): return
    chat_id = call.message.chat.id
    if chat_id not in dados_temporarios:
        bot.answer_callback_query(call.id, "Sessão expirada.")
        return

    escolha = call.data.split('_')[1]
    if escolha == "retry":
        msg = bot.edit_message_text("✍️ Digite a categoria do gasto corretamente:", chat_id, call.message.message_id)
        bot.register_next_step_handler(msg, receber_nova_categoria)
    else:
        categoria_escolhida = dados_temporarios[chat_id]['matches'][int(escolha)]
        dados_temporarios[chat_id]['categoria'] = categoria_escolhida
        enviar_menu_fatura(call.message, chat_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('pag_'))
def processar_pagamento(call):
    if not checar_autorizacao(call): return
    chat_id = call.message.chat.id
    if chat_id not in dados_temporarios:
        bot.answer_callback_query(call.id, "Os dados expiraram.")
        return

    try:
        dados = dados_temporarios[chat_id]
        _, _, nome_aba = call.data.split('_')
        
        hoje = datetime.now(timezone.utc) - timedelta(hours=3)
        data_formatada = hoje.strftime('%d/%m/%Y')
        planilha = client.open_by_url(SPREADSHEET_URL)

        aba = planilha.worksheet(nome_aba)
        coluna_dados = aba.col_values(FATURA_COL_DATA)
        
        if len(coluna_dados) == 0 or coluna_dados[0].strip().lower() != 'date':
            linha_header = len(coluna_dados) + 1 if len(coluna_dados) > 0 else 1
            range_header = f"{FATURA_LETRAS[0]}{linha_header}:{FATURA_LETRAS[1]}{linha_header}"
            lista_cabecalho = aba.range(range_header)
            lista_cabecalho[0].value = 'date'
            lista_cabecalho[1].value = 'title'
            lista_cabecalho[2].value = 'amount'
            lista_cabecalho[3].value = 'Categoria'
            aba.update_cells(lista_cabecalho, value_input_option='USER_ENTERED')
            aba.format(range_header, {'textFormat': {'bold': True}})
            coluna_dados.append('date')
        
        proxima_linha = len(coluna_dados) + 1
        range_alvo = f"{FATURA_LETRAS[0]}{proxima_linha}:{FATURA_LETRAS[1]}{proxima_linha}"
        lista_celulas = aba.range(range_alvo)
        lista_celulas[0].value = data_formatada
        lista_celulas[1].value = dados['estabelecimento']
        lista_celulas[2].value = dados['valor']
        lista_celulas[3].value = dados['categoria']
        aba.update_cells(lista_celulas, value_input_option='USER_ENTERED')
        
        val_fmt = formatar_brl(dados['valor'])
        texto_sucesso = (f"✅ *Gasto no Cartão Registrado!*\n\n"
                         f"🛒 *Local:* {dados['estabelecimento']}\n"
                         f"💰 *Valor:* R$ {val_fmt}\n"
                         f"🏷 *Cat:* {dados['categoria']}\n"
                         f"📅 *Aba:* {nome_aba}\n"
                         f"📍 *Bloco:* Fatura de Cartão")
                         
        try:
            bot.edit_message_text(texto_sucesso, chat_id, call.message.message_id, parse_mode="Markdown")
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(chat_id, texto_sucesso, parse_mode="Markdown")
            
        del dados_temporarios[chat_id]

    except gspread.exceptions.WorksheetNotFound:
        erro_msg = f"❌ Erro: A aba `{nome_aba}` não existe na planilha! Crie ou duplique a aba base primeiro."
        try:
            bot.edit_message_text(erro_msg, chat_id, call.message.message_id, parse_mode="Markdown")
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(chat_id, erro_msg, parse_mode="Markdown")
    except Exception as e:
        erro_msg = f"❌ Erro: {e}"
        try:
            bot.edit_message_text(erro_msg, chat_id, call.message.message_id, parse_mode="Markdown")
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(chat_id, erro_msg, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith('fat_'))
def processar_resumo_fatura(call):
    if not checar_autorizacao(call): return
    chat_id = call.message.chat.id
    nome_aba_alvo = call.data.split('_')[1]
    
    bot.answer_callback_query(call.id, "Buscando dados no Sumário...")
    try:
        msg_resposta = gerar_relatorio_fatura(nome_aba_alvo)
        try:
            bot.edit_message_text(msg_resposta, chat_id, call.message.message_id, parse_mode="Markdown")
        except telebot.apihelper.ApiTelegramException:
            bot.send_message(chat_id, msg_resposta, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Erro crítico ao processar fatura: {e}")


# ---------------------------------------------------------------------------------
# INICIALIZAÇÃO
# ---------------------------------------------------------------------------------
if __name__ == "__main__":
    print("Iniciando rotina de agendamento matinal...")
    thread = threading.Thread(target=thread_agendador, daemon=True)
    thread.start()

    print("Bot rodando no Raspberry Pi (Gasto Cartão, Débito Direto, Receitas, Faturas e Diário)...")
    bot.infinity_polling()