# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import types
from collections.abc import Awaitable, Callable
from typing import Generic, Protocol, Self, TypeVar

import abc
import asyncio
import ipaddress
import logging
import logging.handlers
import pathlib
import signal

import aiohttp.abc
import aiohttp.web


class Request(aiohttp.web.BaseRequest):
    def __init__(  # noqa: PLR0913 need 6 parameters for the super call.
        self,
        message: aiohttp.http.RawRequestMessage,
        payload: aiohttp.streams.StreamReader,
        protocol: aiohttp.web.RequestHandler,
        payload_writer: aiohttp.abc.AbstractStreamWriter,
        task: asyncio.Task[None],
    ) -> None:
        task.set_name(f"HTTP/{message.method}")
        super().__init__(
            message,
            payload,
            protocol,
            payload_writer,
            task,
            asyncio.get_running_loop(),
        )


class RequestContext:
    logger: logging.Logger

    def __init__(
        self,
        app_context: AppContext[Route[RequestContext], RequestContext],
    ) -> None:
        if not (task := asyncio.current_task()):
            raise RuntimeError
        self.logger = app_context.logger.getChild(task.get_name())

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if exc_type is None or exc_val is None or exc_tb is None:
            return

        self.logger.exception("Error in request", exc_info=(exc_type, exc_val, exc_tb))


class ResponseProtocol(Protocol):
    async def prepare(
        self,
        request: aiohttp.web.Request,
    ) -> aiohttp.abc.AbstractStreamWriter | None:
        pass

    async def write_eof(self, data: bytes = b"") -> None:
        pass

    @property
    def keep_alive(self) -> bool | None:
        pass

    def force_close(self) -> None:
        pass


RequestCtx = TypeVar("RequestCtx", bound=RequestContext)
Handler = Callable[[RequestCtx, Request], Awaitable[ResponseProtocol]]


class Route(Generic[RequestCtx]):
    handler: Handler[RequestCtx]

    __slots__ = ("handler",)

    def __init__(self, handler: Handler[RequestCtx]) -> None:
        self.handler = handler


AppRoute = TypeVar("AppRoute", bound=Route)  # type: ignore[type-arg]


