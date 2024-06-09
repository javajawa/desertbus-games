# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import Any

import asyncio
import ipaddress
import pathlib
import uuid
from http import HTTPStatus

import multidict
import yarl
from aiohttp.web import (
    HTTPFound,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPUnauthorized,
)

from catbox.engine import EpisodeState, EpisodeVersion, GameEngine
from catbox.static import DocResponse, StaticResponse
from catbox.user import User
from webapp import Application, Request, RequestContext, ResponseProtocol, RoutingView

from .cms_index import cms_index
from .game_index import game_index
from .play_game import process_options, setup_page
from .review_index import approved, review_index
from .state import CatBoxContext, CatBoxRoute, CatBoxState, OAuthDetails, PublicEndpoint


class CatBoxApplication(Application[CatBoxState, CatBoxContext, CatBoxRoute]):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        engines: dict[str, type[GameEngine[Any]]],
        *,
        oauth: OAuthDetails,
        listen: PublicEndpoint,
        public: PublicEndpoint | None = None,
    ) -> None:
        public = public or listen

        super().__init__(CatBoxState(public, oauth, engines), not_found())
        self._binds.add((ipaddress.IPv4Address(listen.host), listen.port))

        routes = self.default_table()

        routes.add("/play/*", CatBoxRoute(self.play_episode))
        routes.add("/review", CatBoxRoute(self.review))
        routes.add("/cms", CatBoxRoute(self.cms))
        routes.add("/login", CatBoxRoute(self.login))
        routes.add("/cms/create/*", CatBoxRoute(self.create_episode))
        routes.add("/edit/*", CatBoxRoute(self.edit_episode))
        routes.add("/view/*", CatBoxRoute(self.view_episode))
        routes.add("/approve/*", CatBoxRoute(self.approve_episode))
        routes.add("/discard/*", CatBoxRoute(self.discard_episode))
        routes.add("/room/*", CatBoxRoute(self.join))
        routes.add("/join", CatBoxRoute(self.join_by_query))
        routes.add("/ws/*", CatBoxRoute(self.endpoint))
        routes.add("/blob/*", CatBoxRoute(self.blob))
        add_resources(
            loop,
            self._app_context,
            routes,
            (pathlib.Path(__file__) / ".." / "resources").resolve(),
        )
        for ident, engine in engines.items():
            add_resources(loop, self._app_context, routes, engine.resources(), ident + "/")

    async def review(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        user = ctx.user
        if not user:
            return send_to_login(request)

        if not user or not user.is_mod:
            return HTTPUnauthorized(body="This page is for moderators only.")

        return DocResponse(await review_index(self._app_context.engines.values()))

    async def login(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        session = ctx.session

        if "error" in request.query:
            self._app_context.logger.warning(
                "Error in login response %s",
                request.query["error_description"],
                extra={"session": session},
            )
            return HTTPUnauthorized(body=request.query["error_description"])

        if "code" in request.query:
            csrf_state = request.query["state"]
            self._app_context.logger.info(
                "Processing login",
                extra={"session": session, "csrf_token": csrf_state},
            )

            if not csrf_state or (session.login_state != csrf_state):
                self._app_context.logger.warning(
                    "Bad CSRF token",
                    extra={
                        "session": session,
                        "csrf_token": csrf_state,
                        "expected": session.login_state,
                    },
                )
                return HTTPUnauthorized(body="The CSRF token did not match")

            if not (user := await self._get_user_from_twitch(request.query["code"])):
                return HTTPUnauthorized(body="Error getting info from Twitch")

            session.user = user
            return HTTPFound(session.redirect_to or "/")

        session.login_state = uuid.uuid4().hex
        session.redirect_to = request.query.get("to", "/")

        url = yarl.URL.build(
            scheme="https",
            host="id.twitch.tv",
            path="/oauth2/authorize",
            query={
                "response_type": "code",
                "client_id": self._app_context.oauth.client_id,
                "redirect_uri": str(self._app_context.make_url("/login")),
                "scope": "",
                "state": session.login_state,
            },
        )

        resp = HTTPFound(location=url)

        self._app_context.logger.info(
            "Starting login flow",
            extra={"session": session, "csrf_token": session.login_state},
        )

        return resp

    async def cms(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        if not ctx.user:
            return send_to_login(request)

        return DocResponse(await cms_index(self._app_context.engines.values(), ctx.user))

    async def blob(self, _: CatBoxContext, request: Request) -> ResponseProtocol:
        if not self._app_context.blob_manager:
            return HTTPInternalServerError(body="Blob manager not initialised")

        return await self._app_context.blob_manager.handle(request)

    async def play_episode(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        if request.path == "/play":
            return DocResponse(await game_index(self._app_context.engines.values()))

        data = self._get_owned_episode(ctx, request)

        if not isinstance(data, tuple):
            return data

        if request.method == "GET":
            return setup_page(*data)

        engine, episode = data
        room = engine.play_episode(episode, await process_options(request))
        self._app_context.add_room(room)

        return HTTPFound(f"/room/{room.starting_endpoint.room_code}")

    async def view_episode(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        data = self._get_owned_episode(ctx, request)

        if not isinstance(data, tuple):
            return data

        engine, episode = data
        room = engine.view_episode(episode)
        self._app_context.add_room(room)

        return HTTPFound(f"/room/{room.starting_endpoint.room_code}")

    async def create_episode(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        if not ctx.user:
            return send_to_login(request)

        _, _, _, engine_ident = request.path.split("/", 3)

        engine = self._app_context.engines[engine_ident]

        if not engine or not engine.cms_enabled:
            return HTTPNotFound(
                body=f"Engine {engine_ident} does not exist or does not support CMS editing.",
            )

        episode = engine.create_episode(ctx.user)

        return HTTPFound(f"/edit/{engine_ident}/{episode.id}/0")

    async def edit_episode(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        data = self._get_owned_episode(ctx, request, require_owner=True)

        if not isinstance(data, tuple):
            return data

        engine, episode = data

        if episode.state == EpisodeState.PENDING_REVIEW:
            engine.save_state(episode, EpisodeState.DRAFT)
        if episode.state != EpisodeState.DRAFT:
            return HTTPUnauthorized(body="Can not edit version not in draft")

        room = engine.edit_episode(episode)
        self._app_context.add_room(room)

        return HTTPFound(f"/room/{room.starting_endpoint.room_code}")

    async def approve_episode(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        data = self._get_owned_episode(ctx, request, require_moderator=True)

        if not isinstance(data, tuple):
            return data

        engine, episode = data

        if episode.state != EpisodeState.PENDING_REVIEW:
            return HTTPInternalServerError(body="Episode state is not pending review")

        engine.save_state(episode, EpisodeState.PUBLISHED)

        return DocResponse(approved(episode))

    async def discard_episode(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        data = self._get_owned_episode(ctx, request, require_owner=True)

        if not isinstance(data, tuple):
            return data

        engine, episode = data
        new_state = (
            EpisodeState.SUPERSEDED
            if episode.state == EpisodeState.PUBLISHED
            else EpisodeState.DISCARDED
        )
        engine.save_state(episode, new_state)

        return HTTPFound("/cms")

    def _get_owned_episode(
        self,
        ctx: CatBoxContext,
        request: Request,
        *,
        require_owner: bool = False,
        require_moderator: bool = False,
    ) -> tuple[GameEngine[Any], EpisodeVersion] | ResponseProtocol:
        if (require_owner or require_moderator) and not ctx.user:
            return send_to_login(request)

        _, _, engine_ident, episode_id, version_str = request.path.split("/", 5)

        engine = self._app_context.engines[engine_ident]

        if not engine or not engine.cms_enabled:
            return HTTPNotFound(
                body=f"Engine {engine_ident} does not exist or does not support CMS editing.",
            )

        episode = engine.get_episode_version(int(episode_id), int(version_str))

        if not episode:
            return HTTPNotFound(body="Episode not found")

        if require_owner and episode.author_id != ctx.user.user_id:  # type: ignore[union-attr]
            return HTTPUnauthorized(
                body=f"You do not own this episode. (Owned by {episode.author})",
            )

        if require_moderator and not ctx.user.is_mod:  # type: ignore[union-attr]
            return HTTPUnauthorized(
                body="You are not a moderator.",
            )

        return engine, episode

    async def join(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        _, _, room_code = request.path.split("/", 2)

        if not (endpoint := self._app_context.active_endpoints.get(room_code)):
            return HTTPNotFound()

        return await endpoint.on_join(ctx, request)

    async def join_by_query(self, _: CatBoxContext, request: Request) -> ResponseProtocol:
        return HTTPFound("/room/" + request.query.get("room", "0000").upper())

    async def endpoint(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        _, _, room_code = request.path.split("/", 2)

        if not (endpoint := self._app_context.active_endpoints.get(room_code.upper())):
            return HTTPNotFound()

        return await endpoint(ctx, request)

    async def _get_user_from_twitch(self, authorization_code: str) -> User | None:
        if not self._app_context.http:
            raise RuntimeError
        if not self._app_context.user_manager:
            raise RuntimeError

        resp = await self._app_context.http.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": self._app_context.oauth.client_id,
                "client_secret": self._app_context.oauth.client_secret,
                "grant_type": "authorization_code",
                "code": authorization_code,
                "redirect_uri": str(self._app_context.make_url("/login")),
            },
            timeout=15,
        )

        if resp.status != HTTPStatus.OK:
            message = await resp.text()
            self._app_context.logger.error(
                "Error fetching oAuth token: %s",
                message,
                extra={"status_code": resp.status},
            )
            raise HTTPUnauthorized(body=message)

        token = (await resp.json()).get("access_token")

        resp = await self._app_context.http.get(
            "https://api.twitch.tv/helix/users",
            headers={
                "Authorization": "Bearer " + token,
                "Client-ID": self._app_context.oauth.client_id,
            },
            timeout=15,
        )

        if resp.status != HTTPStatus.OK:
            message = await resp.text()
            self._app_context.logger.error(
                "Error getting Twitch user details: %s",
                message,
                extra={"status_code": resp.status},
            )
            raise HTTPUnauthorized(body=message)

        user_list = (await resp.json()).get("data", [])

        if not user_list:
            raise HTTPUnauthorized(body="No user returned?")

        user = user_list[0]

        return self._app_context.user_manager.for_twitch(int(user["id"]), user["display_name"])


def add_resources(
    loop: asyncio.AbstractEventLoop,
    context: CatBoxState,
    router: RoutingView[CatBoxState, CatBoxContext, CatBoxRoute],
    path: pathlib.Path,
    prefix: str = "/",
) -> None:
    for file in path.iterdir():
        router.add(prefix + file.name, static(loop, context, file))

        if file.name == "index.html":
            router.add(prefix, static(loop, context, file))


def static(
    loop: asyncio.AbstractEventLoop,
    context: CatBoxState,
    file: pathlib.Path,
) -> CatBoxRoute:
    return CatBoxRoute(StaticResponse(context, loop, file))  # type: ignore[arg-type]


def not_found() -> CatBoxRoute:
    # TODO @ben: Make this look nice!
    #      Actually, work on errors in general...
    #      CATBOX-1
    async def call(_c: RequestContext, _r: Request) -> ResponseProtocol:
        return HTTPNotFound()

    return CatBoxRoute(call)


def send_to_login(request: Request) -> HTTPFound:
    return HTTPFound(
        yarl.URL.build(
            path="/login",
            query=multidict.MultiDict({"to": str(request.url.relative())}),
        ),
    )


__all__ = ["CatBoxApplication", "CatBoxState", "OAuthDetails", "PublicEndpoint"]
