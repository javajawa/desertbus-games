# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import dataclasses
import enum
from uuid import uuid4

from catbox.blob import Blob

if TYPE_CHECKING:
    from catbox.engine import JSONDict

    from .engine import ThisOrThisEngine


class Answer(enum.StrEnum):
    NEITHER = "neither"
    THIS = "this"
    THAT = "that"
    BOTH = "both"


@dataclasses.dataclass
class ThisOrThatQuestion:
    @classmethod
    def new(cls, engine: ThisOrThisEngine) -> ThisOrThatQuestion:
        return cls(
            engine,
            uuid=uuid4().hex,
            question_text=None,
            question_media=None,
            is_this=False,
            is_that=False,
            answer_text=None,
            answer_media=None,
        )

    uuid: str
    question_text: str | None
    question_media: Blob | None
    is_this: bool
    is_that: bool
    answer_text: str | None
    answer_media: Blob | None

    def __init__(  # noqa: PLR0913 many valued data class
        self,
        engine: ThisOrThisEngine,
        *,
        uuid: str,
        question_text: str | None = None,
        question_media: str | None = None,
        is_this: bool = False,
        is_that: bool = False,
        answer_text: str | None = None,
        answer_media: str | None = None,
    ) -> None:
        self.uuid = uuid
        self.question_text = question_text
        self.question_media = engine.blob_for_id(question_media)
        self.is_this = is_this
        self.is_that = is_that
        self.answer_text = answer_text
        self.answer_media = engine.blob_for_id(answer_media)

    @property
    def is_valid(self) -> bool:
        return self.question_text is not None or self.question_media is not None

    @property
    def answer(self) -> Answer:
        if self.is_this:
            return Answer.BOTH if self.is_that else Answer.THAT
        if self.is_that:
            return Answer.THAT

        return Answer.NEITHER

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.uuid == other

        if not isinstance(other, ThisOrThatQuestion):
            return False

        return other.uuid == self.uuid

    def json(self) -> JSONDict:
        return {
            "uuid": self.uuid,
            "question_text": self.question_text,
            "question_media": self.question_media.json() if self.question_media else None,
            "is_this": self.is_this,
            "is_that": self.is_that,
            "answer_text": self.answer_text,
            "answer_media": self.answer_media.json() if self.answer_media else None,
        }
