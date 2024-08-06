# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _f_annotations
from __future__ import annotations as _future_annotations

import logging

from aiohttp import web

from catbox.room import Endpoint, Room
from catbox.site.state import CatBoxContext
from catbox.static import DocResponse
from dom import Document, Element
from webapp import Request, ResponseProtocol

from .episode import OnlyConnectEpisode, OnlyConnectQuestion, SixQuestions


class OnlyConnectViewRoom(Room):
    episode: OnlyConnectEpisode

    def __init__(self, logger: logging.Logger, episode: OnlyConnectEpisode) -> None:
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

    async def on_join(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
        return DocResponse(Document(""))


class OnlyConnectEditRoom(Room):
    episode: OnlyConnectEpisode

    def __init__(self, logger: logging.Logger, episode: OnlyConnectEpisode) -> None:
        self.episode = episode
        super().__init__(
            logger,
            edit=OnlyConnectEditEndpoint(self),
            view=OnlyConnectViewEndpoint(self),
        )

    def __str__(self) -> str:
        return "Only Connect CMS"

    @property
    def default_endpoint(self) -> Endpoint:
        return self.endpoints["edit"]

    @property
    def starting_endpoint(self) -> Endpoint:
        return self.endpoints["edit"]


class OnlyConnectEditEndpoint(Endpoint):
    room: OnlyConnectEditRoom

    def __init__(self, room: OnlyConnectEditRoom) -> None:
        super().__init__(room)

    def __str__(self) -> str:
        return "CMS Edit View"

    async def on_join(self, ctx: CatBoxContext, request: Request) -> ResponseProtocol:
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
                    self.section_to_element(
                        self.room.episode.connections_round,
                        "Connections",
                        "Work out the connection",
                        "connections",
                    ),
                    self.section_to_element(
                        self.room.episode.completions_round,
                        "Completion",
                        "Complete the sequence (finding the fourth element)",
                        "completions",
                    ),
                    id="main",
                ),
            ),
            styles=["/defs.css", "/style.css", f"/{self.room.episode.engine_ident}/edit.css"],
            scripts=[f"/{self.room.episode.engine_ident}/edit.js"],
            socket=str(self._endpoint),
            class_="",
        )

        return DocResponse(doc)

    def question_to_element(self, question: OnlyConnectQuestion | None, prefix: str) -> Element:
        return Element(
            "fieldset",
            Element(
                "label",
                "Sequence Connection ",
                for_=prefix + ".connection",
                class_="connection",
            ),
            Element(
                "input",
                id=prefix + ".connection",
                value=question.connection if question else "",
                class_="connection",
            ),
            Element(
                "label",
                "Details / Notes",
                for_=prefix + ".details",
                class_="description",
            ),
            Element(
                "textarea",
                question.details if question else "",
                id=prefix + ".details",
                class_="description",
            ),
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
            class_="panel oc-grid",
        )

    def section_to_element(
        self, section: SixQuestions | None, title: str, description: str, prefix: str
    ) -> Element:
        return Element(
            "details",
            Element("summary", Element("h2", title, style="display: inline-block")),
            Element("p", description),
            Element(
                "fieldset",
                Element(
                    "legend",
                    Element(
                        "label",
                        Element("input", type="checkbox", checked="checked" if section else None, onclick=f"document.getElementById('{prefix}').toggleAttribute('disabled', !this.checked)"),
                        "Enable ",
                        title,
                        " round",
                    ),
                ),
                *(
                    self.question_to_element(q, prefix + ".q" + str(i))
                    for i, q in enumerate(section or [None] * 6)
                ),
                id=prefix,
                disabled=None if section else "disabled",
            ),
            class_="panel",
        )
