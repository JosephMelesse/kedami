import os
import threading
import time
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from . import db, library
from .app import create_app
from .config import from_env
from .generation.pipeline import lesson_path
from .storage import seed_sample


def exit_with_parent() -> None:
    """Exit if the process that started us goes away, so a crashed app leaves no server behind."""
    parent = os.getppid()

    def watch() -> None:
        while os.getppid() == parent:
            time.sleep(1)
        os._exit(0)

    threading.Thread(target=watch, daemon=True).start()


def main() -> None:
    # The Anthropic client reads ANTHROPIC_API_KEY from the environment; the key stays in this process.
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    settings = from_env()
    db.init(settings.data_dir)
    with db.connect(settings.data_dir) as conn:
        library.fail_interrupted(conn, lambda lesson_id: lesson_path(settings.data_dir, lesson_id).exists())
    seed_sample(settings.data_dir)
    exit_with_parent()
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port, log_level="warning")


if __name__ == "__main__":
    main()
