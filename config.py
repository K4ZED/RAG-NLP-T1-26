import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


BPS_API_KEY = _require("BPS_API_KEY")
GEMINI_API_KEY = _require("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")

BPS_DOMAIN = os.getenv("BPS_DOMAIN", "3300")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))

# "local" (free, offline, sentence-transformers) or "gemini" (API-based, quota-limited)
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "local")
LOCAL_EMBEDDING_MODEL = os.getenv(
    "LOCAL_EMBEDDING_MODEL", "paraphrase-multilingual-mpnet-base-v2"
)

CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
# Suffixed per backend: the two backends produce vectors of different
# dimensionality/space, so they cannot share a collection.
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "bps_jateng_ekonomi") + f"_{EMBEDDING_BACKEND}"

RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
