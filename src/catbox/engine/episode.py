# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Iterator

import abc
import datetime
import enum

from catbox.user import User


class EpisodeState(enum.StrEnum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "REVIEW"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "UNPUBLISHED"
    DISCARDED = "DISCARDED"

    @classmethod
    def _missing_(cls, value: object) -> EpisodeState | None:
        value = str(value).lower()
        for member in cls:
            if member.value == value:
                return member
        return None


class Episode(abc.ABC):
    """
    A GameEpisode is a
    """

    _engine: str
    _author: User
    _episode_id: int
    _title: str
    _description: str

    __slots__ = ("_engine", "_author", "_episode_id", "_title", "_description")

    def __init__(  # noqa: PLR0913 many valued data class
        self,
        episode_id: int,
        engine: str,
        author: User,
        title: str,
        description: str,
    ) -> None:
        self._engine = engine
        self._author = author
        self._episode_id = episode_id
        self._title = title
        self._description = description

    @property
    def id(self) -> int:
        return self._episode_id

    @property
    def author_id(self) -> int:
        return self._author.user_id

    @property
    def author(self) -> str:
        return self._author.user_name

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, title: str) -> None:
        self._title = title

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, description: str) -> None:
        self._description = description

    @property
    def full_description(self) -> str:
        return self.description

    @property
    def engine_ident(self) -> str:
        return self._engine


class EpisodeVersion(Episode):
    _version: int
    _status: EpisodeState

    def __init__(  # noqa: PLR0913 many valued data class
        self,
        episode_id: int,
        engine: str,
        author: User,
        title: str,
        description: str,
        version: int,
        state: EpisodeState,
    ) -> None:
        super().__init__(episode_id, engine, author, title, description)
        self._status = state
        self._version = version

    @property
    def version(self) -> int:
        return self._version

    @property
    def state(self) -> EpisodeState:
        return self._status

    @property
    @abc.abstractmethod
    def serialise(self) -> str:
        pass


class EpisodeMeta(Episode):
    _current_versions: dict[EpisodeState, int | None]
    _all_versions: dict[int, tuple[EpisodeState, datetime.datetime]]

    def __init__(  # noqa: PLR0913 many valued data class
        self,
        episode_id: int,
        engine: str,
        author: User,
        title: str,
        description: str,
        versions: dict[int, tuple[EpisodeState, datetime.datetime]],
    ) -> None:
        super().__init__(episode_id, engine, author, title, description)

        self._all_versions = versions.copy()
        self._current_versions = {state: None for state in EpisodeState}

        for version, (state, _) in versions.items():
            self._current_versions[state] = max(version, self._current_versions[state] or 0)

    def __len__(self) -> int:
        return len(self._all_versions)

    def __iter__(self) -> Iterator[tuple[int, tuple[EpisodeState, datetime.datetime]]]:
        return iter(self._all_versions.items())

    def version(self, state: EpisodeState) -> int | None:
        return self._current_versions[state]
