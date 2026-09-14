import rag_engine
from bot import build_app


def main():
    print("Menyiapkan model embedding...")
    rag_engine.embed_text("pemanasan", task_type="RETRIEVAL_QUERY")

    app = build_app()
    print("Bot berjalan... tekan Ctrl+C untuk berhenti.")
    app.run_polling()


if __name__ == "__main__":
    main()
