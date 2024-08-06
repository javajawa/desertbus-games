# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import json

from catbox.engine import EpisodeVersion, JSONDict

MAX_TEAMS = 2
QUESTIONS_PER_ROUND = 6


class OnlyConnectQuestion:
    @classmethod
    def default(cls) -> JSONDict:
        return {"connection": "", "elements": [""] * 4}

    connection: str
    details: str
    elements: tuple[str, str, str, str]

    def __init__(self, connection: str, details: str, elements: tuple[str, str, str, str]) -> None:
        self.connection = connection
        self.details = details
        self.elements = elements

    def json(self) -> JSONDict:
        return {
            "connection": self.connection,
            "details": self.details,
            "elements": list(self.elements),
        }


SixQuestions = tuple[
    OnlyConnectQuestion,
    OnlyConnectQuestion,
    OnlyConnectQuestion,
    OnlyConnectQuestion,
    OnlyConnectQuestion,
    OnlyConnectQuestion,
]


class ConnectingWall:
    @classmethod
    def default(cls) -> list[JSONDict]:
        return [OnlyConnectQuestion.default()] * 4

    connections: tuple[
        OnlyConnectQuestion,
        OnlyConnectQuestion,
        OnlyConnectQuestion,
        OnlyConnectQuestion,
    ]

    def __init__(
        self,
        group_a: OnlyConnectQuestion,
        group_b: OnlyConnectQuestion,
        group_c: OnlyConnectQuestion,
        group_d: OnlyConnectQuestion,
    ) -> None:
        self.connections = (group_a, group_b, group_c, group_d)

    @property
    def clues(self) -> tuple[str, ...]:
        return sum((group.elements for group in self.connections), ())

    def json(self) -> JSONDict:
        return {"connections": [section.json() for section in self.connections]}


class MissingVowelsGroup:
    connection: str
    words: list[str]

    def __init__(self, connection: str, words: list[str]) -> None:
        self.connection = connection
        self.words = words

    def json(self) -> JSONDict:
        return {"connection": self.connection, "words": self.words}


class OnlyConnectEpisode(EpisodeVersion):
    connections_round: SixQuestions | None = None
    completions_round: SixQuestions | None = None
    connecting_walls: tuple[ConnectingWall, ConnectingWall] | None = None
    missing_vowels: list[MissingVowelsGroup] | None = None

    @property
    def serialise(self) -> str:
        return json.dumps(
            {
                "connections": (
                    [c.json() for c in self.connections_round] if self.connections_round else None
                ),
                "completions": (
                    [c.json() for c in self.completions_round] if self.completions_round else None
                ),
                "connecting_walls": (
                    [c.json() for c in self.connecting_walls] if self.connecting_walls else None
                ),
                "missing_vowels": (
                    [c.json() for c in self.missing_vowels] if self.missing_vowels else None
                ),
            },
        )
