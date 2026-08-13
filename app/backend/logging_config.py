from __future__ import annotations

import logging


APPLICATION_LOGGER_NAME = "ad_creative_studio"
_HANDLER_MARKER = "_ad_creative_studio_stderr_handler"


def configure_application_logging(*, level: int = logging.INFO) -> None:
    logger = logging.getLogger(APPLICATION_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    if any(getattr(handler, _HANDLER_MARKER, False) for handler in logger.handlers):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    )
    setattr(handler, _HANDLER_MARKER, True)
    logger.addHandler(handler)
