# 🚀 Antigravity IDE + Telegram Agent Bridge

An autonomous AI coding agent bridge connecting **Telegram** directly with **Google Gemini (Antigravity Engine)**. Send coding instructions, manage projects, write files, and approve command executions directly from your Telegram chat — running on **Windows** or **Kali Linux**.

---

## ✨ Features

- 📁 **Dynamic Folder Selection**: `/start` or `/folder` prompts you to choose which folder/workspace to work in (or use `/use_default`).
- 🤖 **Autonomous Coding Agent**: Instruct the bot to create apps, debug code, write REST APIs, and list files.
- 🔒 **Interactive Permission Approval (Inline Buttons)**: When the agent needs to run shell commands or touch sensitive resources, it sends Telegram inline buttons (`[ ✅ Approve ]` / `[ ❌ Reject ]`).
- 🔄 **Cross-Platform**: Runs natively on both Windows and Kali Linux / Ubuntu.
- ⚡ **Powered by Google GenAI**: Uses high-speed Gemini models (`gemini-2.5-flash` / `gemini-1.5-pro`).

---

## 📋 Commands

| Command | Description |
| :--- | :--- |
| `/start` | Welcome message & ask for workspace folder path |
| `/folder <path>` | Switch workspace folder to a custom path |
| `/use_default` | Switch to default workspace (`~/antigravity_workspace`) |
| `/status` | View agent health, active model, workspace, and platform |
| `/clear` | Clear recent conversation context |
| `/help` | Display list of available commands and examples |

---

## 🛠️ Quick Setup Guide

### 1. Requirements
Ensure Python 3.10+ is installed on your system.

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env     # On Kali / Linux
copy .env.example .env   # On Windows
```

Edit `.env` and fill in:
1. **`TELEGRAM_BOT_TOKEN`**: Obtain from [@BotFather](https://t.me/BotFather) on Telegram (`/newbot`).
2. **`GEMINI_API_KEY`**: Free API key from [Google AI Studio](https://aistudio.google.com/).

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
GEMINI_API_KEY=AIzaSy...your_gemini_api_key...
ANTIGRAVITY_MODEL=gemini-2.5-flash
```

---

## 🏃 Running the Bot

### On Windows:
```powershell
python antigravity_telegram_bot.py
```

### On Kali Linux:
```bash
chmod +x antigravity_telegram_bot.py
python3 antigravity_telegram_bot.py
```

---

## 💬 Example Usage on Telegram

1. Open your bot on Telegram and send `/start`.
2. Reply with your desired project directory (e.g. `C:\Users\risha\projects\my_app` or `/home/cyberrishu/projects/my_app`).
3. Send tasks such as:
   - *"Create a FastAPI application with authentication in auth.py"*
   - *"List all files in current folder"*
   - *"Install requirements using pip"* (Bot will send Approve/Reject buttons before executing!)

---

## 📦 GitHub Sync / Update

To push this repository to your GitHub account:

```bash
# 1. Initialize git
git init
git add .
git commit -m "feat: Initial commit for Antigravity Telegram Agent Bridge"

# 2. Link your GitHub repository
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO_NAME>.git
git branch -M main

# 3. Push to GitHub
git push -u origin main
```

---

## 🛡️ Security Note
- The bot restricts file read/writes inside the chosen workspace directory to prevent directory traversal.
- Destructive commands will **always** prompt for Telegram button confirmation before execution.
