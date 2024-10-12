# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import Any

import asyncio
import dataclasses
import logging
import os
import random
import sqlite3
import string
import uuid

import aiohttp
import yarl
from aiohttp.web import StreamResponse

from catbox.blob import BlobManager
from catbox.engine import GameEngine
from catbox.logger import JsonFormatter
from catbox.room import Endpoint, Room
from catbox.user import User, UserManager
from webapp import AppContext, Handler, Request, RequestContext, ResponseProtocol, Route

DEFAULT_HTTPS_PORT = 443
SESSION_COOKIE = "_cookie"


@dataclasses.dataclass
class Session:
    cookie: str
    user: User | None
    redirect_to: str | None
    login_state: str | None

    __slots__ = ("cookie", "user", "redirect_to", "login_state")

    def __init__(self, cookie: str) -> None:
        self.cookie = cookie
        self.user = None
        self.redirect_to = None
        self.login_state = None


class CatBoxContext(RequestContext):
    session: Session

    __slots__ = ("session",)

    def __init__(self, app_ctx: CatBoxState, session: Session) -> None:
        super().__init__(app_ctx)  # type: ignore[arg-type]
        self.session = session

    @property
    def user(self) -> User | None:
        if not self.session:
            return None
        return self.session.user


class CatBoxRoute(Route[CatBoxContext]):
    def __init__(self, handler: Handler[CatBoxContext]) -> None:
        async def inner(a: CatBoxContext, r: Request) -> ResponseProtocol:
            resp = await handler(a, r)
            if isinstance(resp, StreamResponse):
                resp.set_cookie(
                    SESSION_COOKIE,
                    a.session.cookie,
                    max_age=86400 * 30,
                    samesite="lax",
                )
            return resp

        super().__init__(inner)


@dataclasses.dataclass
class PublicEndpoint:
    host: str
    port: int


@dataclasses.dataclass
class OAuthDetails:
    client_id: str
    client_secret: str


class CatBoxState(AppContext[CatBoxRoute, CatBoxContext]):  # Big data class.
    url: PublicEndpoint
    oauth: OAuthDetails

    engine_types: dict[str, type[GameEngine[Any]]]
    engines: dict[str, GameEngine[Any]]
    user_manager: UserManager | None
    blob_manager: BlobManager | None
    database: sqlite3.Connection | None
    http: aiohttp.ClientSession | None

    sessions: dict[str, Session]
    active_rooms: dict[str, Room]
    active_endpoints: dict[str, Endpoint]
    tasks: set[asyncio.Task[None]]

    def __init__(
        self,
        endpoint: PublicEndpoint,
        oauth: OAuthDetails,
        engines: dict[str, type[GameEngine[Any]]],
    ) -> None:
        super().__init__(logging.getLogger("catbox"))
        self.url = endpoint
        self.oauth = oauth
        self.engine_types = engines.copy()
        self.engines = {}
        self.blob_manager = None
        self.user_manager = None
        self.http = None
        self.database = None
        self.sessions = {}
        self.active_rooms = {}
        self.active_endpoints = {}
        self.tasks = set()

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        self.logger.info("Connecting to database.")
        self.database = sqlite3.connect("games.db")
        self.blob_manager = BlobManager(loop, self.database)
        self.user_manager = UserManager(self.database)
        self.http = aiohttp.ClientSession(loop=loop)
        self._kitteh_login(self.user_manager)
        self.logger.info("Setting up game engines.")
        self.engines = {
            ident: engine(
                ident,
                self.logger.getChild(ident),
                self.database,
                self.blob_manager,
                self.user_manager,
            )
            for ident, engine in self.engine_types.items()
        }
        self.tasks.add(loop.create_task(self.reap_rooms(), name="reap-rooms"))

    def _kitteh_login(self, user_manager: UserManager) -> None:
        session = os.getenv("CATBOX_KITTEH")
        if not session:
            return

        kitteh = Session(session)
        kitteh.user = user_manager.get(1)
        self.sessions[session] = kitteh

    async def reap_rooms(self) -> None:
        try:
            while True:
                await asyncio.sleep(2)
                for code in list(self.active_rooms.keys()):
                    room = self.active_rooms.get(code)
                    if not room or not await room.reap():
                        continue

                    del self.active_rooms[code]
                    endpoints = [
                        endpoint.room_code
                        for endpoint in room.endpoints.values()
                        if endpoint.room_code
                    ]
                    for endpoint in endpoints:
                        del self.active_endpoints[endpoint]

                    self.logger.info("Reaped room %s (endpoints %s)", code, endpoints)
        except asyncio.CancelledError:
            pass

    async def shutdown(self) -> None:
        loop = asyncio.get_running_loop()

        self.logger.warning("Shutting down active rooms")
        results = await asyncio.gather(
            *(
                loop.create_task(s.stop(), name=f"shutdown-{k}")
                for k, s in self.active_rooms.items()
            ),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                self.logger.error("Error during shutdown", exc_info=result)
        # Allow to be garbage collected
        self.active_rooms = {}
        self.active_endpoints = {}

        self.logger.warning("Closing database connection")
        if self.database:
            self.database.commit()
            self.database.close()

        self.logger.warning("Closing background tasks")
        for task in self.tasks:
            task.cancel()
        results = await asyncio.gather(*self.tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                self.logger.error("Error during shutdown", exc_info=result)

        if self.http:
            self.logger.warning("Closing HTTP server")
            await self.http.close()

    async def make_context(self, _: CatBoxRoute, request: Request) -> CatBoxContext:
        cookie = request.cookies.get(SESSION_COOKIE, uuid.uuid4().hex)
        session = self.sessions.setdefault(cookie, Session(cookie))

        return CatBoxContext(self, session)

    def _generate_room_code(self) -> str:
        code = "".join(random.choices(string.ascii_uppercase, k=4))  # noqa: S311 - Not crypto
        while code in self.active_endpoints:
            code = "".join(random.choices(string.ascii_uppercase, k=4))  # noqa: S311 - Not crypto
        return code

    def add_task(self, task: asyncio.Task[None]) -> None:
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def add_room(self, room: Room) -> Endpoint:
        self.logger.info("Adding room for %s", room)
        room_code = self._generate_room_code()
        endpoint = room.default_endpoint

        self.active_rooms[room_code] = room
        self.active_endpoints[room_code] = endpoint

        handler = logging.FileHandler(f"logs/{room_code}.log", encoding="utf-8")
        handler.setFormatter(JsonFormatter())  # type: ignore[no-untyped-call]
        handler.setLevel(logging.INFO)
        room.logger = room.logger.getChild(room_code)
        room.logger.addHandler(handler)

        endpoint.on_register(room_code, self.websocket(room_code))

        for endpoint in room.endpoints.values():
            if endpoint.room_code:
                continue

            room_code = self._generate_room_code()
            self.active_endpoints[room_code] = endpoint
            endpoint.on_register(room_code, self.websocket(room_code))

        return room.starting_endpoint

    def websocket(self, room: str) -> yarl.URL:
        return yarl.URL.build(
            scheme="wss" if self.url.port == DEFAULT_HTTPS_PORT else "ws",
            host=self.url.host,
            port=self.url.port,
            path="/ws/" + room,
        )

    def make_url(self, path: str) -> yarl.URL:
        return yarl.URL.build(
            scheme="https" if self.url.port == DEFAULT_HTTPS_PORT else "http",
            host=self.url.host,
            port=self.url.port,
            path=path,
        )
