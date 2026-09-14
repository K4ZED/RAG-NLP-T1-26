import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

import config
import rag_engine

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

WELCOME = (
    "Halo! Aku bot data ekonomi Jawa Tengah berbasis data BPS.\n\n"
    "Tanya apa saja soal ekonomi Jawa Tengah, misalnya:\n"
    "- Berapa PDRB Jawa Tengah tahun 2024?\n"
    "- Bagaimana tren inflasi Jawa Tengah?\n"
    "- Sektor apa penyumbang terbesar ekonomi Jawa Tengah?"
)

GREETING_PATTERN = re.compile(
    r"^\s*(hai|halo|hallo|hello|hi|hey|p+|tes|test|assalamualaikum|woy|min|bang)\W*\s*$",
    re.IGNORECASE,
)


def is_small_talk(text: str) -> bool:
    return bool(GREETING_PATTERN.match(text))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = update.message.text
    if is_small_talk(question):
        await update.message.reply_text(WELCOME)
        return

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    except Exception:
        logger.warning("Gagal mengirim status 'mengetik' (jaringan?), lanjut tanpa itu")

    try:
        reply = rag_engine.answer(question)
    except Exception:
        logger.exception("Failed to answer question")
        reply = "Maaf, terjadi kesalahan saat memproses pertanyaanmu. Coba lagi sebentar lagi."

    try:
        await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        # The model's markdown didn't parse cleanly - fall back to plain text
        # rather than failing to reply at all.
        await update.message.reply_text(reply)
    except Exception:
        logger.exception("Gagal mengirim balasan ke Telegram")


def build_app() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
