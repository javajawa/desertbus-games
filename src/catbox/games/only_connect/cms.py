# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import asyncio
import logging

from aiohttp import web

from catbox.engine import JSONDict
from catbox.room import Endpoint, Room, Socket, command
from catbox.site.state import CatBoxContext
from catbox.static import DocResponse
from dom import Document, Element
from webapp import Request, ResponseProtocol

from .episode import (
    ConnectingWall,
    MissingVowelsGroup,
    OnlyConnectEpisode,
    OnlyConnectQuestion,
    SixQuestions,
)

if TYPE_CHECKING:
    from . import OnlyConnectEngine


class OnlyConnectViewRoom(Room):
    episode: OnlyConnectEpisode

    def __init__(self, logger: logging.Logger, episode: OnlyConnectEpisode) -> None:
        # The episode title is used to generate the name, so we set it before calling __init__.
        self.episode = episode
        super().__init__(logger, view=OnlyConnectViewEndpoint(self))

    def __str__(self) -> str:
        return "Only Connect CMS"

    @property
    def default_endpoint(self) -> Endpoint:
        return self.endpoints["edit"]

    @property
    def starting_endpoint(self) -> Endpoint:
        return self.endpoints["edit"]


class OnlyConnectViewEndpoint(Endpoint):
    def __init__(self, room: OnlyConnectViewRoom | OnlyConnectEditRoom) -> None:
        super().__init__(room)

    def __str__(self) -> str:
        return "CMS (Re)View"

    async def on_join(self, _: CatBoxContext, __: Request) -> ResponseProtocol:
        return DocResponse(Document(""))


class FullEpisodeHelper:
    connections_round: SixQuestions
    completions_round: SixQuestions
    connecting_walls: tuple[ConnectingWall, ConnectingWall]
    missing_vowels: list[MissingVowelsGroup]

    def __init__(self, episode: OnlyConnectEpisode) -> None:
        self.connections_round = episode.connections_round or SixQuestions.default()
        self.completions_round = episode.completions_round or SixQuestions.default()
        self.connecting_walls = episode.connecting_walls or (
            ConnectingWall.default(),
            ConnectingWall.default(),
        )
        self.missing_vowels = episode.missing_vowels or []


class OnlyConnectEditRoom(Room):
    episode: OnlyConnectEpisode
    episode_but_enabled: FullEpisodeHelper

    _engine: OnlyConnectEngine

    save_timer: float | None
    save_task: asyncio.Task[None]

    def __init__(
        self,
        logger: logging.Logger,
        engine: OnlyConnectEngine,
        episode: OnlyConnectEpisode,
    ) -> None:
        # The episode title is used to generate the name, so we set it before calling __init__.
        self.episode = episode
        super().__init__(
            logger,
            edit=OnlyConnectEditEndpoint(self),
            view=OnlyConnectViewEndpoint(self),
        )

        self.save_timer = None
        self.save_task = asyncio.create_task(self._save())
        self._engine = engine

        # Episode But Enabled is used to remember the state of rounds
        # if someone disabled them, then re-enables them within the same
        # editing session.
        #
        # Basically, when any edit it made, it goes to both versions.
        # When a section is disabled, it is set to None only on the
        # main episode (which is saved to the database).
        # When a section is enabled, it is copied from this episode_but_enabled
        # property -- this also means the enable code does not need to understand
        # how to create a blank version of the round (which is done here instead).
        self.episode_but_enabled = FullEpisodeHelper(episode)

    def __str__(self) -> str:
        return "Only Connect CMS"

    async def stop(self) -> None:
        await super().stop()
        self.save_timer = None
        await self.save_task
        self._engine.save(self.episode)

    @property
    def default_endpoint(self) -> Endpoint:
        return self.endpoints["edit"]

    @property
    def starting_endpoint(self) -> Endpoint:
        return self.endpoints["edit"]

    def queue_save(self) -> None:
        self.ping()
        if not self.save_timer:
            self.save_timer = asyncio.get_running_loop().time() + 3

    async def _save(self) -> None:
        loop = asyncio.get_running_loop()

        try:
            while not self._stopped:
                if not self.save_timer:
                    await asyncio.sleep(5)
                    continue

                diff = loop.time() - self.save_timer
                if diff > 0:
                    await asyncio.sleep(diff)

                self.logger.info("Saving %s", self)
                self._engine.save(self.episode)
                self.save_timer = None
        except asyncio.CancelledError:
            pass


