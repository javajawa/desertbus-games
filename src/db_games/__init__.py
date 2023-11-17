from __future__ import annotations

from typing import Any, Awaitable

import asyncio
import dataclasses
import datetime
import functools
import inspect
import json
import logging
import pathlib
import random
import ssl
import string
from pathlib import Path

from aiohttp import WSMessage, WSMsgType, web

from .abc import Game
from .only_connect import AlphaFlightGame, NightWatchGame, TestGame

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
    _games: dict[str, GameServlet | None]

    def __init__(self) -> None:
        self._app = web.Application()
        self._app.router.add_route("GET", "/", self.game_index)
        self._app.router.add_route("GET", "/create/{slug}/{teams}", self.create_room)
        self._app.router.add_route("GET", "/audit/{slug}", self.audit_game)

        self._app.router.add_route("GET", "/{prefix}/ws", self._room_socket)
        self._app.router.add_route("GET", "/ws/{prefix}", self._room_socket)
        self._app.router.add_route("GET", "/{prefix}/{file}", self._room_page)

        self._app.router.add_static("/", Path(__file__).parent / "resources")

        self._available = {
            "af120": AlphaFlightGame,
            "nw126": NightWatchGame,
            # "test": TestGame,
        }
        self._games = {"": None}

    def run(self, ssl_ctx: ssl.SSLContext | None) -> None:
        web.run_app(self._app, port=8081, access_log=None, ssl_context=ssl_ctx)

    async def game_index(self, _: web.Request) -> web.Response:
        rooms = [
            (
                f"<li>{room.description()}<ul>"
                f'<li><a href="/audit/{path}">Audit Content</a> (for stream safety)</li>'
                f'<li><a href="create/{path}/1">Play with One Team</a></li>'
                f"<li><s>Play with Two Teams</s> (Coming Soon(?))</li>"
                f"</ul></li>"
            )
            for path, room in self._available.items()
        ]

        return web.Response(
            content_type="text/html",
            body=(
                "<!DOCTYPE html><html><head>"
                '<meta charset="utf-8">'
                '<link rel="stylesheet" href="/style.css">'
                "</head><body>"
                "<h1>DB Games</h1>"
                f'<ul>{"".join(rooms)}</ul>'
                "</body></html>"
            ),
        )

    async def create_room(self, request: web.Request) -> web.Response:
        game_slug = request.match_info["slug"]
        teams = int(request.match_info["teams"])

        if game_slug not in self._available:
            return web.HTTPNotFound()

        prefix = ""
        while prefix in self._games:
            prefix = "".join(random.choices(string.ascii_uppercase, k=4))  # nosec

        game = self._available[game_slug](total_teams=teams)
        self._games[prefix] = GameServlet(game)

        return web.HTTPFound("/" + prefix + "/" + game.redirect())

    async def audit_game(self, request: web.Request) -> web.Response:
        game_slug = request.match_info["slug"]

        if game_slug not in self._available:
            return web.HTTPNotFound()

        game = self._available[game_slug]
        return await game.audit()

    def _get_room(self, request: web.Request) -> GameServlet | None:
        return self._games.get(request.match_info["prefix"])

    async def _room_socket(self, request: web.Request) -> web.StreamResponse:
        game = self._get_room(request)
        return await game.socket(request) if game else web.HTTPNotFound()

    async def _room_page(self, request: web.Request) -> web.StreamResponse:
        game = self._get_room(request)

        if not game:
            return web.HTTPNotFound()

        file = game.path(request.match_info["file"]).absolute()

        return web.FileResponse(file)

    async def _room_presentation_page(self, request: web.Request) -> web.StreamResponse:
        game = self._get_room(request)
        return (
            web.FileResponse("only_connect/resources/display.html")
            if game
            else web.HTTPNotFound()
        )


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

    def path(self, path: str) -> pathlib.Path:
        return self._game.path(path)

    async def socket(self, request: web.Request) -> web.WebSocketResponse:
        socket = Socket(request.remote or "[unknown endpoint]")

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
                self._logger.warning(
                    "Connection from %s closing with exception %s",
                    socket.remote,
                    socket.exception(),
                )
                return

            try:
                data = msg.json()
            except json.JSONDecodeError:
                self._logger.warning(
                    "Invalid JSON in opening connection from %s", socket.remote
                )
                return

            if "type" not in data:
                continue

            await self.handle_message(socket, data)

    async def handle_message(self, socket: Socket, data: dict[str, Any]) -> None:
        if not hasattr(self._game, data["type"]):
            self._logger.warning(
                "Unknown message %s from %s", data["type"], socket.remote
            )
            return

        handler = getattr(self._game, data["type"])

        if not inspect.isasyncgenfunction(handler) and not inspect.iscoroutinefunction(
            handler
        ):
            self._logger.warning(
                "Non-callable message type %s from %s", data["type"], socket.remote
            )
            return

        response = handler(data)

        if inspect.isasyncgen(response):
            async for action in response:
                if action:
                    await self._fanout()
        else:
            action = await response
            if action:
                await self._fanout()

    async def _fanout(self) -> None:
        await asyncio.gather(*[self._send(socket) for socket in self._sockets])

    async def _send(self, socket: Socket) -> None:
        try:
            await socket.send_json(
                self._game.state, dumps=functools.partial(json.dumps, cls=StateEncoder)
            )
        except ConnectionResetError as err:
            self._logger.warning(
                f"{socket.remote} has left the game! (exception={err})"
            )
            self._sockets.remove(socket)

            try:
                await socket.close()
            except Exception as exp:  # pylint: disable=broad-except
                self._logger.exception(exp)
