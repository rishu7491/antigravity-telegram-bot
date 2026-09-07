#!/usr/bin/env python3
"""
Antigravity IDE + Telegram Agent Bridge
========================================
Connects Telegram messaging with a Google Gemini-powered Autonomous Coding Agent.

Features:
- Workspace folder selection on /start or /folder command
- Autonomous tool execution: file read, file write, directory listing
- Interactive Telegram Permission Approval (Inline Buttons) for running commands or critical file actions
- Multi-user conversation memory and workspace context
- Compatible with Windows and Kali Linux / Linux
"""

import os
import sys
import logging
import asyncio
import subprocess
import uuid
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("AntigravityTelegramBridge")

# Environment Configurations
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
DEFAULT_MODEL = os.getenv("ANTIGRAVITY_MODEL", "gemini-2.5-flash").strip()
DEFAULT_WORKSPACE_ENV = os.getenv("DEFAULT_WORKSPACE", "").strip()

# Gemini SDK Setup
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-genai library not found. Install with: pip install google-genai")

# Pending Permission Requests Store: request_id -> dict
pending_permissions: Dict[str, Dict[str, Any]] = {}

# User State Store: user_id -> dict(workspace, awaiting_folder, conversation_history)
user_sessions: Dict[int, Dict[str, Any]] = {}


def get_default_workspace() -> str:
    """Resolve a cross-platform default workspace path."""
    if DEFAULT_WORKSPACE_ENV and os.path.exists(DEFAULT_WORKSPACE_ENV):
        return os.path.abspath(DEFAULT_WORKSPACE_ENV)
    
    home = os.path.expanduser("~")
    workspace = os.path.join(home, "antigravity_workspace")
    os.makedirs(workspace, exist_ok=True)
    return os.path.abspath(workspace)


def get_user_session(user_id: int) -> Dict[str, Any]:
    """Get or initialize session configuration for a Telegram user."""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "workspace": get_default_workspace(),
            "awaiting_folder": False,
            "chat_history": [],
        }
    return user_sessions[user_id]


def resolve_safe_path(workspace: str, target_path: str) -> Optional[str]:
    """Ensure target path remains inside designated workspace to prevent path traversal."""
    abs_workspace = os.path.abspath(workspace)
    if os.path.isabs(target_path):
        target = os.path.abspath(target_path)
    else:
        target = os.path.abspath(os.path.join(abs_workspace, target_path))
    
    if os.path.commonpath([abs_workspace, target]) == abs_workspace:
        return target
    return None


