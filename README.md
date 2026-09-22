# 💰 Bot de Finanças Pessoais (Telegram + Google Sheets)

Um assistente financeiro pessoal inteligente desenvolvido em **Python** que roda no Telegram. Ele automatiza o registo de transações financeiras (despesas, receitas, gastos no cartão de crédito, débitos diretos e diário) e sincroniza tudo em tempo real com uma planilha no **Google Sheets**.

O projeto está configurado para operar localmente 24/7 em um mini-computador (como o **Raspberry Pi**), garantindo alta disponibilidade e autonomia.

---

## 📊 Planilha Modelo
Para que o bot funcione corretamente e consiga mapear as colunas e abas, você pode utilizar a nossa planilha modelo oficial:
👉 **[Aceder à Planilha Modelo no Google Sheets](https://docs.google.com/spreadsheets/d/1mvFJA00HsQ0f7dRsMsSZKQHi2BeONu35s6S8T149_lk/edit?usp=sharing)**
*(Recomenda-se fazer uma cópia desta planilha para a sua própria conta do Google Drive).*

---

## ⚙️ Passo 1: Como Criar as APIs Necessárias

Antes de colocar o código a rodar, precisa de configurar as credenciais de acesso às duas plataformas principais:

### 1. Telegram Bot API (Criar o Bot)
1. No Telegram, procure pelo utilizador oficial **@BotFather**.
2. Envie o comando `/newbot` para criar um novo bot.
3. Siga as instruções dadas pelo BotFather: escolha um nome para o bot e um nome de utilizador (que deve terminar com `_bot`).
4. No final, ele vai fornecer um **Token de Acesso** (ex: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`). Guarde este token, pois ele será inserido no código do bot.

### 2. Google Workspace API (Google Sheets)
Para permitir que o bot edite a sua planilha automaticamente:
1. Aceda ao [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um novo projeto.
3. Ative a **Google Sheets API** e a **Google Drive API** para esse projeto.
4. Vá em **Credenciais** > **Criar Credenciais** > **Conta de Serviço (Service Account)**.
5. Crie uma chave do tipo **JSON** para essa conta de serviço. Um ficheiro `.json` será descarregado para o seu computador (coloque-o na pasta do projeto e renomeie-o se necessário, ex: `credentials.json`).
6. **Importante:** Copie o e-mail da conta de serviço gerada (parecido com `seu-bot@projeto.iam.gserviceaccount.com`) e dê permissão de **Editor** na sua cópia da planilha do Google Sheets.

---

## 🛠️ Passo 2: Instalação e Dependências

Clone o repositório e instale os pacotes necessários no seu sistema (ex: Raspberry Pi ou Linux):

```bash
git clone [https://github.com/SEU-UTILIZADOR/bot_financas.git](https://github.com/SEU-UTILIZADOR/bot_financas.git)
cd bot_financas