# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, ParamSpec

import abc
import asyncio
import dataclasses
import datetime
import json
import logging
import uuid

import yarl
from aiohttp import http_websocket, web

from webapp import Request, ResponseProtocol

if TYPE_CHECKING:
    from catbox.engine import JSONDict
    from catbox.site.state import CatBoxContext, Session


TIMEOUT = datetime.timedelta(minutes=15)
TIMEZONE = datetime.UTC


P = ParamSpec("P")


def command(
    func: Callable[P, Awaitable[JSONDict | None]],
) -> Callable[P, Awaitable[JSONDict | None]]:
    func.__is_rpc__ = True  # type: ignore[attr-defined]
    func.__rpc_log__ = True  # type: ignore[attr-defined]
    return func


def command_no_log(
    func: Callable[P, Awaitable[JSONDict | None]],
) -> Callable[P, Awaitable[JSONDict | None]]:
    func.__is_rpc__ = True  # type: ignore[attr-defined]
    func.__rpc_log__ = False  # type: ignore[attr-defined]
    return func


@dataclasses.dataclass
class RoomOptions:
    scoring: bool
    teams: list[str]
    audience: bool


class Room(abc.ABC):
    endpoints: Mapping[str, Endpoint]
    logger: logging.Logger
    _stopped: bool
    _ping: datetime.datetime

    def __init__(self, logger: logging.Logger, **kwargs: Endpoint | None) -> None:
        self.endpoints = {k: v for k, v in kwargs.items() if v}
        self.logger = logger
        self._stopped = False
        self.ping()

    @abc.abstractmethod
    def __str__(self) -> str:
        pass

    def ping(self) -> None:
        if self._stopped:
            return

        self._ping = datetime.datetime.now(TIMEZONE) + TIMEOUT

    async def reap(self) -> bool:
        if self._ping < datetime.datetime.now(TIMEZONE):
            await self.stop()

        return self._stopped

    async def stop(self) -> None:
        self.logger.info("Shutting down room %s", self.default_endpoint.room_code)
        self._stopped = True
        for e in self.endpoints.values():
            await e.stop()

    @property
    @abc.abstractmethod
    def default_endpoint(self) -> Endpoint:
        pass

    @property
    @abc.abstractmethod
    def starting_endpoint(self) -> Endpoint:
        pass


class Socket(web.WebSocketResponse):
    remote: str
    socket_id: str
    session: Session

    def __init__(self, session: Session, request: Request) -> None:
        super().__init__(receive_timeout=2.5, heartbeat=1)

        self.remote = (
            request.headers.get("x-forwarded-for") or request.remote or "[unknown endpoint]"
        )
        self.socket_id = str(uuid.uuid4())
        self.session = session

    @property
    def username(self) -> str:
        return self.session.user.user_name if self.session.user else self.session.cookie

    def __repr__(self) -> str:
        return f"Socket<user={self.username},remote={self.remote},socket_id={self.socket_id[0:8]}>"

    def __str__(self) -> str:
        return f"{self.username} @ {self.remote}/{self.socket_id[0:4]}"


class Endpoint(abc.ABC):
    room: Room
    _stopped: bool

    _room_code: str | None
    _endpoint: yarl.URL | None
    _sockets: set[Socket]

    def __init__(self, room: Room) -> None:
        self.room = room

        self._room_code = None
        self._endpoint = None
        self._sockets = set()
        self._stopped = False

    @abc.abstractmethod
    def __str__(self) -> str:
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}<{self._room_code} - {len(self._sockets)} clients>"

    def _exception(
        self,
        ex: BaseException,
        msg: str,
        *args: str,
        socket: Socket | None = None,
    ) -> None:
        self.room.logger.error(
            msg,
            *args,
            exc_info=ex,
            extra={"room": self.room, "endpoint": self, "socket": socket},
        )

    def _info(self, msg: str, *args: str, socket: Socket | None = None) -> None:
        self.room.logger.info(
            msg,
            *args,
            extra={"room": self.room, "endpoint": self, "socket": socket},
        )

    def _error(self, msg: str, *args: str, socket: Socket | None = None) -> None:
        self.room.logger.error(
            msg,
            *args,
            extra={"room": self.room, "endpoint": self, "socket": socket},
        )

    async def _fanout(self, data: JSONDict, *, log: bool = True) -> list[Exception]:
        exceptions = [
            res
            for res in await asyncio.gather(
                *(socket.send_json(data) for socket in self._sockets),
                return_exceptions=True,
            )
            if isinstance(res, Exception)
        ]

        if not log:
            return exceptions

        for exc in exceptions:
            self._exception(exc, "Error in fanout")

        return []

    def on_register(self, room_code: str, endpoint: yarl.URL) -> None:
        self._room_code = room_code
        self._endpoint = endpoint
        self.room.logger.info(
            "Registered as %s",
            room_code,
            extra={"endpoint": self, "room": self.room},
        )

    @property
    def room_code(self) -> str | None:
        return self._room_code

    @abc.abstractmethod
    async def on_join(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        pass

    async def on_close(self, socket: Socket) -> None:
        self._info("Socket closed", socket=socket)

    async def stop(self) -> None:
        self._stopped = True
        sockets = self._sockets.copy()
        for socket in sockets:
            self._info("Closing socket due to stop request", socket=socket)
            await socket.send_json({"cmd": "close"})
            await socket.close()

    async def __call__(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        if self._stopped:
            return web.HTTPNotFound()

        socket = Socket(ctx.session, request)
        self._info("Accepting new connection", socket=socket)
        await socket.prepare(request)

        self._sockets.add(socket)
        if task := asyncio.current_task():
            task.set_name(repr(socket))

        # Process all messages in this socket
        await self._process_messages(socket)

        self._sockets.discard(socket)
        self._info("Disconnecting %s", str(socket), socket=socket)
        await self.on_close(socket)

        return socket  # type: ignore[return-value]

    async def _process_messages(self, socket: Socket) -> None:
        message: http_websocket.WSMessage
        async for message in socket:
            # If the Room has closed, exit immediately.
            if self._stopped:
                await socket.close()
                return

            # Mark the room as still active.
            self.room.ping()
            await self._parse_message(socket, message)

    async def _parse_message(self, socket: Socket, message: http_websocket.WSMessage) -> None:
        # Decode the incoming request
        try:
            data = message.json()
        except json.JSONDecodeError as ex:
            self._exception(ex, "Invalid JSON", socket=socket)
            return await socket.send_json(
                {
                    "cmd": "error",
                    "message": "Invalid JSON",
                    "data": message.data,
                    "exception": str(ex),
                },
            )

        # Extract the command name and underlying function
        cmd_name = data.get("cmd", "[NO COMMAND SPECIFIED]")
        cmd = getattr(self, cmd_name, None)

        # Check the requested command is an RPC command
        if not cmd or not hasattr(cmd, "__is_rpc__"):
            self._error("Invalid command %s", cmd_name, socket=socket)
            return await socket.send_json(
                {"cmd": "error", "message": f"Invalid command {cmd_name}"},
            )

        # Remove the command name from the arguments
        del data["cmd"]

        # Execute the command
        try:
            if cmd.__rpc_log__:
                self._info("Running command %s", cmd_name, socket=socket)
            if resp := await cmd(socket, **data):
                await socket.send_json(resp)
        except BaseException as ex:  # noqa: BLE001 - Being passed to logger
            self._exception(ex, "Error processing command %s", cmd, socket=socket)
            await socket.send_json(
                {
                    "cmd": "error",
                    "message": "Invalid JSON",
                    "exception": str(ex),
                },
            )
