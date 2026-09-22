# 💰 Bot de Finanças Pessoais para o Telegram

Um bot para o Telegram desenvolvido em **Python** que automatiza o registo de despesas, receitas, gastos de cartão e controlo de faturas, integrando-se diretamente com o **Google Sheets** para gerir as suas finanças pessoais de forma prática e rápida diretamente pelo telemóvel.

Atualmente, este projeto encontra-se a correr num ambiente local (**Raspberry Pi**) 24/7 para garantir alta disponibilidade e autonomia.

---

## 🚀 Funcionalidades

* **Registo de Gastos e Receitas:** Registe transações rapidamente através de comandos no chat do Telegram.
* **Integração com Google Sheets:** Todos os dados enviados são automaticamente sincronizados e organizados na sua planilha de controlo financeiro (`gspread`).
* **Rotinas Automatizadas:** Contém agendamentos automáticos (`schedule`) para tarefas e resumos periódicos.
* **Execução Local 24/7:** Configurado para rodar de forma contínua em servidores locais ou mini-computadores como o Raspberry Pi, com arranque automático no sistema (`cron`).

---

## 🛠️ Tecnologias Utilizadas

* **Python 3**
* **pyTelegramBotAPI** (API oficial do Telegram para Python)
* **gspread** & **oauth2client** (Para integração e autenticação com o Google Sheets)
* **schedule** (Para gestão de tarefas agendadas)

---

## ⚙️ Configuração e Instalação Local

Se quiser clonar e colocar este projeto a rodar no seu próprio servidor ou Raspberry Pi, siga os passos abaixo:

### 1. Clonar o repositório
```bash
git clone [https://github.com/SEU-UTILIZADOR/bot_financas.git](https://github.com/SEU-UTILIZADOR/bot_financas.git)
cd bot_financas
