import os
import threading
import time

import uvicorn

from .app import create_app
from .config import from_env
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
    settings = from_env()
    seed_sample(settings.data_dir)
    exit_with_parent()
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port, log_level="warning")


if __name__ == "__main__":
    main()
