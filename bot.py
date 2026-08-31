#!/usr/bin/env python3
"""
Cremica School Shuru - Premium Telegram Bot & Render Deployment Server.
Features:
- Interactive HTML UI with inline keyboards & progress bars
- Multi-link & text file (.txt) panel upload support
- Single number processing with interactive OTP prompt
- Configurable Batch Code & exportable logs
- Embedded aiohttp HTTP server for Render 24/7 web service keep-alive
- Security via ADMIN_IDS environment variable
"""

import os
import sys
import asyncio
import logging
from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import fcremica_core as core

# ----------------------------------------------------------------------
# Configuration & Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("CremicaBot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "").strip()
ADMIN_IDS = set(int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit())
PORT = int(os.environ.get("PORT", "8080"))
CURRENT_BATCH_CODE = os.environ.get("DEFAULT_BATCH_CODE", "CD06G26").strip()

# Conversation states for Single Number & Batch Code updates
WAITING_PANEL_INPUT = 1
WAITING_SINGLE_PHONE = 2
WAITING_SINGLE_OTP = 3
WAITING_BATCH_CODE = 4

# ----------------------------------------------------------------------
# Helper Functions
def is_authorized(user_id: int) -> bool:
    if not ADMIN_IDS:
        return True  # If ADMIN_IDS is empty, permit all (or configure as needed)
    return user_id in ADMIN_IDS


