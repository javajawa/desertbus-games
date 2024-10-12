# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import MutableMapping, MutableSequence
from typing import TypeAlias, Union

from .engine import GameEngine, OptionSupport
from .episode import EpisodeMeta, EpisodeState, EpisodeVersion

JSON: TypeAlias = Union[None, int, str, bool, float, "JSONDict", "JSONList", list[str]]
JSONList: TypeAlias = MutableSequence[JSON]
JSONDict: TypeAlias = MutableMapping[str, JSON]


__all__ = [
    "GameEngine",
    "EpisodeMeta",
    "EpisodeVersion",
    "EpisodeState",
    "OptionSupport",
    "JSON",
    "JSONDict",
]
