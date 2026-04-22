from __future__ import annotations

import logging

from hermes_life_admin.bot import build_application
from hermes_life_admin.config import AppConfig


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = AppConfig.from_env()
    application = build_application(config)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
