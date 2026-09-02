#!/usr/bin/env python3
"""
Dedicated Local High-Speed Telegram OTP Fetcher Bot.
Configured for token: 8608370017:AAGbxIl_DthDCbRwQw7jSw6iuugtwNF7n0w

Usage:
    python local_otp_bot.py
"""

import os
import sys
import re
import html
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import fcremica_core as core

# Fix Windows console UTF-8 output encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("LocalOTPBot")

# Bot Token provided by user
DEFAULT_BOT_TOKEN = "8608370017:AAGbxIl_DthDCbRwQw7jSw6iuugtwNF7n0w"
BOT_TOKEN = os.environ.get("BOT_TOKEN", DEFAULT_BOT_TOKEN).strip()


def format_otp_html(result: dict):
    phone = result.get("phone", "")
    status = result.get("status")

    if status != "success" or not result.get("messages"):
        err_msg = result.get("message", "No messages found for this number.")
        text = (
            f"📱 <b>OTP FETCH RESULTS: <code>{phone}</code></b>\n\n"
            f"⚠️ <b>Status:</b> {err_msg}\n\n"
            f"<i>Make sure this phone number is connected on your Firebase panels.</i>"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh OTPs", callback_data=f"ref_{phone}"),
                InlineKeyboardButton("📱 Try Another Number", callback_data="btn_another"),
            ]
        ])
        return text, keyboard

    messages = result.get("messages", [])
    lines = [f"📱 <b>OTP FETCH RESULTS: <code>{phone}</code></b>\n"]

    for idx, m in enumerate(messages[:3], 1):
        otp = m.get("otp", "N/A")
        sender = m.get("sender", "Unknown")
        time_str = m.get("time", "Unknown")
        body = html.escape(m.get("body", ""))

        lines.append(f"<b>{idx}. [🔑 OTP: <code>{otp}</code>]</b>")
        lines.append(f"⏰ <b>Time:</b> {time_str} | <b>Sender:</b> {sender}")
        lines.append(f"💬 <code>{body}</code>\n")

    lines.append("👉 <i>Click 'Refresh OTPs' after requesting an OTP on the redemption website.</i>")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh OTPs", callback_data=f"ref_{phone}"),
            InlineKeyboardButton("📱 Try Another Number", callback_data="btn_another"),
        ]
    ])

    return "\n".join(lines), keyboard


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"🔥 <b>Instant OTP Fetcher Bot Ready</b> 🔥\n\n"
        f"Hi <b>{user.first_name}</b>!\n"
        f"Simply send ANY 10-digit mobile number in chat (e.g. <code>7208360119</code>, <code>7492077040</code>, <code>8432518738</code>).\n\n"
        f"⚡ <b>Response Speed:</b> ~50ms Direct Lookup\n"
        f"📩 <b>Output:</b> Top 3 Latest Messages & OTP Codes\n\n"
        f"Send a mobile number to fetch OTPs now!"
    )
    await update.message.reply_html(welcome_text)


async def handle_otp_request(update: Update, context: ContextTypes.DEFAULT_TYPE, phone_input: str, is_edit=False):
    clean_phone = re.sub(r"\D", "", phone_input)
    if len(clean_phone) > 10 and clean_phone.startswith("91"):
        clean_phone = clean_phone[2:]

    if len(clean_phone) != 10 or not clean_phone.isdigit() or clean_phone[0] not in "6789":
        msg = "❌ <b>Invalid Phone Number!</b> Please enter a valid 10-digit Indian mobile number."
        if update.callback_query:
            await update.callback_query.message.edit_text(msg, parse_mode="HTML")
        else:
            await update.message.reply_html(msg)
        return

    if update.callback_query and is_edit:
        status_msg = update.callback_query.message
    elif update.callback_query:
        status_msg = await update.callback_query.message.reply_html(f"⚡ <b>Fetching latest OTPs for <code>{clean_phone}</code>...</b>")
    else:
        status_msg = await update.message.reply_html(f"⚡ <b>Fetching latest OTPs for <code>{clean_phone}</code>...</b>")

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: core.fetch_otp_for_phone(clean_phone))

    html_text, keyboard = format_otp_html(result)

    try:
        await status_msg.edit_text(html_text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        pass


async def otp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_html("Usage: <code>/otp 7208360119</code>")
        return
    await handle_otp_request(update, context, context.args[0])


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    clean_digits = re.sub(r"\D", "", text)
    if len(clean_digits) > 10 and clean_digits.startswith("91"):
        clean_digits = clean_digits[2:]

    if len(clean_digits) == 10 and clean_digits[0] in "6789":
        await handle_otp_request(update, context, clean_digits)
    else:
        await update.message.reply_html(
            "📩 <b>Instant OTP Fetcher Bot</b>\n\n"
            "Please send any <b>10-digit mobile number</b> (e.g., <code>7208360119</code> or <code>7492077040</code>) to fetch its latest 3 OTPs instantly!"
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("ref_"):
        phone = data.replace("ref_", "").strip()
        await handle_otp_request(update, context, phone, is_edit=True)
    elif data == "btn_another":
        await query.message.reply_html(
            "📩 <b>Send Another Number</b>\n\n"
            "Please type or paste any 10-digit mobile number in chat:"
        )


async def main_async():
    print("=" * 65)
    print("🚀 Starting Dedicated Local Telegram OTP Fetcher Bot")
    print("=" * 65)
    print(f"Token: {BOT_TOKEN[:15]}...{BOT_TOKEN[-5:]}")
    print("Initializing Telegram polling engine...")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(CommandHandler("otp", otp_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    print("\n🟢 BOT IS LIVE AND ACTIVE! Send any mobile number in your Telegram chat now.")
    print("Press Ctrl+C to stop.\n")

    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        print("\nStopping Local OTP Bot...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