def build_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🚀 Bulk Panel Process", callback_data="btn_bulk"),
            InlineKeyboardButton("📱 Single Number", callback_data="btn_single"),
        ],
        [
            InlineKeyboardButton(f"🏷️ Batch Code ({CURRENT_BATCH_CODE})", callback_data="btn_batch"),
            InlineKeyboardButton("📊 View/Export Logs", callback_data="btn_logs"),
        ],
        [
            InlineKeyboardButton("ℹ️ System Status", callback_data="btn_status"),
            InlineKeyboardButton("❓ Help Guide", callback_data="btn_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def progress_bar(completed: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return "░" * length
    filled = int(length * completed / total)
    return "█" * filled + "░" * (length - filled)


# ----------------------------------------------------------------------
# Render Web Server Keep-Alive Handlers
async def handle_root(request):
    return web.Response(
        text="<b>⚡ Cremica Premium Telegram Bot Service is Running Active!</b>",
        content_type="text/html",
    )


async def handle_health(request):
    return web.json_response(
        {
            "status": "online",
            "bot": "active",
            "batch_code": CURRENT_BATCH_CODE,
            "timestamp": core.datetime.now().isoformat(),
        }
    )


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 Keep-alive Web Server started on port {PORT}")


# ----------------------------------------------------------------------
# Bot Command Handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        await update.message.reply_html(
            "⚠️ <b>Access Denied</b>\n"
            "You are not authorized to use this bot.\n"
            f"Your Telegram ID: <code>{user.id}</code>"
        )
        return

    welcome_text = (
        f"🔥 <b>Welcome to Cremica Automation Bot</b> 🔥\n\n"
        f"Hi <b>{user.first_name}</b>! I am your automated high-speed engine for Cremica School Shuru campaign.\n\n"
        f"📌 <b>Active Batch Code:</b> <code>{CURRENT_BATCH_CODE}</code>\n"
        f"⚡ <b>Engine Status:</b> 🟢 Ready\n\n"
        f"Select an action from the menu below or send a panel link directly!"
    )
    await update.message.reply_html(welcome_text, reply_markup=build_menu_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 <b>Cremica Bot User Guide</b>\n\n"
        "<b>1. Bulk Firebase Panels:</b>\n"
        "• Send one or multiple Firebase links in chat text.\n"
        "• Or upload a <code>.txt</code> file containing Firebase URLs.\n"
        "• The bot auto-detects online devices & polls Firebase for OTPs.\n\n"
        "<b>2. Single Number Processing:</b>\n"
        "• Click <b>📱 Single Number</b>, enter phone number, then enter the OTP received.\n\n"
        "<b>3. Batch Code Management:</b>\n"
        "• Use <code>/setbatch &lt;CODE&gt;</code> or click <b>🏷️ Batch Code</b> to change.\n\n"
        "<b>4. Logs Export:</b>\n"
        "• Use <code>/logs</code> or click <b>📊 View/Export Logs</b> to download the CSV result log."
    )
    if update.callback_query:
        await update.callback_query.message.edit_text(help_text, parse_mode="HTML", reply_markup=build_menu_keyboard())
    else:
        await update.message.reply_html(help_text, reply_markup=build_menu_keyboard())


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_count = 0
    if os.path.exists(core.LOG_FILE):
        with open(core.LOG_FILE, "r", encoding="utf-8") as f:
            log_count = max(0, len(f.readlines()) - 1)

    status_text = (
        "⚡ <b>System Diagnostic & Status</b>\n\n"
        f"• <b>Bot Status:</b> 🟢 Online\n"
        f"• <b>Web Health Server:</b> 🟢 Active (Port {PORT})\n"
        f"• <b>Current Batch Code:</b> <code>{CURRENT_BATCH_CODE}</code>\n"
        f"• <b>Total Logged Records:</b> <code>{log_count}</code>\n"
        f"• <b>Admin Lock:</b> {'🔒 Enabled' if ADMIN_IDS else '🔓 Open'}\n"
    )
    if update.callback_query:
        await update.callback_query.message.edit_text(status_text, parse_mode="HTML", reply_markup=build_menu_keyboard())
    else:
        await update.message.reply_html(status_text, reply_markup=build_menu_keyboard())


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if not os.path.exists(core.LOG_FILE):
        msg = "ℹ️ No log file found yet. Run some tasks first!"
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return

    chat_id = update.effective_chat.id
    await context.bot.send_document(
        chat_id=chat_id,
        document=InputFile(core.LOG_FILE, filename="cremica_results.csv"),
        caption="📊 <b>Cremica Campaign Execution Logs</b>",
        parse_mode="HTML",
    )


# ----------------------------------------------------------------------
# Callback Query Handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not is_authorized(query.from_user.id):
        await query.message.reply_text("⚠️ Access denied.")
        return

    if data == "btn_bulk":
        await query.message.reply_html(
            "🚀 <b>Bulk Panel Processing</b>\n\n"
            "Please paste your <b>Firebase URL(s)</b> here or upload a <code>.txt</code> file containing links!"
        )
    elif data == "btn_single":
        await query.message.reply_html(
            "📱 <b>Single Number Processing</b>\n\n"
            "Please enter the 10-digit mobile number:"
        )
        return WAITING_SINGLE_PHONE
    elif data == "btn_batch":
        await query.message.reply_html(
            f"🏷️ <b>Change Batch Code</b>\n\n"
            f"Current Code: <code>{CURRENT_BATCH_CODE}</code>\n"
            "Send new Batch Code in chat or type <code>/cancel</code>:"
        )
        return WAITING_BATCH_CODE
    elif data == "btn_logs":
        await logs_command(update, context)
    elif data == "btn_status":
        await status_command(update, context)
    elif data == "btn_help":
        await help_command(update, context)


# ----------------------------------------------------------------------
# Change Batch Code Flow
async def set_batch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CURRENT_BATCH_CODE
    user = update.effective_user
    if not is_authorized(user.id):
        return

    if context.args:
        new_code = context.args[0].strip().upper()
        CURRENT_BATCH_CODE = new_code
        await update.message.reply_html(
            f"✅ <b>Batch Code Updated!</b>\nNew Batch Code: <code>{CURRENT_BATCH_CODE}</code>"
        )
    else:
        await update.message.reply_html(
            f"Current Batch Code: <code>{CURRENT_BATCH_CODE}</code>\n"
            "To change, use: <code>/setbatch &lt;NEW_CODE&gt;</code>"
        )


async def receive_new_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CURRENT_BATCH_CODE
    new_code = update.message.text.strip().upper()
    CURRENT_BATCH_CODE = new_code
    await update.message.reply_html(
        f"✅ <b>Batch Code Updated!</b>\nNew Batch Code: <code>{CURRENT_BATCH_CODE}</code>",
        reply_markup=build_menu_keyboard(),
    )
    return ConversationHandler.END


# ----------------------------------------------------------------------
# Single Number Manual Flow
async def receive_single_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    clean_phone = re.sub(r"\D", "", phone)
    if len(clean_phone) > 10 and clean_phone.startswith("91"):
        clean_phone = clean_phone[2:]
    if len(clean_phone) != 10 or not clean_phone.isdigit():
        await update.message.reply_html(
            "❌ <b>Invalid Phone Number!</b>\nPlease enter a valid 10-digit Indian mobile number:"
        )
        return WAITING_SINGLE_PHONE

    context.user_data["single_phone"] = clean_phone
    name = core.random_indian_name()
    state = core.random_state()
    context.user_data["single_name"] = name
    context.user_data["single_state"] = state

    status_msg = await update.message.reply_html(
        f"⏳ <b>Initiating Registration...</b>\n"
        f"• <b>Phone:</b> <code>{clean_phone}</code>\n"
        f"• <b>Name:</b> {name}\n"
        f"• <b>State:</b> {state}\n\n"
        "Sending OTP request..."
    )

    try:
        session = core.requests.Session()
        user_data = core.create_user(session)
        user_key = user_data["userKey"]
        data_key = user_data["dataKey"]
        core.track_click(user_key, data_key, session)
        core.register(user_key, data_key, name, clean_phone, session)

        context.user_data["single_user_key"] = user_key
        context.user_data["single_data_key"] = data_key
        context.user_data["single_session"] = session

        await status_msg.edit_text(
            f"✅ <b>OTP Sent Successfully!</b>\n\n"
            f"• <b>Phone:</b> <code>{clean_phone}</code>\n"
            f"• <b>Name:</b> {name}\n"
            f"• <b>Batch:</b> <code>{CURRENT_BATCH_CODE}</code>\n\n"
            "📩 <b>Please reply with the received OTP in this chat:</b>",
            parse_mode="HTML",
        )
        return WAITING_SINGLE_OTP
    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Registration Request Failed:</b> {e}", parse_mode="HTML"
        )
        return ConversationHandler.END