async def send_split_message(update: Update, text: str, reply_markup=None):
    """Safely send messages within Telegram's 4096 character limit."""
    max_len = 4000
    if len(text) <= max_len:
        try:
            return await update.effective_message.reply_text(
                text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
            )
        except Exception:
            return await update.effective_message.reply_text(text, reply_markup=reply_markup)

    # Split message into chunks
    parts = [text[i:i + max_len] for i in range(0, len(text), max_len)]
    for idx, part in enumerate(parts):
        markup = reply_markup if idx == len(parts) - 1 else None
        try:
            await update.effective_message.reply_text(part, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        except Exception:
            await update.effective_message.reply_text(part, reply_markup=markup)


# ==========================================
# COMMAND HANDLERS
# ==========================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Welcomes user and asks for workspace directory."""
    user = update.effective_user
    session = get_user_session(user.id)
    session["awaiting_folder"] = True

    welcome_text = (
        f"👋 *Namaste {user.first_name}! Welcome to Antigravity IDE Agent Bridge.*\n\n"
        f"Main Antigravity AI Agent hoon jo Telegram ke instructions par aapke computer me "
        f"coding, file operations, debugging aur automation tasks perform kar sakta hoon.\n\n"
        f"📁 *Kripya batayein aapko kis folder (workspace) me kaam karna hai?*\n\n"
        f"📌 *Examples:*\n"
        f"• Windows: `C:\\Users\\risha\\projects`\n"
        f"• Kali Linux: `/home/cyberrishu/projects`\n"
        f"• Default: Type `/use_default` (`{session['workspace']}`)"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_use_default(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Use the default workspace path."""
    user = update.effective_user
    session = get_user_session(user.id)
    session["awaiting_folder"] = False
    session["workspace"] = get_default_workspace()

    msg = (
        f"✅ *Default Workspace Set!*\n\n"
        f"📂 Path: `{session['workspace']}`\n\n"
        f"Ab aap mujhe koi bhi coding task bhej sakte hain. "
        f"Jaise:\n"
        f"• *'Create a Python Flask REST API with JWT auth'*\n"
        f"• *'Show files in current workspace'*\n"
        f"• *'Write a calculator app in index.html'*"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_folder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change workspace folder explicitly."""
    user = update.effective_user
    session = get_user_session(user.id)

    if not context.args:
        session["awaiting_folder"] = True
        await update.message.reply_text(
            f"📂 Current workspace: `{session['workspace']}`\n\n"
            f"Naya folder path reply me bhejiye ya `/use_default` dabaiye.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    new_path = " ".join(context.args).strip()
    clean_path = os.path.abspath(os.path.expanduser(new_path))

    if not os.path.exists(clean_path):
        try:
            os.makedirs(clean_path, exist_ok=True)
            session["workspace"] = clean_path
            session["awaiting_folder"] = False
            await update.message.reply_text(
                f"✅ Naya folder create kiya aur workspace set kiya gaya:\n`{clean_path}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ Path exist nahi karta aur create nahi ho paya: `{e}`\nKripya valid path dein.",
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        session["workspace"] = clean_path
        session["awaiting_folder"] = False
        await update.message.reply_text(
            f"✅ Workspace successfully updated to:\n`{clean_path}`",
            parse_mode=ParseMode.MARKDOWN
        )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display status of Agent, Model, Workspace and API Keys."""
    user = update.effective_user
    session = get_user_session(user.id)

    gemini_status = "✅ Connected (google-genai)" if GEMINI_AVAILABLE and GEMINI_API_KEY else "❌ Missing API Key / SDK"
    status_msg = (
        f"🤖 *Antigravity IDE Agent Bridge Status*\n\n"
        f"• *User:* {user.first_name} (`{user.id}`)\n"
        f"• *AI Engine:* {gemini_status}\n"
        f"• *Active Model:* `{DEFAULT_MODEL}`\n"
        f"• *Active Workspace:* `{session['workspace']}`\n"
        f"• *Workspace Exists:* {'✅ Yes' if os.path.exists(session['workspace']) else '❌ No'}\n"
        f"• *Pending Permissions:* `{len(pending_permissions)}`\n"
        f"• *Platform:* `{sys.platform}`"
    )
    await update.message.reply_text(status_msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help documentation."""
    help_text = (
        f"🛠 *Antigravity IDE Agent Commands:*\n\n"
        f"• `/start` - Start the bot & set workspace folder\n"
        f"• `/folder <path>` - Change active workspace folder\n"
        f"• `/use_default` - Use standard default workspace\n"
        f"• `/status` - Check AI engine, workspace & bot status\n"
        f"• `/clear` - Clear conversation history\n"
        f"• `/help` - Show this guide\n\n"
        f"🔒 *Security & Permissions:*\n"
        f"Jab bhi agent koi terminal command run karna chahega, wo pehle Telegram par "
        f"Aapse *Approve / Reject* button se permission maangega."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear agent conversation history."""
    user = update.effective_user
    session = get_user_session(user.id)
    session["chat_history"] = []
    await update.message.reply_text("🧹 Conversation history cleared!", parse_mode=ParseMode.MARKDOWN)


# ==========================================
# AGENT TOOL EXECUTIONS
# ==========================================

def execute_read_file(workspace: str, file_path: str) -> str:
    safe_path = resolve_safe_path(workspace, file_path)
    if not safe_path:
        return f"Error: Path '{file_path}' is outside active workspace."
    if not os.path.isfile(safe_path):
        return f"Error: File '{file_path}' does not exist."
    try:
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return f"--- {file_path} (lines: {len(content.splitlines())}) ---\n{content}"
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"


def execute_write_file(workspace: str, file_path: str, content: str) -> str:
    safe_path = resolve_safe_path(workspace, file_path)
    if not safe_path:
        return f"Error: Path '{file_path}' is outside active workspace."
    try:
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Success: File '{file_path}' written successfully ({len(content)} characters)."
    except Exception as e:
        return f"Error writing file '{file_path}': {str(e)}"


def execute_list_files(workspace: str, subpath: str = "") -> str:
    target_dir = resolve_safe_path(workspace, subpath if subpath else ".")
    if not target_dir or not os.path.exists(target_dir):
        return f"Error: Directory '{subpath}' does not exist."
    try:
        entries = []
        for root, dirs, files in os.walk(target_dir):
            rel_root = os.path.relpath(root, workspace)
            prefix = "" if rel_root == "." else f"{rel_root}/"
            for d in dirs:
                if not d.startswith("."):
                    entries.append(f"📁 {prefix}{d}/")
            for f in files:
                if not f.startswith("."):
                    entries.append(f"📄 {prefix}{f}")
            # Limit depth for performance
            if rel_root.count(os.sep) >= 2:
                dirs.clear()
        return "\n".join(entries[:60]) if entries else "(Directory is empty)"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


# ==========================================
# AGENT LOOP & PERMISSION HANDLING
# ==========================================

async def request_permission(
    update: Update,
    user_id: int,
    action_type: str,
    action_payload: str,
    workspace: str
) -> str:
    """Send interactive permission request with Inline Buttons to Telegram."""
    request_id = str(uuid.uuid4())[:8]
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    pending_permissions[request_id] = {
        "future": future,
        "user_id": user_id,
        "action_type": action_type,
        "payload": action_payload,
        "workspace": workspace,
    }

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"perm_allow_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"perm_deny_{request_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    perm_text = (
        f"⚠️ *Permission Request Required*\n\n"
        f"• *Action:* `{action_type}`\n"
        f"• *Workspace:* `{workspace}`\n"
        f"• *Command/Target:*\n```bash\n{action_payload}\n```\n"
        f"Do you allow the agent to execute this?"
    )
    await update.effective_message.reply_text(
        perm_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
    )

    # Await user tap on button (timeout 120 seconds)
    try:
        result = await asyncio.wait_for(future, timeout=120.0)
        return result
    except asyncio.TimeoutError:
        pending_permissions.pop(request_id, None)
        return "Permission request timed out. Action cancelled."


async def callback_permission_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Approve/Reject button clicks from user."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split("_", 2)
    if len(parts) < 3:
        return

    action = parts[1]  # allow or deny
    req_id = parts[2]

    item = pending_permissions.pop(req_id, None)
    if not item:
        await query.edit_message_text("⚠️ This permission request has already expired or been handled.")
        return

    future = item["future"]

    if action == "allow":
        await query.edit_message_text(
            f"✅ *Approved:*\nExecuting `{item['payload']}`...", parse_mode=ParseMode.MARKDOWN
        )
        if item["action_type"] == "run_command":
            # Execute command safely in workspace
            try:
                proc = await asyncio.create_subprocess_shell(
                    item["payload"],
                    cwd=item["workspace"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                out_str = stdout.decode(errors="replace")
                err_str = stderr.decode(errors="replace")
                exit_code = proc.returncode
                res = f"[Exit Code: {exit_code}]\nSTDOUT:\n{out_str}\nSTDERR:\n{err_str}"
                future.set_result(res)
            except Exception as exc:
                future.set_result(f"Command execution error: {str(exc)}")
        else:
            future.set_result("Approved")
    else:
        await query.edit_message_text(
            f"❌ *Rejected:* Command execution was denied by user.", parse_mode=ParseMode.MARKDOWN
        )
        future.set_result("Action denied by user.")


# ==========================================
# MAIN MESSAGE PROCESSING
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming user messages and runs the agent loop."""
    user = update.effective_user
    text = update.message.text.strip()
    session = get_user_session(user.id)

    # 1. Handle folder setting prompt if awaiting folder
    if session.get("awaiting_folder"):
        clean_path = os.path.abspath(os.path.expanduser(text))
        if os.path.exists(clean_path):
            session["workspace"] = clean_path
            session["awaiting_folder"] = False
            await update.message.reply_text(
                f"✅ *Workspace Set:*\n`{clean_path}`\n\nAb aap task de sakte hain!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        else:
            # Offer to create or re-enter
            try:
                os.makedirs(clean_path, exist_ok=True)
                session["workspace"] = clean_path
                session["awaiting_folder"] = False
                await update.message.reply_text(
                    f"📁 Folder banaya aur set kiya gaya:\n`{clean_path}`\n\nAb aap task de sakte hain!",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            except Exception as err:
                await update.message.reply_text(
                    f"❌ Path exist nahi karta: `{clean_path}`\nError: {err}\n"
                    f"Kripya sahi path dein ya `/use_default` dabayein.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

    # Check API availability
    if not GEMINI_AVAILABLE:
        await update.message.reply_text(
            "❌ `google-genai` package install nahi hai. Run: `pip install google-genai`"
        )
        return

    if not GEMINI_API_KEY:
        await update.message.reply_text(
            "❌ `GEMINI_API_KEY` set nahi hai!\n"
            "Kripya `.env` file me `GEMINI_API_KEY=your_key` dalein ya environment variable set karein."
        )
        return

    # 2. Agent Processing Indicator
    processing_msg = await update.message.reply_text("⚡ *Antigravity Agent is working...*", parse_mode=ParseMode.MARKDOWN)

    workspace = session["workspace"]

    # System instruction for Gemini Agent
    system_prompt = (
        f"You are the Antigravity Autonomous Coding Agent connected to Telegram.\n"
        f"You operate directly inside the user's workspace at: {workspace}\n\n"
        f"Available capabilities and syntax:\n"
        f"1. To list files: write <<<LIST_FILES: subpath>>>\n"
        f"2. To read a file: write <<<READ_FILE: relative_filepath>>>\n"
        f"3. To create/write a file: write <<<WRITE_FILE: relative_filepath>>>\nfile content here\n<<<END_WRITE>>>\n"
        f"4. To execute shell command: write <<<RUN_CMD: command_here>>> (User will be prompted for permission via Telegram buttons)\n\n"
        f"Rules:\n"
        f"- Always be helpful, concise, and professional.\n"
        f"- When creating code, write complete working implementations, not placeholders.\n"
        f"- You can explain in Hindi / Hinglish if the user asks in Hindi/Hinglish, or English if asked in English.\n"
        f"- Always summarize files created or actions performed."
    )

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Append to user history
    session["chat_history"].append({"role": "user", "text": text})

    # Prepare prompt with history
    conversation_context = "\n".join([f"{item['role'].upper()}: {item['text']}" for item in session["chat_history"][-6:]])
    full_prompt = f"{system_prompt}\n\nConversation Context:\n{conversation_context}\n\nASSISTANT:"

    try:
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=full_prompt,
        )
        agent_reply = response.text or "No response generated."

        # Parse and execute agent tool calls in the reply
        modified = False
        iteration_text = agent_reply

        # 1. Check for RUN_CMD
        if "<<<RUN_CMD:" in iteration_text:
            cmd_start_idx = iteration_text.find("<<<RUN_CMD:") + len("<<<RUN_CMD:")
            cmd_end_idx = iteration_text.find(">>>", cmd_start_idx)
            if cmd_end_idx != -1:
                cmd_to_run = iteration_text[cmd_start_idx:cmd_end_idx].strip()
                perm_result = await request_permission(
                    update=update,
                    user_id=user.id,
                    action_type="run_command",
                    action_payload=cmd_to_run,
                    workspace=workspace
                )
                iteration_text += f"\n\n*Command Execution Result:*\n```\n{perm_result[:1500]}\n```"
                modified = True

        # 2. Check for WRITE_FILE
        if "<<<WRITE_FILE:" in iteration_text:
            wf_start_idx = iteration_text.find("<<<WRITE_FILE:") + len("<<<WRITE_FILE:")
            wf_header_end = iteration_text.find(">>>", wf_start_idx)
            wf_end_idx = iteration_text.find("<<<END_WRITE>>>", wf_header_end)

            if wf_header_end != -1 and wf_end_idx != -1:
                file_rel_path = iteration_text[wf_start_idx:wf_header_end].strip()
                file_content = iteration_text[wf_header_end + 3:wf_end_idx].strip()
                write_result = execute_write_file(workspace, file_rel_path, file_content)
                iteration_text += f"\n\n*{write_result}*"
                modified = True

        # 3. Check for LIST_FILES
        if "<<<LIST_FILES:" in iteration_text:
            lf_start = iteration_text.find("<<<LIST_FILES:") + len("<<<LIST_FILES:")
            lf_end = iteration_text.find(">>>", lf_start)
            if lf_end != -1:
                sub = iteration_text[lf_start:lf_end].strip()
                files_out = execute_list_files(workspace, sub)
                iteration_text += f"\n\n*Files in `{workspace}`:*\n```\n{files_out}\n```"
                modified = True

        # Clean tags from final message display
        clean_display = (
            iteration_text
            .replace("<<<END_WRITE>>>", "")
        )

        session["chat_history"].append({"role": "assistant", "text": clean_display})

        await processing_msg.delete()
        await send_split_message(update, clean_display)

    except Exception as e:
        logger.exception("Error processing agent request")
        await processing_msg.edit_text(f"❌ Error occurred: `{str(e)}`", parse_mode=ParseMode.MARKDOWN)


def main():
    """Start Telegram bot application."""
    if not TELEGRAM_BOT_TOKEN:
        print("=" * 60)
        print("ERROR: TELEGRAM_BOT_TOKEN is not set!")
        print("Please set it in your .env file or environment variable:")
        print("  export TELEGRAM_BOT_TOKEN='your_bot_token'")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)
    print("🚀 Starting Antigravity IDE Telegram Agent Bridge...")
    print(f"🤖 Model: {DEFAULT_MODEL}")
    print(f"📁 Default Workspace: {get_default_workspace()}")
    print("=" * 60)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("folder", cmd_folder))
    app.add_handler(CommandHandler("use_default", cmd_use_default))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("help", cmd_help))

    # Interactive Permission Callbacks
    app.add_handler(CallbackQueryHandler(callback_permission_handler, pattern="^perm_"))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start Polling
    app.run_polling()


if __name__ == "__main__":
    main()
