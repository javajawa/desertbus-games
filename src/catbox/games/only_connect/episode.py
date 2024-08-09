# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import json

from catbox.engine import EpisodeVersion, JSONDict

MAX_TEAMS = 2
SLOTS_PER_CONNECTION = 4
QUESTIONS_PER_ROUND = 6


class OnlyConnectQuestion:
    @classmethod
    def default(cls) -> JSONDict:
        return {
            "question_type": "text",
            "connection": "",
            "details": "",
            "elements": [""] * SLOTS_PER_CONNECTION,
        }

    connection: str
    details: str
    elements: list[str]

    def __init__(
        self,
        question_type: str,
        connection: str,
        details: str,
        elements: tuple[str, str, str, str],
    ) -> None:
        if question_type != "text":
            raise ValueError

        self.connection = connection
        self.details = details
        self.elements = list(elements)

    def json(self) -> JSONDict:
        return {
            "question_type": "text",
            "connection": self.connection,
            "details": self.details,
            "elements": list(self.elements),
        }

    def __repr__(self) -> str:
        return f"<OnlyConnectQuestion({self.connection}, {self.elements})>"


class SixQuestions(
    tuple[
        OnlyConnectQuestion,
        OnlyConnectQuestion,
        OnlyConnectQuestion,
        OnlyConnectQuestion,
        OnlyConnectQuestion,
        OnlyConnectQuestion,
    ],
):
    __slots__ = ()

    @classmethod
    def default(cls) -> SixQuestions:
        defaults = OnlyConnectQuestion.default()

        elements = defaults.get("elements", [])
        if not isinstance(elements, list):
            raise TypeError

        return SixQuestions(
            OnlyConnectQuestion(
                question_type="text",
                connection=str(defaults["connection"]),
                details=str(defaults["details"]),
                elements=(
                    str(elements[0]),
                    str(elements[1]),
                    str(elements[2]),
                    str(elements[3]),
                ),
            )
            for _ in range(QUESTIONS_PER_ROUND)
        )


class ConnectingWall(
    tuple[
        OnlyConnectQuestion,
        OnlyConnectQuestion,
        OnlyConnectQuestion,
        OnlyConnectQuestion,
    ],
):
    @classmethod
    def default(cls) -> ConnectingWall:
        defaults = OnlyConnectQuestion.default()

        elements = defaults.get("elements", [])
        if not isinstance(elements, list):
            raise TypeError

        return ConnectingWall(
            OnlyConnectQuestion(
                question_type="text",
                connection=str(defaults["connection"]),
                details=str(defaults["details"]),
                elements=(
                    str(elements[0]),
                    str(elements[1]),
                    str(elements[2]),
                    str(elements[3]),
                ),
            )
            for _ in range(SLOTS_PER_CONNECTION)
        )

    __slots__ = ()

    @property
    def clues(self) -> tuple[str, ...]:
        return tuple(sum((group.elements for group in self), ()))

    def json(self) -> list[JSONDict]:
        return [section.json() for section in self]


class MissingVowelsGroup:
    connection: str
    words: list[str]

    def __init__(self, connection: str, words: list[str]) -> None:
        self.connection = connection
        self.words = words

    def json(self) -> JSONDict:
        return {"connection": self.connection, "words": self.words}  # type: ignore[dict-item]


class OnlyConnectEpisode(EpisodeVersion):
    connections_round: SixQuestions | None = None
    completions_round: SixQuestions | None = None
    connecting_walls: tuple[ConnectingWall, ConnectingWall] | None = None
    missing_vowels: list[MissingVowelsGroup] | None = None

    def json(self) -> JSONDict:
        return {
            "connections": (
                [c.json() for c in self.connections_round] if self.connections_round else None
            ),
            "completions": (
                [c.json() for c in self.completions_round] if self.completions_round else None
            ),
            "connecting_walls": (
                [c.json() for c in self.connecting_walls]  # type: ignore[misc]
                if self.connecting_walls
                else None
            ),
            "missing_vowels": (
                [c.json() for c in self.missing_vowels] if self.missing_vowels else None
            ),
        }

    @property
    def serialise(self) -> str:
        return json.dumps(self.json())
