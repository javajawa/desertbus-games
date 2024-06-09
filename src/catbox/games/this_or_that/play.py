# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Coroutine, Iterable, Mapping
from typing import TYPE_CHECKING, Any

import abc
import asyncio
import enum
import logging
import uuid

import yarl

from catbox.engine import JSONDict
from catbox.room import Endpoint, Room, RoomOptions, Socket, command
from catbox.site.state import CatBoxContext
from catbox.static import DocResponse
from dom import Document, Element
from webapp import Request, ResponseProtocol

from .question import Answer as Vote
from .question import ThisOrThatQuestion

if TYPE_CHECKING:
    from .engine import ThisOrThatEpisode


class GameState(str, enum.Enum):
    GAME_STARTING = "pre-game"
    QUESTION = "question"
    ANSWER = "answer"
    POST_GAME = "post-game"


class Audience:
    room: str
    score: float
    vote_record: dict[str, Vote]
    members: set[str]

    def __init__(self) -> None:
        self.score = 0.0
        self.vote_record = {}
        self.members = set()
        self.room = ""

    def json(self) -> JSONDict:
        return {
            "room": self.room,
            "score": self.score,
            "voted": len(self.vote_record),
            "count": len(self.members),
        }


class Team:
    id: str
    name: str
    score: int = 0
    vote: Vote | None = None

    def __init__(self, name: str) -> None:
        self.id = uuid.uuid4().hex
        self.name = name
        self.score = 0
        self.vote = None

    def public(self) -> JSONDict:
        return {
            "id": self.id,
            "name": self.name,
            "score": self.score,
            "voted": self.vote is not None,
        }

    def full(self) -> JSONDict:
        return {
            "id": self.id,
            "name": self.name,
            "score": self.score,
            "voted": str(self.vote) if self.vote else None,
        }


class ThisOrThatRoom(Room):
    endpoints: Mapping[str, ThisOrThatEndpoint]
    episode: ThisOrThatEpisode
    state: GameState
    question_index: int

    teams: list[Team] | None = None
    audience: Audience | None = None
    next_audience_sync: bool = False

    def __init__(
        self,
        logger: logging.Logger,
        options: RoomOptions,
        episode: ThisOrThatEpisode,
    ) -> None:
        self.loop = asyncio.get_running_loop()
        self.episode = episode
        self.state = GameState.GAME_STARTING
        self.question_index = -1  # Before the first question.

        endpoints: dict[str, ThisOrThatEndpoint] = {}

        if options.scoring:
            endpoints["score"] = ThisOrThatScoreOverlay(self)
            self.teams = [Team(team) for team in options.teams]
            for team in self.teams:
                endpoints["team " + team.name] = ThisOrThatPlayer(self, team)

        if options.audience:
            self.audience = Audience()
            endpoints["audience"] = ThisOrThatAudience(self, self.audience)

        super().__init__(
            logger,
            gm=ThisOrThatGameManager(self),
            screen=ThisOrThatFullScreen(self),
            **endpoints,
        )
        asyncio.get_running_loop().create_task(self.audience_pinger(), name="audience-ping")

    @property
    def question(self) -> ThisOrThatQuestion | None:
        if self.state in {GameState.GAME_STARTING, GameState.POST_GAME}:
            return None

        return self.episode.questions[self.question_index]

    def __str__(self) -> str:
        return str(self.default_endpoint.room_code) + ": " + self.episode.title

    @property
    def default_endpoint(self) -> Endpoint:
        return self.endpoints["screen"]

    @property
    def starting_endpoint(self) -> Endpoint:
        return self.endpoints["gm"]

    async def _gather(
        self,
        coroutines: Iterable[Coroutine[Any, Any, list[Exception] | Exception | None]],
        msg: str,
        *args: Any,
    ) -> None:
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                for exc in result:
                    self.logger.error(msg, *args, exc_info=exc, extra={"room": self})
            elif isinstance(result, Exception):
                self.logger.error(msg, *args, exc_info=result, extra={"room": self})

    async def vote(self, team_id: str, vote: Vote | None) -> None:
        if not self.teams:
            self.logger.error("Attempting to vote with no scoring??", extra={"room": self})
            return

        team = next((team for team in self.teams if team.id == team_id), None)

        if not team:
            self.logger.error(
                "Attempted to vote for unknown team %s",
                team_id,
                extra={"room": self},
            )
            return

        team.vote = vote

        await self._gather(
            (endpoint.on_vote_change() for endpoint in self.endpoints.values()),
            "Error updating after vote from %s",
            team.name,
        )

    async def next_question(self) -> None:
        if self.state not in {GameState.GAME_STARTING, GameState.ANSWER}:
            self.logger.error(
                "Attempting to move to next question from %s",
                self.state,
                extra={"room": self},
            )
            return

        self.question_index += 1
        if self.question_index == len(self.episode.questions):
            self.state = GameState.POST_GAME
        else:
            self.state = GameState.QUESTION

            # Reset the votes.
            if self.teams:
                for team in self.teams:
                    team.vote = None

            self.logger.info("Moved to question %d", self.question_index, extra={"room": self})

        await self._gather(
            (endpoint.on_state_change() for endpoint in self.endpoints.values()),
            "Error moving to question %d",
            self.question_index,
        )

    async def reveal_answer(self) -> None:
        if self.state != GameState.QUESTION:
            self.logger.error(
                "Attempting to reveal in state %s",
                self.state,
                extra={"room": self},
            )
            return

        question = self.question
        correct = question.answer if question else None
        if self.teams:
            for team in self.teams:
                if team.vote == correct:
                    team.score += 1
        if self.audience and self.audience.vote_record:
            self.audience.score += sum(
                1 for v in self.audience.vote_record.values() if v == correct
            ) / len(self.audience.vote_record)
            self.audience.vote_record.clear()

        self.state = GameState.ANSWER
        self.logger.info("Revealed answer for %d", self.question_index, extra={"room": self})

        await self._gather(
            (endpoint.on_state_change() for endpoint in self.endpoints.values()),
            "Error revealing question %d",
            self.question_index,
        )

    def queue_audience_update(self) -> None:
        if not self.audience:
            return

        self.next_audience_sync = True

    async def audience_pinger(self) -> None:
        while not self._stopped:
            await asyncio.sleep(0.5)

            if not self.next_audience_sync:
                continue

            self.next_audience_sync = False
            self.logger.info("Sending out audience changes", extra={"room": self})
            await self._gather(
                (endpoint.on_state_change() for endpoint in self.endpoints.values()),
                "Error during audience update",
            )


