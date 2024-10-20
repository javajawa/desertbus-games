# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from types import TracebackType
from typing import Any

import logging
import traceback

from pythonjsonlogger.jsonlogger import JsonFormatter as _JsonFormatter

try:
    import systemd.journal  # type: ignore[import-not-found]

    JournalHandler = systemd.journal.JournalHandler
except ImportError:

    class JournalHandler(logging.StreamHandler):  # type: ignore[no-redef,type-arg]
        def __init__(self, *, SYSLOG_IDENTIFIER: str = "") -> None:  # noqa: ARG002, N803
            super().__init__()


_SysExcInfoType = (
    tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]
)


class JsonFormatter(_JsonFormatter):
    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        log_record["level"] = record.levelname
        log_record["logger"] = record.name

        super().add_fields(log_record, record, message_dict)

    def formatException(  # type: ignore[override]  # noqa: N802 inherited function name
        self,
        ei: _SysExcInfoType,
    ) -> dict[str, Any] | None:
        exc_type, exc_value, exc_traceback = ei
        if exc_type is None or exc_value is None:
            return None

        trace = traceback.extract_tb(exc_traceback)

        return {
            "type": exc_type.__name__,
            "message": str(exc_value),
            "traceback": [
                {
                    "source": f"{frame.filename}:{frame.lineno}",
                    "method": frame.name,
                    "code": frame.line,
                    "locals": frame.locals,
                }
                for frame in reversed(trace)
            ],
            "cause": (
                self.formatException(
                    (
                        type(exc_value.__cause__),
                        exc_value.__cause__,
                        exc_value.__cause__.__traceback__,
                    ),
                )
                if exc_value.__cause__
                else None
            ),
        }


__all__ = "JsonFormatter", "JournalHandler"