class OnlyConnectEditEndpoint(Endpoint):
    room: OnlyConnectEditRoom
    editing: dict[Socket, str | None]

    def __init__(self, room: OnlyConnectEditRoom) -> None:
        super().__init__(room)
        self.editing = {}

    def __str__(self) -> str:
        return "CMS Edit View"

    async def on_join(self, ctx: CatBoxContext, _: Request) -> ResponseProtocol:
        if not ctx.user:
            return web.HTTPFound(f"/login?to=/room/{self.room_code}")

        doc = Document(
            f'Editing "{self.room.episode.title}"',
            Element(
                "section",
                Element(
                    "header",
                    Element("h1", f'Editing "{self.room.episode.title}"'),
                    class_="left-slant",
                ),
                Element(
                    "main",
                    section_to_element(
                        self.room.episode.connections_round,
                        "Connections",
                        "Work out the connection",
                        "connections",
                    ),
                    section_to_element(
                        self.room.episode.completions_round,
                        "Completions",
                        "Complete the sequence (finding the fourth element)",
                        "completions",
                    ),
                    walls_to_element(self.room.episode.connecting_walls),
                    id="main",
                ),
            ),
            styles=["/defs.css", "/style.css", f"/{self.room.episode.engine_ident}/edit.css"],
            scripts=[f"/{self.room.episode.engine_ident}/edit.js"],
            socket=str(self._endpoint),
            class_="",
        )

        return DocResponse(doc)

    async def on_close(self, socket: Socket) -> None:
        await super().on_close(socket)

        if socket in self.editing:
            self.editing.pop(socket)
            await self.announce_editing(None, None)

    @command
    async def init(self, _: Socket) -> JSONDict:
        return {"cmd": "update", **self.room.episode.json()}

    @command
    async def announce_editing(self, socket: Socket | None, element: str | None) -> None:
        self._info("User is editing %s", element or "[nothing]", socket=socket)
        if socket is not None:
            self.editing[socket] = element

        await self._fanout(
            {
                "cmd": "editing",
                "positions": [
                    {
                        "session": socket.socket_id,
                        "username": socket.username,
                        "position": position,
                    }
                    for socket, position in self.editing.items()
                ],
            },
        )

    @command
    async def enable_section(self, socket: Socket, section: str) -> None:
        episode = self.room.episode
        episode_enabled = self.room.episode_but_enabled

        if section == "connections":
            episode.connections_round = episode_enabled.connections_round
        elif section == "completions":
            episode.completions_round = episode_enabled.completions_round
        elif section == "connecting_walls":
            episode.connecting_walls = episode_enabled.connecting_walls
        elif section == "missing_vowels":
            episode.missing_vowels = episode_enabled.missing_vowels
        else:
            self._error("Attempting to enable invalid section %s", section, socket=socket)
            return

        self.room.queue_save()
        await self._fanout({"cmd": "update", **episode.json()})

    @command
    async def disable_section(self, socket: Socket, section: str) -> None:
        episode = self.room.episode

        if section == "connections":
            episode.connections_round = None
        elif section == "completions":
            episode.completions_round = None
        elif section == "connecting_walls":
            episode.connecting_walls = None
        elif section == "missing_vowels":
            episode.missing_vowels = None
        else:
            self._error("Attempting to disable invalid section %s", section, socket=socket)
            return

        self.room.queue_save()
        await self._fanout({"cmd": "update", **episode.json()})

    @command
    async def update(  # noqa: PLR0913  need all 6 args
        self,
        socket: Socket,
        section: str,
        question: str,
        element: str,
        value: str,
    ) -> None:
        block: ConnectingWall | SixQuestions

        if section == "connections":
            block = self.room.episode_but_enabled.connections_round
        elif section == "completions":
            block = self.room.episode_but_enabled.completions_round
        elif section == "wall0":
            block = (
                self.room.episode_but_enabled.connecting_walls[0]
                if self.room.episode_but_enabled.connecting_walls
                else None
            )
        elif section == "wall1":
            block = (
                self.room.episode_but_enabled.connecting_walls[1]
                if self.room.episode_but_enabled.connecting_walls
                else None
            )
        else:
            self._error(
                "Attempt to update invalid: section %s/question %s/property %s",
                section,
                question,
                element,
                socket=socket,
            )
            return

        if self._update_basic_round(socket, block, question, element, value):
            self.room.queue_save()
            await self._fanout({"cmd": "update", **self.room.episode.json()})

    def _update_basic_round(  # noqa: PLR0913 need all 6 args.
        self,
        socket: Socket,
        questions: SixQuestions | ConnectingWall,
        question_str: str,
        element: str,
        value: str,
    ) -> bool:
        try:
            question_number = range_number(question_str, 0, len(questions))
        except ValueError:
            self._error(
                "Attempting to edit invalid connection question %s",
                question_str,
                socket=socket,
            )
            return False

        question: OnlyConnectQuestion = questions[question_number]

        if element == "connection":
            question.connection = value
            return True
        if element == "details":
            question.details = value
            return True

        try:
            element_number = range_number(element, 0, 4)
        except ValueError:
            self._error("Attempting to edit invalid element %s", element, socket=socket)
            return False

        question.elements[element_number] = value
        return True