class ThisOrThatEndpoint(Endpoint, abc.ABC):
    room: ThisOrThatRoom

    async def on_state_change(self) -> list[Exception]:
        return await self._fanout(self._state_representation(), log=False)

    def _state_representation(self, *, full_teams: bool = False) -> JSONDict:
        state = self.room.state
        question = self.room.question
        full_teams = full_teams or state == GameState.ANSWER

        base: JSONDict = {
            "cmd": "state_change",
            "state": state,
            "teams": (
                [team.full() if full_teams else team.public() for team in self.room.teams]
                if self.room.teams
                else None
            ),
            "audience": self.room.audience.json() if self.room.audience else None,
        }

        if full_teams and question:
            base["full_question"] = question.json()

        if question and state == GameState.QUESTION:
            base["question"] = {
                "headline": "Question #" + str(self.room.question_index + 1),
                "text": question.question_text,
                "media": question.question_media.json() if question.question_media else None,
            }
        elif question and state == GameState.ANSWER:
            base["question"] = {
                "headline": self.room.episode.answer_text(question.answer),
                "answer": str(question.answer),
                "text": question.answer_text,
                "media": question.answer_media.json() if question.answer_media else None,
            }
        else:
            base["question"] = None

        return base

    def _can_vote(self, _: str) -> bool:
        return False

    async def on_vote_change(self) -> None:
        await self._fanout(self._state_representation())

    @command
    async def setup(self, _: Socket) -> JSONDict:
        self.room.ping()
        return {
            "cmd": "setup",
            "state": self.room.state,
            "episode": {
                "title": self.room.episode.title,
                "author": self.room.episode.author,
                "description": self.room.episode.full_description,
                "this": self.room.episode.this_category,
                "that": self.room.episode.that_category,
                "has_both": self.room.episode.both_possible,
                "has_neither": self.room.episode.neither_possible,
            },
            "status": self._state_representation(),
        }

    @command
    async def vote(self, socket: Socket, team: str, vote: str) -> JSONDict | None:  # noqa: ARG002
        self.room.ping()

        # Ensure this endpoint can vote for this team
        if not isinstance(team, str) or not self._can_vote(team):
            self.room.logger.error("Rejecting for for %s in %s", team, self, extra={"room": self})
            return None

        voted = Vote(vote) if vote is not None else None
        await self.room.vote(team, voted)
        return {"cmd": "voted", "team": team, "voted": str(voted)}


class ThisOrThatGameManager(ThisOrThatEndpoint):
    def __str__(self) -> str:
        return "Game Master View"

    def _state_representation(self, *, full_teams: bool = True) -> JSONDict:
        base = super()._state_representation(full_teams=full_teams)

        question = self.room.question
        base["full_question"] = question.json() if question else None

        return base

    async def on_join(self, _: CatBoxContext, __: Request) -> ResponseProtocol:
        episode = self.room.episode

        doc = Document(
            episode.title,
            Element("section", id="endpoints", class_="panel"),
            _game_info_panel(),
            _play_area_panel(with_scores=True),
            Element("section", id="game-actions", class_="panel"),
            styles=[
                "/defs.css",
                "/style.css",
                "/gm.css",
                f"/{episode.engine_ident}/this-or-that.css",
            ],
            scripts=[
                "/gm.js",
                f"/{episode.engine_ident}/gm.js",
            ],
            class_="connecting",
            socket=str(self._endpoint),
        )

        return DocResponse(doc)

    def _can_vote(self, _: str) -> bool:
        return True

    @command
    async def endpoints(self, _: Socket) -> JSONDict:
        return {
            "cmd": "endpoints",
            "endpoints": [
                {"room": endpoint.room_code, "name": str(endpoint)}
                for endpoint in self.room.endpoints.values()
            ],
        }

    @command
    async def start(self, _: Socket) -> JSONDict | None:
        if self.room.state != GameState.GAME_STARTING:
            self._error("Attempting to 'start' in progress game.")
            return {"cmd": "error", "message": "Game already started."}

        await self.room.next_question()
        return None

    @command
    async def next_question(self, _: Socket) -> None:
        await self.room.next_question()

    @command
    async def reveal_answer(self, _: Socket) -> None:
        await self.room.reveal_answer()

    @command
    async def close(self, _: Socket) -> None:
        await self.room.stop()