async def receive_single_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    otp = update.message.text.strip()
    if not otp.isdigit() or len(otp) not in (4, 6):
        await update.message.reply_html(
            "❌ <b>Invalid OTP format!</b> Please enter a 4 or 6 digit OTP:"
        )
        return WAITING_SINGLE_OTP

    phone = context.user_data.get("single_phone")
    name = context.user_data.get("single_name")
    state = context.user_data.get("single_state")
    user_key = context.user_data.get("single_user_key")
    data_key = context.user_data.get("single_data_key")
    session = context.user_data.get("single_session")

    status_msg = await update.message.reply_html("⏳ <b>Verifying OTP & Submitting Batch Code...</b>")

    try:
        access_token = core.verify_otp(user_key, data_key, otp, session)
        core.get_batch_code(user_key, data_key, access_token, CURRENT_BATCH_CODE, state, session)
        core.log_result(phone, name, state, CURRENT_BATCH_CODE, "success", "Manual Telegram OTP verified")
        await status_msg.edit_text(
            f"🎉 <b>Success! Registration Complete</b>\n\n"
            f"• <b>Phone:</b> <code>{phone}</code>\n"
            f"• <b>Name:</b> {name}\n"
            f"• <b>State:</b> {state}\n"
            f"• <b>Batch Code:</b> <code>{CURRENT_BATCH_CODE}</code>\n"
            f"• <b>Status:</b> Validated & Logged!",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
        )
    except Exception as e:
        core.log_result(phone, name, state, CURRENT_BATCH_CODE, "verify_failed", str(e))
        await status_msg.edit_text(
            f"❌ <b>Verification Failed:</b> {e}",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
        )
    finally:
        if session:
            session.close()

    return ConversationHandler.END


async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html("🚫 Action cancelled.", reply_markup=build_menu_keyboard())
    return ConversationHandler.END


