# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Iterator

import dataclasses
import datetime
import sqlite3

import lru


@dataclasses.dataclass
class User:
    _manager: UserManager
    user_id: int
    user_name: str
    twitch_id: int
    is_mod: bool

    def json(self) -> dict[str, str | int | bool]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "is_mod": self.is_mod,
            "unread_notifications": self.unread_count,
        }

    @property
    def unread_count(self) -> int:
        return self._manager.unread_notification_count(self.user_id)

    def notifications(self) -> list[Notification]:
        return list(self._manager.notifications(self))

    def send_notification(self, message: str) -> None:
        self._manager.send_notification(self.user_id, message)

    def mark_notifications_as_read(self) -> None:
        self._manager.mark_notifications_as_read(self.user_id)


@dataclasses.dataclass
class Notification:
    user: User
    date: datetime.datetime
    is_read: bool
    data: str

    def json(self) -> dict[str, str | bool]:
        return {
            "date": self.date.isoformat(),
            "is_read": self.is_read,
            "data": self.data,
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

            self._cache[user_id] = User(self, **row)

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

    def notifications(self, user: User) -> Iterator[Notification]:
        self._cursor.execute("SELECT * FROM Notification WHERE user_id = ?", (user.user_id,))

        for row in self._cursor.fetchall():
            yield Notification(
                user,
                datetime.datetime.fromisoformat(row["created_at"]),
                bool(row["is_read"]),
                row["data"],
            )

    def unread_notification_count(self, user_id: int) -> int:
        self._cursor.execute(
            "SELECT COUNT(0) FROM Notification WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )

        return int(self._cursor.fetchone()[0])

    def send_notification(self, user_id: int, message: str) -> None:
        self._cursor.execute(
            "INSERT INTO Notification (user_id, data) VALUES (?, ?)",
            (user_id, message),
        )

    def mark_notifications_as_read(self, user_id: int) -> None:
        self._cursor.execute(
            "UPDATE Notification SET is_read = 1 WHERE user_id = ?",
            (user_id,),
        )
