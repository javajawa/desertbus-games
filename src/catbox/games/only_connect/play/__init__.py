# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import abc
import asyncio
import logging
import uuid

from catbox.engine import JSONDict
from catbox.games.only_connect.episode import OnlyConnectEpisode
from catbox.room import Endpoint, Room, RoomOptions, Socket, command, command_no_log
from catbox.site.state import CatBoxContext
from catbox.static import DocResponse
from dom import Document, Element
from webapp import Request, ResponseProtocol

from .state_machine import (
    ConnectingWallState,
    MissingVowelsState,
    PossibleActions,
    RoundHandler,
    RoundTracker,
    StandardRoundState,
)


class TeamData:
    team_id: str
    name: str
    score: int

    def __init__(self, name: str) -> None:
        self.team_id = uuid.uuid4().hex
        self.name = name
        self.score = 0

    def __str__(self) -> str:
        return f"{self.name} ({self.score})"

    def __repr__(self) -> str:
        return f"TeamData(id={self.team_id}, name={self.name})"

    def json(self) -> JSONDict:
        return {"id": self.team_id, "name": self.name, "score": self.score}


class OnlyConnectRoom(Room):
    episode: OnlyConnectEpisode
    teams: tuple[TeamData] | tuple[TeamData, TeamData]
    endpoints: dict[str, OnlyConnectEndpoint]

    current_round: RoundTracker
    current_state: RoundHandler | None

    __slots__ = ("episode", "teams", "endpoints", "current_round", "current_state")

    def __init__(
        self,
        logger: logging.Logger,
        episode: OnlyConnectEpisode,
        options: RoomOptions,
    ) -> None:
        self.episode = episode
        self.current_round = RoundTracker.PRE_GAME
        self.current_state = None
        self.teams = tuple(TeamData(team) for team in options.teams[0:2])  # type: ignore[assignment]

        super().__init__(
            logger,
            gm=OnlyConnectGMEndpoint(self),
            preview=OnlyConnectPreviewEndpoint(self),
            overlay=OnlyConnectOverlayEndpoint(self),
        )

    def __str__(self) -> str:
        return "Only Connect"

    @property
    def default_endpoint(self) -> Endpoint:
        return self.endpoints["gm"]

    @property
    def starting_endpoint(self) -> Endpoint:
        return self.endpoints["gm"]

    async def fanout(self) -> None:
        exceptions = [
            res
            for res in await asyncio.gather(
                *(endpoint.fanout() for endpoint in self.endpoints.values()),
                return_exceptions=True,
            )
            if isinstance(res, Exception)
        ]

        for exception in exceptions:
            self.logger.exception("Error in fanout", exc_info=exception)

        self.logger.info("Fanout complete")

    def next_round(self) -> None:
        new_round = self.current_round
        while new_round := new_round.next():
            if self.start_round(new_round):
                return

    def start_round(self, new_round: RoundTracker) -> bool:

        if new_round == RoundTracker.CONNECTIONS and self.episode.has_connections_round:
            self.current_round = new_round
            self.current_state = StandardRoundState(self, self.episode.connections_round)  # type: ignore[arg-type]
            return True

        if new_round == RoundTracker.COMPLETIONS and self.episode.has_completions_round:
            self.current_round = new_round
            self.current_state = StandardRoundState(self, self.episode.completions_round)  # type: ignore[arg-type]
            return True

        if new_round == RoundTracker.CONNECTING_WALLS and self.episode.has_connecting_walls(
            len(self.teams),  # type: ignore[arg-type]
        ):
            self.current_round = new_round
            self.current_state = ConnectingWallState(self, self.episode.connecting_walls)  # type: ignore[arg-type]
            return True

        if new_round == RoundTracker.MISSING_VOWELS and self.episode.has_missing_vowels:
            self.current_round = new_round
            self.current_state = MissingVowelsState(self, self.episode.missing_vowels)  # type: ignore[arg-type]
            return True

        if new_round in {RoundTracker.PRE_GAME, RoundTracker.POST_GAME}:
            self.current_round = new_round
            self.current_state = None
            return True

        return False


class OnlyConnectEndpoint(Endpoint, abc.ABC):
    room: OnlyConnectRoom

    def _state_representation(self) -> JSONDict:
        state: JSONDict = {
            "round": self.room.current_round,
            "teams": [team.json() for team in self.room.teams],  # type: ignore[dict-item] # JSON
        }

        if self.room.current_state:
            state.update(self.room.current_state.public_state() or {})

        return state

    @command
    async def setup(self, _: Socket) -> JSONDict:
        return {
            "cmd": "setup",
            "episode": {
                "title": self.room.episode.title,
                "author": self.room.episode.author,
                "description": self.room.episode.full_description,
                "rounds": {
                    "connections": self.room.episode.has_connections_round,
                    "completions": self.room.episode.has_completions_round,
                    "walls": self.room.episode.has_connecting_walls(len(self.room.teams)),  # type: ignore[arg-type]
                    "vowels": self.room.episode.has_missing_vowels,
                },
            },
            "state": self._state_representation(),
        }

    async def fanout(self) -> None:
        await self._fanout({"cmd": "state_change", "state": self._state_representation()})