class AppContext(abc.ABC, Generic[AppRoute, RequestCtx]):
    logger: logging.Logger

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    async def start(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    @abc.abstractmethod
    async def make_context(self, route: AppRoute, request: Request) -> RequestContext:
        pass


AppCtx = TypeVar("AppCtx", bound=AppContext)  # type: ignore[type-arg]

Bind = tuple[ipaddress.IPv4Address | ipaddress.IPv6Address | None, int] | pathlib.Path


async def default_not_found(_c: RequestContext, _r: Request) -> aiohttp.web.Response:
    return aiohttp.web.HTTPNotFound()


DEFAULT_NOT_FOUND = Route(default_not_found)


class Router(Generic[AppCtx, RequestCtx, AppRoute]):
    _full_routes: dict[tuple[Bind | None, str | None], dict[str, AppRoute]]
    _prefix_routes: dict[
        tuple[Bind | None, str | None],
        dict[tuple[str, ...], AppRoute],
    ]

    def __init__(self, not_found_route: AppRoute) -> None:
        self._full_routes = {}
        self._prefix_routes = {}
        self.add_route(None, None, "/*", not_found_route)

    def default_table(self) -> RoutingView[AppCtx, RequestCtx, AppRoute]:
        return RoutingView(self, None, None)

    def route_table(
        self,
        bind: Bind,
        vhost: str | None,
    ) -> RoutingView[AppCtx, RequestCtx, AppRoute]:
        return RoutingView(self, bind, vhost)

    def add_route(
        self,
        bind: Bind | None,
        vhost: str | None,
        path: str,
        route: AppRoute,
    ) -> Self:
        if vhost is not None and bind is None:
            raise ValueError

        group = (bind, vhost)
        if group not in self._full_routes:
            self._full_routes[group] = {}
            self._prefix_routes[group] = {}

        if path.endswith("/*"):
            segments = (seg for seg in path.strip("/*").split("/") if seg)
            self._prefix_routes[group][tuple(segments)] = route
        else:
            self._full_routes[group][path.strip("/")] = route

        return self

    def route(self, bind: Bind, vhost: str, path: str) -> AppRoute:
        groups = tuple(
            g for g in ((bind, vhost), (bind, None), (None, None)) if g in self._full_routes
        )
        path = path.strip("/")

        for group in groups:
            if handler := self._full_routes[group].get(path):
                return handler

        segments = tuple(seg for seg in path.split("/") if seg)

        while True:
            for group in groups:
                if handler := self._prefix_routes[group].get(segments):
                    return handler

            if not segments:
                raise ValueError
            segments = segments[:-1]


class RoutingView(Generic[AppCtx, RequestCtx, AppRoute]):
    _parent: Router[AppCtx, RequestCtx, AppRoute]
    _bind: Bind | None
    _vhost: str | None

    def __init__(
        self,
        router: Router[AppCtx, RequestCtx, AppRoute],
        bind: Bind | None,
        vhost: str | None,
    ) -> None:
        self._parent = router
        self._bind = bind
        self._vhost = vhost

    def add(self, path: str, route: AppRoute) -> Self:
        self._parent.add_route(self._bind, self._vhost, path, route)
        return self

    def __setitem__(self, path: str, route: AppRoute) -> Self:
        self._parent.add_route(self._bind, self._vhost, path, route)
        return self


class TCPSite(aiohttp.web.TCPSite):
    async def start(self) -> None:
        await super().start()
        if isinstance(self._server, asyncio.Server):
            self._host, self._port = self._server.sockets[0].getsockname()


class BindConfig:
    _logger: logging.Logger
    _binds: set[Bind]
    _servers: dict[Bind, aiohttp.web.BaseSite]

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._binds = set()
        self._servers = {}

    def __hash__(self) -> int:
        return hash(self._binds)

    def add(self, bind: Bind) -> None:
        self._binds.add(bind)

    async def start(self, runner: aiohttp.web.BaseRunner) -> None:
        server: aiohttp.web.BaseSite

        for bind in (bind for bind in self._binds if bind not in self._servers):
            if isinstance(bind, pathlib.Path):
                self._logger.info("Listening to unix %s", bind)
                server = aiohttp.web.UnixSite(runner, bind)
            else:
                self._logger.warning("Listing to tcp %s:%d", str(bind[0]), bind[1])
                server = TCPSite(runner, host=str(bind[0]), port=bind[1])

            self._servers[bind] = server
            await server.start()
            self._logger.warning("Startup complete for %s", server.name)

    async def stop(self) -> None:
        await asyncio.gather(*[server.stop() for server in self._servers.values()])
        self._servers.clear()

    @property
    def binds(self) -> frozenset[Bind]:
        return frozenset(self._binds)


class Application(Generic[AppCtx, RequestCtx, AppRoute]):
    _app_context: AppCtx
    _runner: aiohttp.web.BaseRunner | None
    _binds: BindConfig
    _router: Router[AppCtx, RequestCtx, AppRoute]
    _config_lock: asyncio.Lock

    def __init__(self, app_context: AppCtx, not_found_route: AppRoute) -> None:
        self._app_context = app_context
        self._binds = BindConfig(self._app_context.logger)
        self._router = Router(not_found_route)
        self._config_lock = asyncio.Lock()
        self._runner = None

    def default_table(self) -> RoutingView[AppCtx, RequestCtx, AppRoute]:
        return self._router.default_table()

    def route_table(
        self,
        bind: Bind,
        vhost: str | None,
    ) -> RoutingView[AppCtx, RequestCtx, AppRoute]:
        if bind not in self._binds.binds:
            self._binds.add(bind)

        return self._router.route_table(bind, vhost)

    async def _handle(self, request: Request) -> ResponseProtocol:
        route = self._router.route(pathlib.Path(), request.host, request.path)
        context = await self._app_context.make_context(route, request)
        try:
            async with context as request_context:
                return await route.handler(request_context, request)
        except:  # noqa: E722 # pylint: disable=W0702 # we need to catch all errors here
            return aiohttp.web.HTTPInternalServerError()

    async def __aenter__(self) -> Application[AppCtx, RequestCtx, AppRoute]:
        async with self._config_lock:
            if self._runner:
                raise RuntimeError("Already running!")  # noqa: TRY003

            server = aiohttp.web.Server(
                self._handle,  # type: ignore[arg-type]
                request_factory=Request,
            )

            self._runner = aiohttp.web.ServerRunner(server)

            await self._app_context.start()
            await self._runner.setup()
            await self._binds.start(self._runner)

            return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        async with self._config_lock:
            if not self._runner:
                raise RuntimeError("Not running?")  # noqa: TRY003

            self._app_context.logger.warning("Closing binds")
            await self._binds.stop()

            self._app_context.logger.warning("Shutdown runner")
            await self._runner.shutdown()

            self._app_context.logger.warning("Shutdown app")
            await self._app_context.shutdown()

            self._app_context.logger.warning("Final cleanup")
            await self._runner.cleanup()

    async def main(self) -> None:
        loop = asyncio.get_running_loop()
        event = asyncio.Event()

        loop.add_signal_handler(signal.SIGINT, event.set)
        loop.add_signal_handler(signal.SIGTERM, event.set)

        async with self:
            await event.wait()
