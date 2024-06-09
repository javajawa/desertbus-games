# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from types import TracebackType
from typing import Any

import traceback

from pythonjsonlogger.jsonlogger import JsonFormatter as _JsonFormatter

_SysExcInfoType = (
    tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]
)


class JsonFormatter(_JsonFormatter):
    def formatException(self, ei: _SysExcInfoType) -> dict[str, Any] | None:  # type: ignore[override]
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