class OnlyConnectPreviewEndpoint(OnlyConnectEndpoint):
    def __str__(self) -> str:
        return "Only Connect - Full Screen"

    async def on_join(self, _: CatBoxContext, __: Request) -> ResponseProtocol:
        episode = self.room.episode

        return DocResponse(
            Document(
                episode.title,
                Element("section", id="scores", class_="panel"),
                Element("section", id="play-area", class_="panel fill"),
                styles=[
                    "/defs.css",
                    "/style.css",
                    f"/{episode.engine_ident}/onlyconnect.css",
                ],
                scripts=[f"/{episode.engine_ident}/onlyconnect.js"],
                class_="connecting big-screen",
                socket=str(self._endpoint),
                autoconnect="autoconnect",
            ),
        )

    @command
    async def toggle(self, socket: Socket, word: str) -> None:
        if not isinstance(self.room.current_state, ConnectingWallState):
            self._error("Attempting to toggle when not on connecting wall", socket=socket)
            return

        for _ in self.room.current_state.toggle(word):
            await self.room.fanout()


class OnlyConnectGMEndpoint(OnlyConnectPreviewEndpoint):
    def __str__(self) -> str:
        return "Only Connect - Game Manager"

    async def on_join(self, _: CatBoxContext, __: Request) -> ResponseProtocol:
        episode = self.room.episode

        return DocResponse(
            Document(
                episode.title,
                Element("section", id="endpoints", class_="panel"),
                Element(
                    "section",
                    Element("h1", id="gi-title"),
                    Element("p", id="gi-author"),
                    Element("p", id="gi-description"),
                    Element("p", id="gi-how-to"),
                    id="game-info",
                    class_="panel",
                ),
                Element("section", id="play-area", class_="panel fill"),
                Element("section", id="game-actions", class_="panel"),
                styles=[
                    "/defs.css",
                    "/style.css",
                    "/gm.css",
                    f"/{episode.engine_ident}/onlyconnect.css",
                ],
                scripts=[
                    "/gm.js",
                    f"/{episode.engine_ident}/gm.js",
                ],
                class_="connecting",
                socket=str(self._endpoint),
            ),
        )

    @command
    async def endpoints(self, _: Socket) -> JSONDict:
        return {
            "cmd": "endpoints",
            "endpoints": [  # type: ignore[dict-item] # JSON typing is hard
                {"room": endpoint.room_code, "name": str(endpoint)}
                for endpoint in self.room.endpoints.values()
            ],
        }

    @command
    async def close(self, _: Socket) -> None:
        await self.room.stop()

    @command
    async def skip(self, socket: Socket, round_name: str) -> None:
        new_round = RoundTracker[round_name]

        if not new_round:
            self._error("Invalid round %s", round_name, socket=socket)
            return

        if not self.room.start_round(new_round):
            self._error("Unable to skip to %s", new_round, socket=socket)
            return

        await self.room.fanout()

    @command_no_log
    async def action(self, _: Socket, action: str) -> None:
        choice = PossibleActions[action]
        room = self.room

        room.logger.info("Processing action %s", action)

        if choice == PossibleActions.START_NEXT_ROUND:
            room.next_round()
            await room.fanout()
            return

        if not self.room.current_state:
            return

        if self.room.current_state.do(choice):
            await room.fanout()

    def _state_representation(self) -> JSONDict:
        state: JSONDict = {
            "round": self.room.current_round,
            "teams": [team.json() for team in self.room.teams],  # type: ignore[dict-item] # JSON
        }

        if self.room.current_state:
            state.update(self.room.current_state.admin_state() or {})
            actions = self.room.current_state.possible_actions()
            state["actions"] = list(actions)  # type: ignore[assignment] # JSON typing is hard.
        elif self.room.current_round == RoundTracker.PRE_GAME:
            state["actions"] = [  # type: ignore[assignment] # JSON typing is hard.
                PossibleActions.START_NEXT_ROUND,
            ]

        return state


class OnlyConnectOverlayEndpoint(OnlyConnectEndpoint):
    def __str__(self) -> str:
        return "Only Connect - Overlay"

    async def on_join(self, _: CatBoxContext, request: Request) -> ResponseProtocol:
        episode = self.room.episode

        if chroma := request.query.get("chroma", ""):
            chroma = "--chroma: " + chroma

        return DocResponse(
            Document(
                episode.title,
                Element("header", id="scores", class_="overlay left-slant right-slant"),
                Element("section", id="play-area", class_="overlay"),
                styles=[
                    "/defs.css",
                    "/style.css",
                    f"/{episode.engine_ident}/onlyconnect.css",
                ],
                scripts=[f"/{episode.engine_ident}/onlyconnect.js"],
                class_="connecting chroma-keyed",
                socket=str(self._endpoint),
                style=chroma,
                autoconnect="autoconnect",
            ),
        )
