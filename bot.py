import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import rag_engine

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

WELCOME = (
    "Halo! Aku bot data ekonomi Jawa Tengah berbasis data BPS.\n\n"
    "Pilih topik di bawah, atau langsung tanya bebas, misalnya:\n"
    "- Berapa PDRB Jawa Tengah tahun 2024?\n"
    "- Bagaimana tren inflasi Jawa Tengah?"
)

# label -> pertanyaan default yang dikirim ke RAG saat tombol topik ditekan
TOPICS = {
    "pdrb": ("📈 PDRB", "Bagaimana kondisi PDRB (Produk Domestik Regional Bruto) Jawa Tengah?"),
    "inflasi": ("💰 Inflasi", "Bagaimana tren inflasi di Jawa Tengah?"),
    "keuangan": ("🏦 Keuangan", "Bagaimana kondisi keuangan (tabungan, kredit, investasi) di Jawa Tengah?"),
    "pariwisata": ("🏨 Pariwisata", "Bagaimana kondisi pariwisata dan perhotelan di Jawa Tengah?"),
    "industri": ("🏭 Industri", "Bagaimana kondisi industri di Jawa Tengah?"),
    "ekspor_impor": ("🚢 Ekspor-Impor", "Bagaimana kondisi ekspor-impor Jawa Tengah?"),
    "energi": ("⚡ Energi", "Bagaimana kondisi energi (listrik, SPBU, gas) di Jawa Tengah?"),
    "transportasi": ("🚌 Transportasi", "Bagaimana kondisi transportasi di Jawa Tengah?"),
    "ntp": ("🌾 Nilai Tukar Petani", "Berapa Nilai Tukar Petani (NTP) terbaru di Jawa Tengah?"),
    "komunikasi": ("📡 Komunikasi", "Bagaimana kondisi komunikasi dan akses internet di Jawa Tengah?"),
    "perdagangan": ("🛒 Perdagangan", "Bagaimana kondisi perdagangan di Jawa Tengah?"),
    "konstruksi": ("🏗️ Konstruksi", "Bagaimana kondisi konstruksi di Jawa Tengah?"),
}

GREETING_PATTERN = re.compile(
    r"^\s*(hai|halo|hallo|hello|hi|hey|p+|tes|test|assalamualaikum|woy|min|bang)\W*\s*$",
    re.IGNORECASE,
)


def is_small_talk(text: str) -> bool:
    return bool(GREETING_PATTERN.match(text))


def topics_keyboard() -> InlineKeyboardMarkup:
    keys = list(TOPICS.items())
    rows = [
        [
            InlineKeyboardButton(keys[i][1][0], callback_data=f"topic:{keys[i][0]}"),
            InlineKeyboardButton(keys[i + 1][1][0], callback_data=f"topic:{keys[i + 1][0]}"),
        ]
        for i in range(0, len(keys) - 1, 2)
    ]
    if len(keys) % 2:
        rows.append([InlineKeyboardButton(keys[-1][1][0], callback_data=f"topic:{keys[-1][0]}")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME, reply_markup=topics_keyboard())


async def send_answer(question: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception:
        logger.warning("Gagal mengirim status 'mengetik' (jaringan?), lanjut tanpa itu")

    try:
        reply = rag_engine.answer(question)
    except Exception:
        logger.exception("Failed to answer question")
        reply = "Maaf, terjadi kesalahan saat memproses pertanyaanmu. Coba lagi sebentar lagi."

    try:
        await context.bot.send_message(chat_id=chat_id, text=reply, parse_mode=ParseMode.MARKDOWN)
    except BadRequest:
        # The model's markdown didn't parse cleanly - fall back to plain text
        # rather than failing to reply at all.
        await context.bot.send_message(chat_id=chat_id, text=reply)
    except Exception:
        logger.exception("Gagal mengirim balasan ke Telegram")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = update.message.text
    if is_small_talk(question):
        await update.message.reply_text(WELCOME, reply_markup=topics_keyboard())
        return
    await send_answer(question, update.effective_chat.id, context)


async def handle_topic_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    topic_key = query.data.removeprefix("topic:")
    topic = TOPICS.get(topic_key)
    if not topic:
        return
    label, question = topic
    await context.bot.send_message(chat_id=query.message.chat_id, text=f"{label}\n{question}")
    await send_answer(question, query.message.chat_id, context)


def build_app() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_topic_button, pattern=r"^topic:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
