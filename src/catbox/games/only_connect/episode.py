# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Iterable, Sequence
from typing import Literal

import json
import random
import re

from catbox.blob import Blob
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

    question_type: str
    connection: str
    details: str
    elements: list[str | Blob]

    def __init__(
        self,
        question_type: str,
        connection: str,
        details: str,
        elements: Sequence[str | Blob],
    ) -> None:
        if question_type not in {"text", "media"}:
            raise ValueError
        if len(elements) != SLOTS_PER_CONNECTION:
            raise ValueError

        self.question_type = question_type
        self.connection = connection
        self.details = details
        self.elements = list(elements)

    def json(self) -> JSONDict:
        elements = [e.json() if isinstance(e, Blob) else e for e in self.elements]
        return {
            "question_type": self.question_type,
            "connection": self.connection,
            "details": self.details,
            "elements": elements,  # type: ignore[dict-item]
        }

    @property
    def valid(self) -> bool:
        return (
            bool(self.connection)
            and (len(self.elements) == SLOTS_PER_CONNECTION)
            and all(self.elements)
        )

    def __repr__(self) -> str:
        return f"<OnlyConnectQuestion({self.connection}, {self.elements})>"


class OnlyConnectTextQuestion(OnlyConnectQuestion):
    elements: list[str]  # type: ignore[assignment]

    def __init__(
        self,
        question_type: str,
        connection: str,
        details: str,
        elements: Sequence[str],
    ) -> None:
        if question_type != "text":
            raise ValueError

        super().__init__("text", connection, details, elements)


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

        elements: list[str] = defaults.get("elements", [])  # type: ignore[assignment]
        if not isinstance(elements, list):
            raise TypeError

        return SixQuestions(
            OnlyConnectQuestion(
                question_type=str(defaults["question_type"]),
                connection=str(defaults["connection"]),
                details=str(defaults["details"]),
                elements=elements,
            )
            for _ in range(QUESTIONS_PER_ROUND)
        )

    @property
    def valid(self) -> bool:
        return all(question.valid for question in self)


class ConnectingWall(
    tuple[
        OnlyConnectTextQuestion,
        OnlyConnectTextQuestion,
        OnlyConnectTextQuestion,
        OnlyConnectTextQuestion,
    ],
):
    @classmethod
    def default(cls) -> ConnectingWall:
        defaults = OnlyConnectQuestion.default()

        elements = defaults.get("elements", [])
        if not isinstance(elements, list):
            raise TypeError

        return ConnectingWall(
            OnlyConnectTextQuestion(
                question_type=str(defaults["question_type"]),
                connection=str(defaults["connection"]),
                details=str(defaults["details"]),
                elements=elements,
            )
            for _ in range(SLOTS_PER_CONNECTION)
        )

    __slots__ = ()

    @property
    def clues(self) -> tuple[str, ...]:
        return tuple(sum((group.elements for group in self), []))  # noqa: RUF017 -- n^2 is fine...

    @property
    def valid(self) -> bool:
        return all(group.valid for group in self)

    def json(self) -> list[JSONDict]:
        return [section.json() for section in self]


VOWELS_AND_SPACES = re.compile(r"[ AEIOU]")


class MissingVowelsGroup:
    @staticmethod
    def check_valid(prompt: str, answer: str) -> bool:
        return prompt.upper().replace(" ", "") == VOWELS_AND_SPACES.sub("", answer.upper())

    @staticmethod
    def generate_prompt(answer: str) -> str:
        prompt = VOWELS_AND_SPACES.sub("", answer.upper())

        x = 0
        while (x := x + random.randint(2, 6)) < len(prompt):  # noqa: S311 non-security rand
            prompt = prompt[:x] + " " + prompt[x:]

        return prompt.strip()

    @staticmethod
    def regexp(answer: str) -> str:
        return "^" + " ?".join(VOWELS_AND_SPACES.sub("", answer.upper())) + "$"

    connection: str
    words: list[tuple[str, str] | None]

    def __init__(self, connection: str, words: list[list[str]]) -> None:
        self.connection = connection
        self.words = [(word[1], word[2]) for word in words]

    def json(self) -> JSONDict:
        return {
            "connection": self.connection,
            "words": list(self.pairs),  # type: ignore[dict-item]
        }

    @property
    def valid(self) -> bool:
        return any(self.check_valid(x[1], x[0]) for x in self.words if x)

    @property
    def pairs(self) -> Iterable[tuple[int, str, str, bool]]:
        return (
            (i, x[0], x[1], self.check_valid(x[1], x[0])) for i, x in enumerate(self.words) if x
        )

    @property
    def valid_pairs(self) -> Iterable[tuple[str, str]]:
        return (x for x in self.words if x and self.check_valid(x[1], x[0]))


class OnlyConnectEpisode(EpisodeVersion):
    connections_round: SixQuestions | None = None
    completions_round: SixQuestions | None = None
    connecting_walls: tuple[ConnectingWall, ConnectingWall] | None = None
    missing_vowels: list[MissingVowelsGroup | None] | None = None

    def json(self) -> JSONDict:
        return {
            "title": self.title,
            "description": self.description,
            "connections": (  # type: ignore[dict-item]
                [c.json() for c in self.connections_round] if self.connections_round else None
            ),
            "completions": (  # type: ignore[dict-item]
                [c.json() for c in self.completions_round] if self.completions_round else None
            ),
            "connecting_walls": (  # type: ignore[dict-item]
                [c.json() for c in self.connecting_walls] if self.connecting_walls else None
            ),
            "missing_vowels": (  # type: ignore[dict-item]
                [c.json() if c else None for c in self.missing_vowels]
                if self.missing_vowels is not None
                else None
            ),
        }

    @property
    def serialise(self) -> str:
        return json.dumps(self.json())

    @property
    def has_connections_round(self) -> bool:
        return self.connections_round is not None and self.connections_round.valid

    @property
    def has_completions_round(self) -> bool:
        return self.completions_round is not None and self.completions_round.valid

    @property
    def has_missing_vowels(self) -> bool:
        return self.missing_vowels is not None and any(x and x.valid for x in self.missing_vowels)

    def has_connecting_walls(self, teams: Literal[1, 2]) -> bool:
        if not self.connecting_walls or not self.connecting_walls[0].valid:
            return False

        return (teams == 1) or self.connecting_walls[1].valid
