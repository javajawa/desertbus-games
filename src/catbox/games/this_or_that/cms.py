# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import logging
from collections import defaultdict

from aiohttp import web

from catbox.engine import EpisodeState, JSONDict
from catbox.room import Endpoint, Room, Socket, command
from catbox.site.state import CatBoxContext
from catbox.static import DocResponse
from dom import Document, Element
from webapp import Request, ResponseProtocol

from .question import ThisOrThatQuestion

if TYPE_CHECKING:
    from .engine import ThisOrThatEpisode, ThisOrThisEngine


class ThisOrThatPreviewRoom(Room):
    episode: ThisOrThatEpisode

    def __init__(
        self,
        logger: logging.Logger,
        episode: ThisOrThatEpisode,
    ) -> None:
        self.episode = episode
        super().__init__(logger, view=ThisOrThatPreview(self))

    def __str__(self) -> str:
        return f"ThisOrThat #{self.episode.id} Preview"

    @property
    def default_endpoint(self) -> Endpoint:
        return self.endpoints["view"]

    @property
    def starting_endpoint(self) -> Endpoint:
        return self.endpoints["view"]


class ThisOrThatPreview(Endpoint):
    room: ThisOrThatEditRoom | ThisOrThatPreviewRoom

    def __str__(self) -> str:
        return f"ThisOrThat #{self.room.episode.id} Preview"

    async def on_join(self, _: CatBoxContext, __: Request) -> ResponseProtocol:
        self.room.ping()
        episode = self.room.episode
        answers: dict[str, int] = defaultdict(int)
        articles: list[Element] = []

        for index, question in enumerate(episode.questions):
            answer = self.answer(episode, question)
            answers[answer] += 1
            articles.append(self.article(question, index, answer))

        doc = Document(
            episode.title,
            Element(
                "section",
                Element(
                    "header",
                    Element("h1", episode.title),
                    Element("p", episode.full_description, class_="usertext"),
                    Element("p", str(answers)),
                    class_="left-slant",
                ),
                Element("main", *articles, id="main"),
            ),
            styles=["/defs.css", "/style.css", f"/{self.room.episode.engine_ident}/edit.css"],
        )

        return DocResponse(doc)

    def answer(self, episode: ThisOrThatEpisode, question: ThisOrThatQuestion) -> str:
        if question.is_this and question.is_that:
            return "Both"
        if question.is_this:
            return episode.this_category
        if question.is_that:
            return episode.that_category

        return "Neither"

    def article(self, question: ThisOrThatQuestion, index: int, answer: str) -> Element:
        return Element(
            "article",
            Element("h3", f"Question {index}"),
            (
                Element("p", question.question_text, class_="usertext")
                if question.question_text
                else ""
            ),
            (
                Element("img", src=question.question_media.url, class_="preview")
                if question.question_media
                else ""
            ),
            Element("h4", "Answer: ", answer),
            Element("p", question.answer_text, class_="usertext") if question.answer_text else "",
            (
                Element("img", src=question.answer_media.url, class_="preview")
                if question.answer_media
                else ""
            ),
            class_=" ".join(
                [
                    "panel",
                    "invalid" if not question.is_valid else "",
                ],
            ),
        )


class ThisOrThatEditRoom(Room):
    engine: ThisOrThisEngine
    episode: ThisOrThatEpisode

    def __init__(
        self,
        logger: logging.Logger,
        engine: ThisOrThisEngine,
        episode: ThisOrThatEpisode,
    ) -> None:
        self.engine = engine
        self.episode = episode
        super().__init__(logger, edit=ThisOrThatEditor(self), view=ThisOrThatPreview(self))

    def __str__(self) -> str:
        return f"ThisOrThat #{self.episode.id} Edit Room"

    @property
    def default_endpoint(self) -> Endpoint:
        return self.endpoints["edit"]

    @property
    def starting_endpoint(self) -> Endpoint:
        return self.endpoints["edit"]


class ThisOrThatEditor(Endpoint):
    room: ThisOrThatEditRoom

    def __str__(self) -> str:
        return f"ThisOrThat #{self.room.episode.id} Editor"

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
                Element("main", id="main"),
            ),
            styles=["/defs.css", "/style.css", f"/{self.room.engine.ident}/edit.css"],
            scripts=[f"/{self.room.engine.ident}/edit.js"],
            socket=str(self._endpoint),
            class_="connecting",
        )

        return DocResponse(doc)

    async def fanout_state(self) -> None:
        await self._fanout(
            {
                "cmd": "update",
                "title": self.room.episode.title,
                "description": self.room.episode.description,
                **self.room.episode.json(),
            },
        )

    @command
    async def get(self, _: Socket) -> JSONDict:
        return {
            "cmd": "update",
            "title": self.room.episode.title,
            "description": self.room.episode.description,
            **self.room.episode.json(),
        }

    @command
    async def set_meta(  # noqa: PLR0913 beeegg call
        self,
        socket: Socket,
        title: str,
        description: str,
        this: str,
        that: str,
    ) -> None:
        self.room.episode.title = title
        self.room.episode.description = description
        self.room.episode.this_category = this
        self.room.episode.that_category = that
        await self.save(socket)

    @command
    async def new_question(self, _: Socket) -> None:
        self.room.episode.questions.append(ThisOrThatQuestion.new(self.room.engine))
        await self.fanout_state()

    @command
    async def update(self, socket: Socket, uuid: str, **kwargs: str | bool | None) -> None:
        target = self.room.episode.questions.index(ThisOrThatQuestion(self.room.engine, uuid=uuid))
        self.room.episode.questions[target] = ThisOrThatQuestion(
            self.room.engine,
            uuid=uuid,
            **kwargs,  # type: ignore[arg-type]
        )
        await self.save(socket)

    @command
    async def reorder(self, socket: Socket, order: list[str]) -> None:
        output = []

        for uuid in order:
            index = self.room.episode.questions.index(
                ThisOrThatQuestion(self.room.engine, uuid=uuid),
            )
            output.append(
                (
                    self.room.episode.questions[index]
                    if index
                    else ThisOrThatQuestion(self.room.engine, uuid=uuid)
                ),
            )

        self.room.episode.questions = output
        await self.save(socket)

    @command
    async def delete_question(self, socket: Socket, uuid: str) -> None:
        self.room.episode.questions.remove(ThisOrThatQuestion(self.room.engine, uuid=uuid))
        await self.save(socket)

    @command
    async def save(self, _: Socket) -> None:
        self.room.engine.save(self.room.episode)
        await self.fanout_state()

    @command
    async def submit(self, _: Socket) -> None:
        self.room.engine.save(self.room.episode)
        self.room.engine.save_state(self.room.episode, EpisodeState.PENDING_REVIEW)
        await self.room.stop()
