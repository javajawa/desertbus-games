from __future__ import annotations

from typing import Any

import asyncio
import dataclasses
import enum
import pathlib
import random
import sqlite3
import string

from db_games.abc import Game, GameEngine, GameInfo, _IdMixin
from db_games.dom import NodeList, Element


@dataclasses.dataclass
class ThisOrThatGame(GameInfo):
    this: str
    that: str
    info: str

    questions: list[Question]
    both_possible: bool
    none_possible: bool

    def __init__(
        self,
        categories: tuple[str, str],
        description: str,
        credit: str,
        questions: list[Question],
    ) -> None:
        self.this, self.that = categories
        self.info = description
        self.questions = questions
        self.both_possible = any(x.is_this and x.is_that for x in questions)
        self.none_possible = any(not x.is_this and not x.is_that for x in questions)

        summary = (
            f"{len(self.questions)} questions"
            f"{', default rules' if not self.both_possible and not self.none_possible else ''}"
            f"{', both possible' if self.both_possible else ''}"
            f"{', none possible' if self.none_possible else ''}"
        )

        super().__init__(
            f"{self.this} or {self.that}?", credit, summary, list(range(4))
        )


class Option(enum.IntEnum):
    NONE = 0
    THIS = 1
    THAT = 2
    BOTH = 3


@dataclasses.dataclass
class Question(_IdMixin):
    prompt: str
    image: str
    info: str

    is_this: bool
    is_that: bool


class ThisOrThatInstance(Game):
    game: ThisOrThatGame

    scores: list[int]
    question_index: int = -1
    votes: dict[str, Option] = {}
    revealed: bool = False

    admin_path: str

    def __init__(self, game: ThisOrThatGame, teams: int) -> None:
        super().__init__()

        self.game = game
        self.scores = [0] * teams
        self.admin_path = "".join(random.choices(string.ascii_uppercase, k=4))  # nosec

    @property
    def state(self) -> dict[str, Any]:
        question = (
            dataclasses.asdict(self.game.questions[self.question_index])
            if self.game.questions
            and 0 <= self.question_index < len(self.game.questions)
            else None
        )

        if question and not self.revealed:
            question = {"prompt": question["prompt"], "image": question["image"]}

        return {
            "this": self.game.this,
            "that": self.game.that,
            "credits": self.game.credit,
            "description": self.game.description,
            "both_possible": self.game.both_possible,
            "none_possible": self.game.none_possible,
            "question": question,
        }

    def path(self, name: str) -> pathlib.Path:
        _map = {self.admin_path: "gm.html", "": "audience.html"}

        return super().path(_map.get(name, name))

    def redirect(self) -> str:
        return self.admin_path


class ThisOrThat(GameEngine):
    _db: sqlite3.Cursor
    _cache: dict[str, ThisOrThatGame]
    _lock: asyncio.Lock

    def __init__(self, db: sqlite3.Connection) -> None:
        cur = db.cursor()

        with (pathlib.Path(__file__).parent / "init.sql").open(
            "r", encoding="utf-8"
        ) as script:
            cur.executescript(script.read())

        self._db = db.cursor()
        self._cache = {}
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "This or That"

    @property
    def description(self) -> str:
        return "Guess which items belong to one of two known categories"

    def path(self, name: str) -> pathlib.Path:
        return pathlib.Path(__file__).parent / "resources" / name

    async def available(self) -> dict[str, ThisOrThatGame]:
        if not self._cache:
            await self._load_quizzes()

        return self._cache

    async def create(self, ident: str) -> Game:
        if not self._cache:
            await self._load_quizzes()
        if ident not in self._cache:
            raise KeyError("No known game with ID " + ident)

        return ThisOrThatInstance(self._cache[ident], 1)

    async def audit(self, engine_slug: str, ident: str) -> NodeList:
        if not self._cache:
            await self._load_quizzes()

        if ident not in self._cache:
            raise KeyError("No known game with ID " + ident + str(self._cache))

        return NodeList(
            Element("link", rel="stylesheet", href=f"/{engine_slug}/this-or-that.css"),
            Element("p", "Meow!", class_="lozenge")
        )

    async def _load_quizzes(self) -> None:
        async with self._lock:
            self._db.execute("SELECT * FROM ThisOrThatGame")
            games = self._db.fetchall()

            self._db.execute("SELECT * FROM ThisOrThatQuestion")
            questions = self._db.fetchall()

        self._cache = {
            str(game[0]): ThisOrThatGame(
                (game[1], game[2]),
                game[3],
                game[4],
                [
                    Question(row[1], row[2], row[3], row[4], bool(row[5]), bool(row[6]))
                    for row in questions
                    if row[0] == game[0]
                ],
            )
            for game in games
        }
