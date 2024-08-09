# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Generic, TypeVar

import abc
import datetime
import enum
import logging
import pathlib
import sqlite3

from catbox.blob import BlobManager
from catbox.room import Room, RoomOptions
from catbox.user import UserManager

from .episode import EpisodeMeta, EpisodeState, EpisodeVersion

if TYPE_CHECKING:
    from catbox.blob import Blob
    from catbox.user import User


Episode = TypeVar("Episode", bound=EpisodeVersion)


class OptionSupport(enum.Enum):
    NOT_SUPPORTED = None
    OPTIONAL = False
    REQUIRED = True


class GameEngine(abc.ABC, Generic[Episode]):
    """
    GameEngine represents
    """

    @classmethod
    @abc.abstractmethod
    def resources(cls) -> pathlib.Path:
        pass

    _ident: str

    _logger: logging.Logger
    _cursor: sqlite3.Cursor
    _blobs: BlobManager
    _users: UserManager

    def __init__(  # noqa: PLR0913
        self,
        ident: str,
        logger: logging.Logger,
        cursor: sqlite3.Connection,
        blobs: BlobManager,
        users: UserManager,
    ) -> None:
        self._ident = ident
        self._logger = logger
        self._cursor = cursor.cursor()
        self._cursor.row_factory = sqlite3.Row  # type: ignore[assignment]
        self._blobs = blobs
        self._users = users

    @property
    @abc.abstractmethod
    def _episode(self) -> type[Episode]:
        pass

    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @property
    def ident(self) -> str:
        return self._ident

    @property
    @abc.abstractmethod
    def description(self) -> str:
        pass

    def get_episode_meta(self, episode_id: int) -> EpisodeMeta | None:
        self._cursor.execute(
            """SELECT episode_id, user_id, title, description
            FROM Episode WHERE game_engine = ? AND episode_id = ?""",
            (self._ident, episode_id),
        )

        main = self._cursor.fetchone()

        if not main:
            return None

        user = self._get_user(main["user_id"])

        self._cursor.execute(
            """SELECT state, version, version_updated
            FROM EpisodeVersion WHERE episode_id = ?""",
            (episode_id,),
        )

        versions = {
            row["version"]: (row["state"], datetime.datetime.fromisoformat(row["version_updated"]))
            for row in self._cursor.fetchall()
        }

        return EpisodeMeta(
            episode_id,
            self._ident,
            user,
            main["title"],
            main["description"],
            versions,
        )

    def _get_or_create_draft_version(self, episode_id: int) -> int:
        self._cursor.execute(
            "SELECT version FROM EpisodeVersion WHERE episode_id = ? AND state = 'DRAFT'",
            (episode_id,),
        )

        if row := self._cursor.fetchone():
            return int(row["version"])

        self._cursor.execute(
            "SELECT MAX(version) as version FROM EpisodeVersion WHERE episode_id = ?",
            (episode_id,),
        )

        row = self._cursor.fetchone()
        if not isinstance(row["version"], int):
            raise TypeError("No versions for episode")  # noqa: TRY003

        self._cursor.execute(
            """INSERT INTO EpisodeVersion (episode_id, version, data)
            SELECT episode_id, version + 1, data
            FROM EpisodeVersion WHERE episode_id = ? AND version = ?""",
            (episode_id, row["version"]),
        )

        self._cursor.connection.commit()
        return row["version"] + 1

    def get_episode_version(self, episode_id: int, version: int) -> Episode:
        if version == 0:
            version = self._get_or_create_draft_version(episode_id)

        self._cursor.execute(
            """SELECT user_id, title, state, description, data
            FROM Episode NATURAL JOIN EpisodeVersion
            WHERE game_engine = ? AND episode_id = ? AND version = ?""",
            (self._ident, episode_id, version),
        )

        row = self._cursor.fetchone()

        if not row:
            raise ValueError

        user = self._get_user(row["user_id"])

        episode = self._episode(
            episode_id,
            self._ident,
            user,
            row["title"],
            row["description"],
            version,
            EpisodeState(row["state"]),
        )
        self._load_data(episode, row["data"])
        return episode

    @abc.abstractmethod
    def _load_data(self, episode: Episode, data: str) -> None:
        pass

    def _get_user(self, user_id: int) -> User:
        if user := self._users.get(user_id):
            return user
        raise RuntimeError

    def list_episodes(self, state: EpisodeState) -> Generator[Episode, None, None]:
        self._cursor.execute(
            """SELECT episode_id, MAX(version) as version, user_id, title, description, data
            FROM Episode NATURAL JOIN EpisodeVersion
            WHERE game_engine = ? AND state = ? GROUP BY episode_id""",
            (self._ident, state),
        )

        for row in self._cursor:
            user = self._get_user(row["user_id"])
            episode = self._episode(
                row["episode_id"],
                self._ident,
                user,
                row["title"],
                row["description"],
                row["version"],
                state,
            )
            self._load_data(episode, row["data"])
            yield episode

    def list_user_episodes(self, user: User) -> list[EpisodeMeta]:
        self._cursor.execute(
            """
            SELECT episode_id, user_id, title, description, state, version, version_updated
            FROM Episode NATURAL LEFT JOIN EpisodeVersion
            WHERE game_engine = ? AND user_id = ?
            """,
            (self._ident, user.user_id),
        )

        metadata: dict[int, tuple[User, str, str]] = {}
        versions: dict[int, dict[int, tuple[EpisodeState, datetime.datetime]]] = {}

        row: sqlite3.Row
        for row in self._cursor:
            if row["episode_id"] not in metadata:
                user = self._get_user(row["user_id"])
                metadata[row["episode_id"]] = (user, row["title"], row["description"])
                versions[row["episode_id"]] = {}

            versions[row["episode_id"]][row["version"]] = (
                EpisodeState(row["state"]),
                datetime.datetime.fromisoformat(row["version_updated"]),
            )

        return [
            EpisodeMeta(eid, self._ident, user, title, description, versions[eid])
            for eid, (user, title, description) in metadata.items()
        ]

    @property
    @abc.abstractmethod
    def scoring_mode(self) -> OptionSupport:
        pass

    @property
    @abc.abstractmethod
    def max_teams(self) -> int:
        """
        Maximum number of scoring teams (excluding the audience).
        """

    @property
    @abc.abstractmethod
    def supports_audience(self) -> OptionSupport:
        """
        Whether there is support for
        """

    @abc.abstractmethod
    def play_episode(self, episode: Episode, options: RoomOptions) -> Room:
        pass

    @property
    def cms_enabled(self) -> bool:
        return False

    def create_episode(self, user: User) -> EpisodeMeta:
        if not self.cms_enabled:
            raise NotImplementedError

        title = f"{user.user_name}'s Episode"

        self._cursor.execute(
            "INSERT INTO Episode (game_engine, user_id, title, description) VALUES (?, ?, ?, ?)",
            (self._ident, user.user_id, title, ""),
        )

        new_episode_id = self._cursor.lastrowid

        if not new_episode_id:
            raise ValueError

        self._cursor.execute(
            "INSERT INTO EpisodeVersion (episode_id, version, data) VALUES (?, ?, ?)",
            (new_episode_id, 1, ""),
        )
        self._cursor.connection.commit()

        return EpisodeMeta(new_episode_id, self._ident, user, title, "", {})

    @abc.abstractmethod
    def edit_episode(self, episode: Episode) -> Room:
        pass

    @abc.abstractmethod
    def view_episode(self, episode: Episode) -> Room:
        pass

    def save(self, episode: Episode) -> None:
        self._cursor.execute(
            """UPDATE Episode SET title = ?, description = ?
            WHERE game_engine = ? and episode_id = ?""",
            (episode.title, episode.description, self._ident, episode.id),
        )
        self._cursor.execute(
            """UPDATE EpisodeVersion SET data = ?, version_updated = CURRENT_TIMESTAMP
            WHERE episode_id = ? AND version = ? AND state = 'DRAFT'""",
            (str(episode.serialise), episode.id, episode.version),
        )
        self._cursor.connection.commit()

    def save_state(self, episode: Episode, state: EpisodeState) -> None:
        self._cursor.execute(
            """UPDATE EpisodeVersion SET state = ?, version_updated = CURRENT_TIMESTAMP
                    WHERE episode_id = ? AND version = ? AND state = ?""",
            (state, episode.id, episode.version, episode.state),
        )
        episode._status = state  # noqa: SLF001 access better than trying to replace the object.

        if state not in [EpisodeState.DISCARDED, EpisodeState.SUPERSEDED]:
            # Ensure state uniqueness, by moving others to Discard / Superseded
            state = (
                EpisodeState.SUPERSEDED
                if state == EpisodeState.PUBLISHED
                else EpisodeState.DISCARDED
            )
            self._cursor.execute(
                """UPDATE EpisodeVersion SET state = ?
                 WHERE episode_id = ? AND state = ? AND version != ?""",
                (state, episode.id, episode.state, episode.version),
            )

        self._cursor.connection.commit()

    def blob_for_id(self, blob_id: str | dict[str, str] | None) -> Blob | None:
        if not blob_id:
            return None

        if isinstance(blob_id, dict):
            return self.blob_for_id(blob_id.get("blob_id"))

        return self._blobs.blob(blob_id)
