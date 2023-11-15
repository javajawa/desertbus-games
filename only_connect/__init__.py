from __future__ import annotations

from typing import Any, Awaitable

import asyncio
import dataclasses
import datetime
import functools
import logging
import json
import random
import string

from aiohttp import web, WSMsgType, WSMessage

from .state import Game, OverallState, Question
from .config import TestGame


Message = str
MaybeMessage = Message | None | Awaitable[Message | None]


class StateEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


class Servlet:
    _app: web.Application
    _available: dict[str, type[Game]]
    _games: dict[str | None, GameServlet | None]

    def __init__(self) -> None:
        self._app = web.Application()
        self._app.router.add_route("GET", "/", self._game_index)
        self._app.router.add_route("GET", "/create/{slug}/{teams}", self._create_room)
        self._app.router.add_route("GET", "/{prefix}/ws", self._room_socket)
        self._app.router.add_route("GET", "/{prefix}/gm", self._room_gm_page)
        self._app.router.add_route("GET", "/{prefix}/pres", self._room_presentation_page)
        self._app.router.add_static("/{prefix}/", "only_connect/resources/")
        self._app.router.add_static("/", "only_connect/resources/")

        self._available = {
            "test": TestGame,
        }
        self._games = {None: None}

    def run(self, ssl) -> None:
        web.run_app(self._app, port=8081, access_log=None, ssl_context=ssl)

    async def _game_index(self, _: web.Request) -> web.Response:
        rooms = [
            f'<li>{room.description()}: <a href="create/{path}/1">One Team</a> | <s>Two Teams</s> (Coming Soon(?))</li>'
            for path, room in self._available.items()
        ]

        return web.Response(
            content_type="text/html",
            body=(
                "<!DOCTYPE html><html><head>"
                '<meta charset="utf-8">'
                '<link rel="stylesheet" href="/style.css">'
                "</head><body>"
                "<h1>Only Connect</h1>"
                f'<ul>{"".join(rooms)}</ul>'
                "</body></html>"
            ),
        )

    async def _create_room(self, request: web.Request) -> web.Response:
        game_slug = request.match_info["slug"]
        teams = int(request.match_info["teams"])

        if game_slug not in self._available:
            return web.Response(status=404)

        prefix = None
        while prefix in self._games:
            prefix = "".join(random.choices(string.ascii_uppercase, k=4))

        self._games[prefix] = GameServlet(self._available[game_slug](teams))

        return web.HTTPFound("/" + prefix + "/gm")

    def _get_room(self, request: web.Request) -> GameServlet | None:
        return self._games.get(request.match_info["prefix"])

    async def _room_socket(self, request: web.Request) -> web.StreamResponse:
        game = self._get_room(request)
        return await game.socket(request) if game else web.HTTPNotFound()

    async def _room_gm_page(self, request: web.Request) -> web.StreamResponse:
        game = self._get_room(request)
        return web.FileResponse("only_connect/resources/gm.html") if game else web.HTTPNotFound()

    async def _room_presentation_page(self, request: web.Request) -> web.StreamResponse:
        game = self._get_room(request)
        return web.FileResponse("only_connect/resources/display.html") if game else web.HTTPNotFound()


class Socket(web.WebSocketResponse):
    remote: str

    def __init__(self, remote: str) -> None:
        self.remote = remote
        super().__init__()


class GameServlet:
    _game: Game
    _sockets: set[Socket]

    def __init__(self, game: Game) -> None:
        super().__init__()

        self._game = game
        self._sockets = set()
        self._logger = logging.getLogger("only_connect").getChild(str(hash(game)))

    async def socket(self, request: web.Request) -> web.WebSocketResponse:
        socket = Socket(request.remote)

        self._logger.info("Accepting new websocket from %s", socket.remote)
        await socket.prepare(request)

        self._sockets.add(socket)
        await self._send(socket)
        await self._process_messages(socket)

        self._sockets.remove(socket)
        await socket.close()

        return socket

    async def _process_messages(self, socket: Socket) -> None:
        msg: WSMessage
        async for msg in socket:
            if msg.type != WSMsgType.TEXT:
                self._logger.warning("Connection from %s closing with exception %s", socket.remote, socket.exception())
                return

            try:
                data = msg.json()
            except json.JSONDecodeError:
                self._logger.warning("Invalid JSON in opening connection from %s", socket.remote)
                return

            if "type" not in data:
                continue

            if hasattr(self, data["type"]):
                await (getattr(self, data["type"])(data))

    async def round(self, data: dict[str, str | int]) -> None:
        if self._game.state.current_question:
            return

        index = int(data.get("index", -1))

        if index < 0 or index >= len(self._game.rounds):
            return

        self._game.state.current_round = index
        self._game.state.available_questions = [True for _ in self._game.rounds[index]]
        await self._fanout()

    async def select(self, data: dict[str, str | int]) -> None:
        if self._game.state.current_question:
            return

        index = int(data.get("index", -1))

        if index < 0 or index >= len(self._game.state.available_questions):
            return

        if not self._game.state.available_questions[index]:
            return

        self._game.state.available_questions[index] = False
        self._game.state.selecting = index
        await self._fanout()
        self._game.state.selecting = None
        self._game.state.current_question = self._game.rounds[self._game.state.current_round][index]
        await asyncio.sleep(0.5)
        await self._fanout()

    async def clue(self, _: dict[str, str | int]) -> None:
        if not self._game.state.current_question:
            return

        if self._game.state.revealed_clues < self._game.state.current_question.max_clues:
            self._game.state.revealed_clues += 1
            await self._fanout()

    async def reveal(self, _: dict[str, str | int]) -> None:
        if not self._game.state.current_question:
            return

        self._game.state.answer_revealed = True
        await self._fanout()

    async def next_question(self, _: dict[str, str | int]) -> None:
        if not self._game.state.current_question:
            return

        self._game.state.current_question = None
        self._game.state.answer_revealed = False
        self._game.state.revealed_clues = 0
        await self._fanout()

    async def score(self, _: dict[str, str | int]) -> None:
        if not self._game.state.current_question:
            return

        points = [5, 3, 2, 1]
        score = points[self._game.state.revealed_clues]

        self._game.state.scores[self._game.state.current_team] += score
        self._game.state.current_question = None
        self._game.state.answer_revealed = False
        self._game.state.revealed_clues = 0
        await self._fanout()

    async def _fanout(self) -> None:
        await asyncio.gather(*[self._send(socket) for socket in self._sockets])

    async def _send(self, socket: Socket) -> None:
        try:
            await socket.send_json(
                self._game.state,
                dumps=functools.partial(json.dumps, cls=StateEncoder)
            )
        except ConnectionResetError as err:
            self._logger.warning(f"{socket.remote} has left the game! (exception={err})")
            self._sockets.remove(socket)

            try:
                await socket.close()
            except Exception:  # pylint: disable=broad-except
                pass
