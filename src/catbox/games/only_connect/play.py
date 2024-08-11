# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import abc
import enum
import logging
import uuid

from catbox.room import Endpoint, Room, RoomOptions
from catbox.site.state import CatBoxContext
from catbox.static import DocResponse
from dom import Document, Element
from webapp import Request, ResponseProtocol

from .episode import OnlyConnectEpisode


class RoundTracker(enum.StrEnum):
    PRE_GAME = "pre_game"
    CONNECTIONS = "connections"
    COMPLETIONS = "completions"
    CONNECTING_WALLS = "connecting_walls"
    MISSING_VOWELS = "missing_vowels"
    POST_GAME = "post_game"


class InRoundState(enum.StrEnum):
    QUESTION_SELECTION = "select"
    QUESTION_ACTIVE = "question"
    ANSWER_REVEALED = "answer"
    POST_ROUND = "post-round"


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


class OnlyConnectRoom(Room):
    episode: OnlyConnectEpisode
    teams: tuple[TeamData] | tuple[TeamData, TeamData]

    current_round: RoundTracker
    round_state: InRoundState

    def __init__(
        self, logger: logging.Logger, episode: OnlyConnectEpisode, options: RoomOptions
    ) -> None:
        self.episode = episode
        self.current_round = RoundTracker.PRE_GAME
        self.round_state = InRoundState.POST_ROUND
        self.teams = tuple(TeamData(team) for team in options.teams[0:2])

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


class OnlyConnectEndpoint(Endpoint, abc.ABC):
    room: OnlyConnectRoom


class OnlyConnectGMEndpoint(OnlyConnectEndpoint):
    def __str__(self) -> str:
        return "Only Connect - Game Manager"

    async def on_join(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        episode = self.room.episode

        return DocResponse(
            Document(
                episode.title,
                Element("section", id="endpoints", class_="panel"),
                Element("section", id="game-actions", class_="panel"),
                styles=[
                    "/defs.css",
                    "/style.css",
                    "/gm.css",
                    f"/{episode.engine_ident}/only-connect.css",
                ],
                scripts=[
                    "/gm.js",
                    f"/{episode.engine_ident}/gm.js",
                ],
                class_="connecting",
                socket=str(self._endpoint),
            ),
        )


class OnlyConnectOverlayEndpoint(OnlyConnectEndpoint):
    def __str__(self) -> str:
        return "Only Connect - Overlay"

    async def on_join(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        return DocResponse(Document("nyaa"))


class OnlyConnectPreviewEndpoint(OnlyConnectEndpoint):
    def __str__(self) -> str:
        return "Only Connect - Full Screen"

    async def on_join(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        return DocResponse(Document("nyaa"))