class ThisOrThatFullScreen(ThisOrThatEndpoint):
    def __str__(self) -> str:
        return "Shared/TV view"

    async def on_join(self, _: CatBoxContext, __: Request) -> ResponseProtocol:
        episode = self.room.episode

        doc = Document(
            episode.title,
            _play_area_panel(with_scores=True),
            styles=["/defs.css", "/style.css", f"/{episode.engine_ident}/this-or-that.css"],
            scripts=[f"/{episode.engine_ident}/general.js"],
            class_="fullscreen connecting",
            socket=str(self._endpoint),
            autoconnect="yes",
        )

        return DocResponse(doc)


class ThisOrThatPlayer(ThisOrThatEndpoint):
    _team: Team

    def __init__(self, room: ThisOrThatRoom, team: Team) -> None:
        super().__init__(room)
        self._team = team

    def __str__(self) -> str:
        return f"Team {self._team.name} controls"

    def _state_representation(self, *, full_teams: bool = False) -> JSONDict:
        base = super()._state_representation(full_teams=full_teams)
        base["self"] = self._team.full()

        return base

    def _can_vote(self, team: str) -> bool:
        return self._team.id == team

    async def on_join(self, _: CatBoxContext, __: Request) -> ResponseProtocol:
        episode = self.room.episode

        return DocResponse(
            Document(
                episode.title,
                Element("section", id="game-actions", class_="panel"),
                styles=["/defs.css", "/style.css", f"/{episode.engine_ident}/this-or-that.css"],
                scripts=[f"/{episode.engine_ident}/player.js"],
                class_="full connecting",
                socket=str(self._endpoint),
            ),
        )


class ThisOrThatAudience(ThisOrThatEndpoint):
    status: Audience

    def __init__(self, room: ThisOrThatRoom, status: Audience) -> None:
        super().__init__(room)
        self.status = status

    def __str__(self) -> str:
        return "Audience controls"

    def on_register(self, room_code: str, endpoint: yarl.URL) -> None:
        super().on_register(room_code, endpoint)
        self.status.room = room_code

    async def on_join(self, _: CatBoxContext, __: Request) -> ResponseProtocol:
        episode = self.room.episode

        return DocResponse(
            Document(
                episode.title,
                Element("section", id="game-actions", class_="panel"),
                styles=["/defs.css", "/style.css", f"/{episode.engine_ident}/this-or-that.css"],
                scripts=[f"/{episode.engine_ident}/audience.js"],
                class_="connecting",
                socket=str(self._endpoint),
            ),
        )

    async def on_close(self, socket: Socket) -> None:
        self.status.vote_record.pop(socket.session.cookie, None)
        self.status.members.discard(socket.session.cookie)
        self.room.queue_audience_update()

    @command
    async def setup(self, socket: Socket) -> JSONDict | None:
        self.status.members.add(socket.session.cookie)
        self.room.queue_audience_update()
        return await super().setup(socket)

    @command
    async def vote(self, socket: Socket, team: str, vote: str) -> JSONDict:
        voted = Vote(vote)
        self.status.vote_record[socket.session.cookie] = voted
        self.status.members.add(socket.session.cookie)
        self.room.queue_audience_update()

        return {"cmd": "voted", "vote": str(voted)}


class ThisOrThatScoreOverlay(ThisOrThatEndpoint):
    def __str__(self) -> str:
        return "Scoreboard overlay"

    async def on_join(self, _: CatBoxContext, __: Request) -> ResponseProtocol:
        episode = self.room.episode

        return DocResponse(
            Document(
                episode.title,
                Element("header", id="scores", class_="left-slant right-slant"),
                styles=["/defs.css", "/style.css", f"/{episode.engine_ident}/this-or-that.css"],
                scripts=[f"/{episode.engine_ident}/general.js"],
                class_="connecting score-overlay",
                socket=str(self._endpoint),
                autoconnect="yes",
            ),
        )


def _game_info_panel() -> Element:
    return Element(
        "section",
        Element("h1", id="gi-title"),
        Element("p", id="gi-author"),
        Element("p", id="gi-description", class_="usertext"),
        id="game-info",
        class_="panel",
    )


def _play_area_panel(*, with_scores: bool) -> Element:
    return Element(
        "section",
        Element(
            "main",
            Element("p", id="pl-headline"),
            Element("p", id="pl-text", class_="usertext"),
            Element("img", id="pl-media"),
        ),
        Element("div", id="scores") if with_scores else "",
        id="play-area",
        class_="panel",
    )