def range_number(number: str, v_min: int, v_max: int) -> int:
    element_number = int(number)
    if element_number < v_min or element_number >= v_max:
        raise ValueError

    return element_number


def section_to_element(
    section: SixQuestions | None,
    title: str,
    description: str,
    prefix: str,
) -> Element:
    return Element(
        "details",
        Element("summary", Element("h2", title)),
        Element("p", description),
        Element(
            "fieldset",
            Element(
                "legend",
                Element(
                    "label",
                    Element("input", type="checkbox", checked="checked" if section else None),
                    "Enable ",
                    title,
                    " round",
                ),
            ),
            *(
                question_to_element(q, prefix + "." + str(i), title + " #" + str(i + 1))
                for i, q in enumerate(section or [None] * 6)
            ),
            id=prefix,
            disabled=None if section else "disabled",
        ),
        class_="panel",
        open="open",
    )


def walls_to_element(_walls: tuple[ConnectingWall, ConnectingWall] | None) -> Element:
    enabled = _walls is not None
    walls = _walls or ((None, None, None, None), (None, None, None, None))

    return Element(
        "details",
        Element("summary", Element("h2", "Connecting Walls")),
        Element(
            "p",
            "Each team gets a scrambled 4x4 grid, and has to find the four connected groups.",
        ),
        Element(
            "fieldset",
            Element(
                "legend",
                Element(
                    "label",
                    Element("input", type="checkbox", checked="checked" if enabled else None),
                    "Enable Connecting Walls",
                ),
            ),
            Element(
                "fieldset",
                Element("h3", "Wall A"),
                *(
                    question_to_element(question, f"wall0.{i}", f"Wall A - Group {i}")
                    for i, question in enumerate(walls[0])
                ),
            ),
            Element(
                "fieldset",
                Element("h3", "Wall B"),
                *(
                    question_to_element(question, f"wall1.{i}", f"Wall B - Group {i+1}")
                    for i, question in enumerate(walls[1])
                ),
            ),
            id="connecting_walls",
            disabled=None if enabled else "disabled",
        ),
        class_="panel",
        open="open",
    )


def question_to_element(question: OnlyConnectQuestion | None, prefix: str, title: str) -> Element:
    return Element(
        "fieldset",
        Element("h3", title, class_="conn-title"),
        Element(
            "label",
            Element("span", "Element 1"),
            Element("input", id=prefix + ".0", value=question.elements[0] if question else ""),
            for_=prefix + ".0",
            class_="element0",
        ),
        Element(
            "label",
            Element("span", "Element 2"),
            Element("input", id=prefix + ".1", value=question.elements[1] if question else ""),
            for_=prefix + ".1",
            class_="element1",
        ),
        Element(
            "label",
            Element("span", "Element 3"),
            Element("input", id=prefix + ".2", value=question.elements[2] if question else ""),
            for_=prefix + ".2",
            class_="element2",
        ),
        Element(
            "label",
            Element("span", "Element 4"),
            Element("input", id=prefix + ".3", value=question.elements[3] if question else ""),
            for_=prefix + ".3",
            class_="element3",
        ),
        Element(
            "label",
            Element("span", "Sequence Connection"),
            Element(
                "input",
                id=prefix + ".connection",
                value=question.connection if question else "",
            ),
            for_=prefix + ".connection",
            class_="connection",
        ),
        Element(
            "label",
            Element("span", "Details / Notes (only shown to game manager)"),
            Element(
                "textarea",
                question.details if question else "",
                id=prefix + ".details",
                rows="4",
            ),
            for_=prefix + ".details",
            class_="description",
        ),
        class_="panel oc-grid",
    )
