# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TypeAlias

from .engine import GameEngine, OptionSupport
from .episode import EpisodeMeta, EpisodeState, EpisodeVersion

JSON: TypeAlias = (  # pylint: disable=invalid-name
    None | int | str | bool | float | list["JSON"] | dict[str, "JSON"]
)
JSONDict: TypeAlias = dict[str, "JSON"]


__all__ = [
    "GameEngine",
    "EpisodeMeta",
    "EpisodeVersion",
    "EpisodeState",
    "OptionSupport",
    "JSON",
    "JSONDict",
]
