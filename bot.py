# ====================================================================
# 🔐 HIDE TOKEN FROM LOGS - MUST BE FIRST
# ====================================================================
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx").disabled = True
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpcore").disabled = True
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("urllib3").disabled = True

# ====================================================================
# REGULAR IMPORTS
# ====================================================================
import os
import asyncio
import threading
import json
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ====================================================================
# NORMAL LOGGING
# ====================================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====================================================================
# ENVIRONMENT VARIABLES
# ====================================================================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ No TELEGRAM_BOT_TOKEN set!")

# File to store todos
TODO_FILE = "todos.json"

# ====================================================================
# DATA STORAGE
# ====================================================================
def load_todos():
    """Load todos from file."""
    try:
        if os.path.exists(TODO_FILE):
            with open(TODO_FILE, 'r') as f:
                return json.load(f)
        return {}
    except:
        return {}

def save_todos(todos):
    """Save todos to file."""
    try:
        with open(TODO_FILE, 'w') as f:
            json.dump(todos, f, indent=2)
    except:
        pass

# Load existing todos
todos = load_todos()

# ====================================================================
# FLASK - KEEPS RENDER ALIVE
# ====================================================================
flask_app = Flask(__name__)

# Disable Flask's default logger
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@flask_app.route('/')
def health_check():
    return "✅ Todo List Bot is running!", 200

