# ⚡ Cremica Automation - Premium Telegram Bot & Render Deploy

A powerful, asynchronous Telegram Bot engine for automating the **Cremica School Shuru Campaign**, featuring parallel processing, Firebase OTP auto-polling, dynamic batch code switching, CSV log exports, interactive inline keyboards, and built-in Render 24/7 web keep-alive server.

---

## 🌟 Key Features

- **🚀 Interactive Telegram UI**: Powered by `python-telegram-bot` v20+ with inline button dashboards, live progress bars, and rich HTML styling.
- **🌐 Firebase Panel Integration**: Send panel links in chat text or upload `.txt` files containing panel URLs.
- **📱 Single Number Mode**: Process individual mobile numbers with interactive step-by-step OTP entry inside Telegram.
- **🏷️ Dynamic Batch Code**: Update batch code instantly via `/setbatch` command or inline button.
- **📊 Real-time Log Export**: Instant download of execution results (`cremica_results.csv`) via `/logs`.
- **🛡️ Admin Security**: Restrict access to designated Telegram user IDs via `ADMIN_IDS` env variable.
- **⚡ 24/7 Render Keep-Alive**: Embedded `aiohttp` web server running on `$PORT` with `/health` endpoint to prevent Render free-tier sleep mode.

---

## 📂 Project Architecture

```
loot/
├── bot.py             # Main Telegram Bot & Render Web Server entrypoint
├── fcremica_core.py   # Cremica API encryption, Firebase link parser & execution engine
├── fcremica.py        # Original CLI script (standalone backup)
├── requirements.txt   # Dependencies (python-telegram-bot, requests, aiohttp, python-dotenv)
├── render.yaml        # Render Blueprint deployment configuration
├── Procfile           # Render process runner definition
├── .env.example       # Template for environment variables
├── .gitignore         # Git ignore file for secrets and logs
└── README.md          # Documentation & deployment guide
```

---

## ⚙️ Environment Variables

Before running locally or deploying, set up the following environment variables:

| Variable | Required | Description | Example |
| --- | --- | --- | --- |
| `BOT_TOKEN` | **Yes** | Telegram Bot Token from [@BotFather](https://t.me/BotFather) | `7123456789:AA...` |
| `ADMIN_IDS` | Optional | Comma-separated Telegram User IDs allowed to use the bot | `123456789,987654321` |
| `DEFAULT_BATCH_CODE` | Optional | Default Cremica campaign code (Default: `CD06G26`) | `CD06G26` |
| `PORT` | Optional | HTTP port for Render health ping server (Default: `8080`) | `8080` |

---

## 🖥️ Local Setup & Testing

1. **Clone or navigate to project directory**:
   ```bash
   cd "C:\Users\Himanshu Kumar\OneDrive\Desktop\loot"
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file from `.env.example` and set your `BOT_TOKEN`:
   ```bash
   BOT_TOKEN="your_bot_token_here"
   ADMIN_IDS="123456789"
   ```

4. **Run the Bot**:
   ```bash
   python bot.py
   ```

---

## 🚀 How to Deploy on GitHub & Render

### Step 1: Push to GitHub

Open terminal / command prompt in the project folder (`C:\Users\Himanshu Kumar\OneDrive\Desktop\loot`) and run:

```bash
git init
git add .
git commit -m "Initial commit - Cremica Premium Telegram Bot"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/cremica-telegram-bot.git
git push -u origin main
```

### Step 2: Deploy on Render

1. Log in to [Render.com](https://render.com/).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository (`cremica-telegram-bot`).
4. Set the following settings:
   - **Name**: `cremica-telegram-bot`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
5. Under **Environment Variables**, add:
   - `BOT_TOKEN`: `<your_telegram_bot_token>`
   - `ADMIN_IDS`: `<your_telegram_user_id>` (optional)
   - `DEFAULT_BATCH_CODE`: `CD06G26`
6. Click **Create Web Service**.

> 💡 Render will automatically detect the `/health` endpoint and keep your Telegram Bot online 24/7 without sleeping!

---

## 🤖 Telegram Bot Commands Quick Reference

- `/start` or `/menu` - Open interactive menu dashboard
- `/setbatch <CODE>` - View or update campaign batch code
- `/logs` - Export result logs as CSV document
- `/status` - Display live system diagnostic & health status
- `/help` - View usage guide & Firebase link instructions
