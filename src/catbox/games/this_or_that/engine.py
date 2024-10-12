# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import json
import pathlib
from uuid import uuid4

from catbox.engine import EpisodeVersion, GameEngine, JSONDict, OptionSupport
from catbox.room import Room, RoomOptions

from .cms import ThisOrThatEditRoom, ThisOrThatPreviewRoom
from .play import ThisOrThatRoom
from .question import Answer, ThisOrThatQuestion


class ThisOrThatEpisode(EpisodeVersion):
    this_category: str
    that_category: str
    questions: list[ThisOrThatQuestion]

    def json(self) -> JSONDict:
        return {
            "this": self.this_category,
            "that": self.that_category,
            "questions": [q.json() for q in self.questions],  # type: ignore[dict-item]
        }

    @property
    def serialise(self) -> str:
        return json.dumps(self.json())

    @property
    def both_possible(self) -> bool:
        return any(q.is_this and q.is_that for q in self.questions)

    @property
    def neither_possible(self) -> bool:
        return any(not (q.is_this or q.is_that) for q in self.questions)

    def __len__(self) -> int:
        return sum(1 for q in self.questions if q.is_valid)

    @property
    def full_description(self) -> str:
        both = self.both_possible
        neither = self.neither_possible
        count = str(len(self))

        if not (both or neither):
            rules = (
                f"{count!s} this-or-that questions between "
                f"'{self.this_category}' or '{self.that_category}'."
            )
        else:
            rules = (
                count
                + f" questions, with '{self.this_category}', '{self.that_category}'"
                + (", or both" if both else "")
                + (", or neither" if neither else "")
            )

        return super().full_description + "\n" + rules

    def answer_text(self, answer: Answer) -> str:
        if answer == Answer.THIS:
            return self.this_category
        if answer == Answer.THAT:
            return self.that_category
        if answer == Answer.BOTH:
            return "Both"
        if answer == Answer.NEITHER:
            return "Neither"
        raise ValueError


class ThisOrThisEngine(GameEngine[ThisOrThatEpisode]):
    @classmethod
    def resources(cls) -> pathlib.Path:
        return (pathlib.Path(__file__).parent / "resources").resolve()

    @property
    def _episode(self) -> type[ThisOrThatEpisode]:
        return ThisOrThatEpisode

    @property
    def name(self) -> str:
        return "This...or That?"

    @property
    def description(self) -> str:
        return "Guess which items belong to one of two known categories"

    @property
    def cms_enabled(self) -> bool:
        return True

    @property
    def scoring_mode(self) -> OptionSupport:
        return OptionSupport.OPTIONAL

    @property
    def max_teams(self) -> int:
        return 4

    @property
    def supports_audience(self) -> OptionSupport:
        return OptionSupport.OPTIONAL

    def _load_data(self, episode: ThisOrThatEpisode, data: str) -> None:
        try:
            contents = json.loads(data)
        except json.JSONDecodeError:
            contents = {}

        episode.this_category = contents.get("this", "")
        episode.that_category = contents.get("that", "")
        episode.questions = []

        for question in contents.get("questions", []):
            episode.questions.append(ThisOrThatQuestion(self, **question))

        if not episode.questions:
            episode.questions.append(ThisOrThatQuestion(self, uuid=uuid4().hex))

    def play_episode(self, episode: EpisodeVersion, options: RoomOptions) -> Room:
        if not isinstance(episode, ThisOrThatEpisode):
            raise TypeError

        return ThisOrThatRoom(self._logger.getChild(f"play-{episode.id}"), options, episode)

    def edit_episode(self, episode: EpisodeVersion) -> Room:
        if not isinstance(episode, ThisOrThatEpisode):
            raise TypeError

        return ThisOrThatEditRoom(self._logger.getChild(f"edit-{episode.id}"), self, episode)

    def view_episode(self, episode: EpisodeVersion) -> Room:
        if not isinstance(episode, ThisOrThatEpisode):
            raise TypeError

        return ThisOrThatPreviewRoom(self._logger.getChild(f"view-{episode.id}"), episode)