# ====================================================================
# COMMANDS
# ====================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command."""
    user = update.effective_user
    welcome_text = (
        f"✅ Hello {user.first_name}!\n\n"
        "I'm a **Todo List Bot** to help you manage your tasks!\n\n"
        "📝 **Commands:**\n"
        "/add [task] - Add a new task\n"
        "/list - Show all your tasks\n"
        "/done [number] - Mark a task as done\n"
        "/delete [number] - Delete a task\n"
        "/clear - Delete ALL tasks\n"
        "/help - Show this help\n\n"
        "💡 **Example:**\n"
        "/add Buy groceries"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command."""
    help_text = (
        "📚 **Todo List Bot Help**\n\n"
        "**Commands:**\n"
        "/add [task] - Add a new task\n"
        "/list - Show all your tasks\n"
        "/done [number] - Mark a task as done\n"
        "/delete [number] - Delete a task\n"
        "/clear - Delete ALL tasks\n"
        "/help - Show this help\n\n"
        "**Examples:**\n"
        "/add Buy milk\n"
        "/add Finish project\n"
        "/done 1\n"
        "/delete 2\n\n"
        "**Tips:**\n"
        "• Tasks are saved automatically\n"
        "• Your tasks are private to you\n"
        "• Use numbers from /list to mark done"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new task."""
    user_id = str(update.effective_user.id)
    task = update.message.text.replace("/add", "", 1).strip()
    
    if not task:
        await update.message.reply_text(
            "❌ Please provide a task.\n"
            "Example: `/add Buy groceries`"
        )
        return
    
    # Initialize user's todo list if not exists
    if user_id not in todos:
        todos[user_id] = []
    
    # Add task with timestamp
    todos[user_id].append({
        'task': task,
        'done': False,
        'created': datetime.now().isoformat()
    })
    
    # Save to file
    save_todos(todos)
    
    task_number = len(todos[user_id])
    await update.message.reply_text(
        f"✅ **Task added!**\n\n"
        f"📝 {task}\n"
        f"📊 You now have {task_number} task(s)"
    )

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all tasks."""
    user_id = str(update.effective_user.id)
    
    if user_id not in todos or not todos[user_id]:
        await update.message.reply_text(
            "📭 **No tasks found!**\n\n"
            "Add a task with:\n"
            "/add Your task here"
        )
        return
    
    tasks = todos[user_id]
    
    # Separate done and pending tasks
    pending = [t for t in tasks if not t['done']]
    done = [t for t in tasks if t['done']]
    
    # Build message
    message = "📋 **Your Todo List**\n\n"
    
    if pending:
        message += "⏳ **Pending Tasks:**\n"
        for i, task in enumerate(pending, 1):
            message += f"{i}. {task['task']}\n"
    else:
        message += "✅ **No pending tasks!**\n"
    
    if done:
        message += f"\n✅ **Completed Tasks:** {len(done)}\n"
        for i, task in enumerate(done[:3], 1):
            message += f"  ✓ {task['task']}\n"
        if len(done) > 3:
            message += f"  ...and {len(done) - 3} more\n"
    
    message += f"\n📊 **Total:** {len(tasks)} tasks"
    
    # Create inline buttons
    keyboard = []
    if pending:
        keyboard.append([InlineKeyboardButton("✅ Done", callback_data="show_done")])
    keyboard.append([InlineKeyboardButton("❌ Clear All", callback_data="confirm_clear")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)

async def mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mark a task as done."""
    user_id = str(update.effective_user.id)
    
    if user_id not in todos or not todos[user_id]:
        await update.message.reply_text(
            "❌ You have no tasks!\n"
            "Add a task with /add"
        )
        return
    
    try:
        number = int(update.message.text.replace("/done", "", 1).strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Please provide a task number.\n"
            "Example: `/done 1`\n"
            "Use /list to see task numbers."
        )
        return
    
    # Get only pending tasks
    pending = [t for t in todos[user_id] if not t['done']]
    
    if number < 1 or number > len(pending):
        await update.message.reply_text(
            f"❌ Invalid task number {number}.\n"
            f"You have {len(pending)} pending task(s)."
        )
        return
    
    # Mark as done
    task = pending[number - 1]
    task['done'] = True
    
    # Save to file
    save_todos(todos)
    
    await update.message.reply_text(
        f"✅ **Task completed!**\n\n"
        f"📝 {task['task']}\n"
        f"🎉 Great job!"
    )

async def delete_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a task."""
    user_id = str(update.effective_user.id)
    
    if user_id not in todos or not todos[user_id]:
        await update.message.reply_text(
            "❌ You have no tasks to delete."
        )
        return
    
    try:
        number = int(update.message.text.replace("/delete", "", 1).strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Please provide a task number.\n"
            "Example: `/delete 1`\n"
            "Use /list to see task numbers."
        )
        return
    
    if number < 1 or number > len(todos[user_id]):
        await update.message.reply_text(
            f"❌ Invalid task number {number}.\n"
            f"You have {len(todos[user_id])} task(s)."
        )
        return
    
    # Delete the task
    deleted_task = todos[user_id].pop(number - 1)
    
    # Save to file
    save_todos(todos)
    
    await update.message.reply_text(
        f"🗑️ **Task deleted!**\n\n"
        f"📝 {deleted_task['task']}"
    )

async def clear_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all tasks."""
    user_id = str(update.effective_user.id)
    
    if user_id not in todos or not todos[user_id]:
        await update.message.reply_text(
            "📭 You have no tasks to clear."
        )
        return
    
    # Ask for confirmation
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Clear All", callback_data="clear_all"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"⚠️ **Warning!**\n\n"
        f"You have {len(todos[user_id])} tasks.\n"
        f"Are you sure you want to delete ALL tasks?",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle non-command messages."""
    await update.message.reply_text(
        "❌ I only understand commands.\n\n"
        "Try:\n"
        "/add Your task\n"
        "/list\n"
        "/done 1\n"
        "/help"
    )

# ====================================================================
# CALLBACK HANDLER
# ====================================================================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks."""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    data = query.data
    
    if data == "show_done":
        # Show completed tasks
        if user_id in todos and todos[user_id]:
            done = [t for t in todos[user_id] if t['done']]
            if done:
                text = "✅ **Completed Tasks:**\n\n"
                for i, task in enumerate(done, 1):
                    text += f"{i}. ✓ {task['task']}\n"
                text += f"\nTotal: {len(done)} tasks"
                await query.edit_message_text(text, parse_mode="Markdown")
            else:
                await query.edit_message_text("📭 No completed tasks yet.")
    
    elif data == "confirm_clear":
        # Confirm clear
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Clear All", callback_data="clear_all"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"⚠️ Are you sure you want to delete ALL your tasks?",
            reply_markup=reply_markup
        )
    
    elif data == "clear_all":
        if user_id in todos:
            count = len(todos[user_id])
            todos[user_id] = []
            save_todos(todos)
            await query.edit_message_text(
                f"🗑️ **Cleared all {count} tasks!**"
            )
    
    elif data == "cancel":
        await query.edit_message_text("✅ Cancelled.")

# ====================================================================
# ERROR HANDLER
# ====================================================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and prevent bot from crashing."""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )
    except:
        pass

# ====================================================================
# BOT STARTUP
# ====================================================================

async def run_bot_async():
    """Run the bot asynchronously."""
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_task))
    application.add_handler(CommandHandler("list", list_tasks))
    application.add_handler(CommandHandler("done", mark_done))
    application.add_handler(CommandHandler("delete", delete_task))
    application.add_handler(CommandHandler("clear", clear_tasks))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )
    
    logger.info("✅ Todo List Bot is polling and ready!")
    
    while True:
        await asyncio.sleep(1)

def run_bot():
    """Run bot in a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bot_async())

# Start bot thread when Gunicorn loads
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# ====================================================================
# MAIN
# ====================================================================
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