# ----------------------------------------------------------------------
# Bulk Panel Link & File Processor
async def handle_panel_processing(update: Update, context: ContextTypes.DEFAULT_TYPE, lines: list):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    panel_urls = []
    for line in lines:
        parsed = core.parse_firebase_link(line)
        if parsed:
            panel_urls.append(parsed)

    if not panel_urls:
        await update.message.reply_html(
            "❌ <b>No valid Firebase URLs found!</b>\nMake sure your link contains <code>firebaseio.com</code> or <code>firebasedatabase.app</code>."
        )
        return

    status_msg = await update.message.reply_html(
        f"🔄 <b>Scanning {len(panel_urls)} Firebase Panel(s)...</b>\nFetching connected online devices..."
    )

    all_jobs = []
    for idx, fb_url in enumerate(panel_urls, 1):
        devices = core.fetch_devices_and_phones(fb_url)
        for dev in devices:
            phone = dev["phone"]
            name = core.random_indian_name()
            state = core.random_state()
            all_jobs.append((phone, name, state, fb_url, dev["client_id"]))

    if not all_jobs:
        await status_msg.edit_text(
            "⚠️ <b>No online devices with numbers found in the provided Firebase panels.</b>",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
        )
        return

    total_jobs = len(all_jobs)
    await status_msg.edit_text(
        f"⚡ <b>Found {total_jobs} device(s) across {len(panel_urls)} panel(s).</b>\n"
        f"Starting parallel execution engine with Batch Code <code>{CURRENT_BATCH_CODE}</code>...\n\n"
        f"<code>[{progress_bar(0, total_jobs)}] 0/{total_jobs}</code>",
        parse_mode="HTML",
    )

    loop = asyncio.get_running_loop()
    last_update_time = [0.0]

    def on_progress(completed, total, outcome):
        now = asyncio.get_event_loop().time()
        if now - last_update_time[0] >= 3.0 or completed == total:
            last_update_time[0] = now
            bar = progress_bar(completed, total)
            text = (
                f"⚡ <b>Processing Bulk Campaign...</b>\n\n"
                f"Progress: <code>[{bar}] {completed}/{total}</code>\n"
                f"Batch Code: <code>{CURRENT_BATCH_CODE}</code>"
            )
            asyncio.run_coroutine_threadsafe(
                status_msg.edit_text(text, parse_mode="HTML"), loop
            )

    # Run blocking processing in threadpool executor
    total_success, results = await loop.run_in_executor(
        None,
        lambda: core.process_numbers_parallel(
            all_jobs, CURRENT_BATCH_CODE, max_workers=5, progress_callback=on_progress
        ),
    )

    summary_text = (
        f"🎉 <b>Bulk Processing Complete!</b>\n\n"
        f"• <b>Total Numbers Processed:</b> {total_jobs}\n"
        f"• <b>Successful Registrations:</b> <code>{total_success}</code>\n"
        f"• <b>Failed/Timeout:</b> <code>{total_jobs - total_success}</code>\n"
        f"• <b>Batch Code Used:</b> <code>{CURRENT_BATCH_CODE}</code>\n\n"
        f"📄 Results saved to <code>cremica_results.txt</code>"
    )

    await status_msg.edit_text(summary_text, parse_mode="HTML", reply_markup=build_menu_keyboard())

    # Send log file as document
    if os.path.exists(core.LOG_FILE):
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=InputFile(core.LOG_FILE, filename="cremica_results.csv"),
            caption="📊 <b>Campaign Execution Log Output</b>",
            parse_mode="HTML",
        )


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    text = update.message.text.strip()
    if "firebaseio.com" in text or "firebasedatabase.app" in text or "s=" in text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        await handle_panel_processing(update, context, lines)
    else:
        await update.message.reply_html(
            "❓ Unrecognized text format. Send a Firebase URL or click a button from `/start` menu.",
            reply_markup=build_menu_keyboard(),
        )


async def document_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_authorized(user.id):
        return

    doc = update.message.document
    if not doc.file_name.endswith(".txt"):
        await update.message.reply_html("❌ Please upload a <code>.txt</code> file containing Firebase URLs.")
        return

    file_obj = await context.bot.get_file(doc.file_id)
    byte_content = await file_obj.download_as_bytearray()
    content_str = byte_content.decode("utf-8", errors="ignore")
    lines = [line.strip() for line in content_str.splitlines() if line.strip()]

    await update.message.reply_html(f"📥 Received file <code>{doc.file_name}</code> with {len(lines)} line(s).")
    await handle_panel_processing(update, context, lines)


# ----------------------------------------------------------------------
# Main Application Launcher
def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN environment variable not found! Exiting.")
        sys.exit(1)

    # Initialize Telegram Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation Handlers for Single Mode & Batch Mode
    single_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_callback, pattern="^btn_single$"),
            CommandHandler("single", button_callback),
        ],
        states={
            WAITING_SINGLE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_single_phone)],
            WAITING_SINGLE_OTP: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_single_otp)],
        },
        fallbacks=[CommandHandler("cancel", cancel_flow)],
    )

    batch_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_callback, pattern="^btn_batch$"),
            CommandHandler("setbatch", set_batch_command),
        ],
        states={
            WAITING_BATCH_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_batch)],
        },
        fallbacks=[CommandHandler("cancel", cancel_flow)],
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("setbatch", set_batch_command))
    application.add_handler(single_conv)
    application.add_handler(batch_conv)
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.Document.ALL, document_file_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    # Event loop setup for concurrent Telegram bot polling & keep-alive web server
    loop = asyncio.get_event_loop()

    # Schedule Web Server
    loop.create_task(start_web_server())

    logger.info("🚀 Cremica Telegram Bot is starting polling...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
