# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import dataclasses
import sqlite3

import lru


@dataclasses.dataclass
class User:
    user_id: int
    user_name: str
    twitch_id: int
    is_mod: bool

    def json(self) -> dict[str, str | bool]:
        return {
            "user_id": str(self.user_id),
            "user_name": self.user_name,
            "is_mod": self.is_mod,
        }


class UserManager:
    _db: sqlite3.Connection
    _cursor: sqlite3.Cursor
    _cache: lru.LRU[int, User]

    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db
        self._cursor = self._db.cursor()
        self._cursor.row_factory = sqlite3.Row  # type: ignore[assignment]
        self._cache = lru.LRU(1024)

    def get(self, user_id: int) -> User | None:
        if user_id not in self._cache:
            self._cursor.execute("SELECT * FROM User WHERE user_id = ?", (user_id,))

            if not (row := self._cursor.fetchone()):
                return None

            self._cache[user_id] = User(**row)

        return self._cache[user_id]

    def for_twitch(self, twitch_id: int, display_name: str) -> User | None:
        self._cursor.execute("SELECT * FROM User WHERE twitch_id = ?", (twitch_id,))

        if row := self._cursor.fetchone():
            return User(**row)

        self._cursor.execute(
            "INSERT INTO User (twitch_id, user_name) VALUES (?, ?)",
            (twitch_id, display_name),
        )

        if not (user_id := self._cursor.lastrowid):
            raise RuntimeError

        return self.get(user_id)
