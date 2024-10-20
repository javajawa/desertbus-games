# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import asyncio
import logging

from aiohttp import web

from catbox.blob import Blob
from catbox.engine import EpisodeState, JSONDict
from catbox.room import Endpoint, Room, Socket, command, command_no_log
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
        return self.endpoints["view"]

    @property
    def starting_endpoint(self) -> Endpoint:
        return self.endpoints["view"]


class OnlyConnectViewEndpoint(Endpoint):
    room: OnlyConnectViewRoom | OnlyConnectEditRoom

    def __init__(self, room: OnlyConnectViewRoom | OnlyConnectEditRoom) -> None:
        super().__init__(room)

    def __str__(self) -> str:
        return "CMS (Re)View"

    async def on_join(self, _: CatBoxContext, __: Request) -> ResponseProtocol:
        return DocResponse(
            Document(
                f'Preview: "{self.room.episode.title}"',
                Element(
                    "main",
                    Element(
                        "header",
                        Element("h1", f'"{self.room.episode.title}"'),
                        class_="left-slant",
                    ),
                    Element(
                        "article",
                        Element("div", self.room.episode.full_description, class_="usertext"),
                        class_="panel",
                    ),
                    section_to_element(
                        self.room.episode.connections_round,
                        "Connections",
                        "Work out the connection",
                        "connections",
                        editable=False,
                    ),
                    section_to_element(
                        self.room.episode.completions_round,
                        "Completions",
                        "Complete the sequence (finding the fourth element)",
                        "completions",
                        editable=False,
                    ),
                    walls_to_element(self.room.episode.connecting_walls, editable=False),
                    missing_vowels_to_element(self.room.episode.missing_vowels, editable=False),
                    id="main",
                ),
                styles=["/defs.css", "/style.css", f"/{self.room.episode.engine_ident}/edit.css"],
            ),
        )


class FullEpisodeHelper:
    connections_round: SixQuestions
    completions_round: SixQuestions
    connecting_walls: tuple[ConnectingWall, ConnectingWall]
    missing_vowels: list[MissingVowelsGroup | None]

    def __init__(self, episode: OnlyConnectEpisode) -> None:
        self.connections_round = episode.connections_round or SixQuestions.default()
        self.completions_round = episode.completions_round or SixQuestions.default()
        self.connecting_walls = episode.connecting_walls or (
            ConnectingWall.default(),
            ConnectingWall.default(),
        )
        if episode.missing_vowels is not None:
            self.missing_vowels = episode.missing_vowels
        else:
            self.missing_vowels = []


class OnlyConnectEditRoom(Room):
    episode: OnlyConnectEpisode
    episode_but_enabled: FullEpisodeHelper

    engine: OnlyConnectEngine

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
        self.engine = engine

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
        self.engine.save(self.episode)

    def submit(self) -> None:
        self.engine.save_state(self.episode, EpisodeState.PENDING_REVIEW)

    @property
    def default_endpoint(self) -> Endpoint:
        return self.endpoints["edit"]

    @property
    def starting_endpoint(self) -> Endpoint:
        return self.endpoints["edit"]

    def queue_save(self) -> None:
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
                self.engine.save(self.episode)
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
                    Element(
                        "article",
                        Element("h2", "Game Info"),
                        Element(
                            "label",
                            "Title: ",
                            Element("input", value=self.room.episode.title, id="title"),
                            for_="title",
                        ),
                        Element(
                            "label",
                            "Description:",
                            Element(
                                "textarea",
                                self.room.episode.description,
                                id="description",
                                rows="4",
                            ),
                            for_="description",
                        ),
                        Element(
                            "button",
                            "Save + Submit for Review",
                            id="submit",
                            class_="button button-large",
                        ),
                        class_="panel",
                    ),
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
                    missing_vowels_to_element(self.room.episode.missing_vowels),
                    id="main",
                ),
            ),
            styles=["/defs.css", "/style.css", f"/{self.room.episode.engine_ident}/edit.css"],
            scripts=[f"/{self.room.episode.engine_ident}/edit.js"],
            socket=str(self._endpoint),
            class_="connecting",
        )

        return DocResponse(doc)

    async def on_close(self, socket: Socket) -> None:
        await super().on_close(socket)

        if socket in self.editing:
            self.editing.pop(socket)
            await self.announce_editing(None, None)

    @command
    async def init(self, socket: Socket) -> JSONDict:
        await self.announce_editing(socket, None)
        return {"cmd": "update", **self.room.episode.json()}

    @command
    async def set_meta(self, _: Socket, title: str, description: str) -> None:
        self.room.episode.title = title
        self.room.episode.description = description
        self.room.queue_save()

    @command
    async def submit(self, _: Socket) -> None:
        await self.room.stop()
        self.room.submit()

    @command_no_log
    async def announce_editing(self, socket: Socket | None, element: str | None) -> None:
        if socket is not None:
            self.editing[socket] = element

        await self._fanout(
            {
                "cmd": "editing",
                "positions": [  # type: ignore[dict-item] # JSON typing is hard
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
        elif section == "missing_vowels":
            self._update_missing_vowels(socket, question, element, value)
            self.room.queue_save()
            await self._fanout({"cmd": "update", **self.room.episode.json()})
            return
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
        if element == "media":
            question.question_type = "media" if value else "text"
            return True

        try:
            element_number = range_number(element, 0, 4)
        except ValueError:
            self._error("Attempting to edit invalid element %s", element, socket=socket)
            return False

        if value.startswith("blob::"):
            blob = self.room.engine.blob_for_id(value.removeprefix("blob::"))
            if blob:
                question.elements[element_number] = blob
        else:
            question.elements[element_number] = value

        return True

    def _update_missing_vowels(  # noqa: PLR0911  # pylint: disable=R0911
        self,
        socket: Socket,
        question: str,
        element: str,
        value: str,
    ) -> None:
        groups = self.room.episode_but_enabled.missing_vowels

        if question == "new":
            groups.append(MissingVowelsGroup("", []))
            return

        try:
            group_number = range_number(question, 0, len(groups))
        except ValueError:
            self._error(
                "Attempting to edit out-of-range missing values group %s",
                question,
                socket=socket,
            )
            return

        group = groups[group_number]
        if not group:
            return

        if element == "connection":
            group.connection = value
            return
        if element == "new":
            group.words.append((value, MissingVowelsGroup.generate_prompt(value)))
            return

        is_prompt = element.endswith("-prompt")

        try:
            question_number = range_number(element.removesuffix("-prompt"), 0, len(group.words))
        except ValueError:
            self._error(
                "Attempting to edit invalid element %s in group %s",
                element,
                str(group_number),
                socket=socket,
            )
            return

        if not is_prompt and not value:
            group.words[question_number] = None
            return

        previous = group.words[question_number] or ("", "")
        group.words[question_number] = (
            previous[0] if is_prompt else value,
            value if is_prompt else previous[1],
        )


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
    *,
    editable: bool = True,
) -> Element:
    disabled = "disabled" if not editable else None

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
                    Element(
                        "input",
                        type="checkbox",
                        checked="checked" if section else None,
                        disabled=disabled,
                    ),
                    "Enable ",
                    title,
                    " round",
                ),
            ),
            *(
                question_to_element(
                    q,
                    prefix + "." + str(i),
                    title + " #" + str(i + 1),
                    disabled,
                    media_permitted=True,
                )
                for i, q in enumerate(section or [None] * 6)
            ),
            id=prefix,
            disabled=None if section else "disabled",
        ),
        class_="panel",
        open="open",
    )


def walls_to_element(
    _walls: tuple[ConnectingWall, ConnectingWall] | None,
    *,
    editable: bool = True,
) -> Element:
    enabled = _walls is not None
    walls = _walls or ((None, None, None, None), (None, None, None, None))
    disabled = "disabled" if not editable else None

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
                    question_to_element(question, f"wall0.{i}", f"Wall A - Group {i+1}", disabled)
                    for i, question in enumerate(walls[0])
                ),
            ),
            Element(
                "fieldset",
                Element("h3", "Wall B"),
                *(
                    question_to_element(question, f"wall1.{i}", f"Wall B - Group {i+1}", disabled)
                    for i, question in enumerate(walls[1])
                ),
            ),
            id="connecting_walls",
            disabled=None if enabled else "disabled",
        ),
        class_="panel",
        open="open",
    )


def question_to_element(
    question: OnlyConnectQuestion | None,
    prefix: str,
    title: str,
    disabled: str | None,
    *,
    media_permitted: bool = True,
) -> Element:
    return Element(
        "fieldset",
        Element("h3", title, class_="conn-title"),
        (
            Element(
                "label",
                Element(
                    "input",
                    id=prefix + ".media",
                    type="checkbox",
                    checked="checked" if question and question.question_type == "media" else None,
                ),
                "Media question",
            )
            if media_permitted
            else ""
        ),
        clue_to_element(question, prefix, 0, disabled),
        clue_to_element(question, prefix, 1, disabled),
        clue_to_element(question, prefix, 2, disabled),
        clue_to_element(question, prefix, 3, disabled),
        Element(
            "label",
            Element("span", "Sequence Connection"),
            Element(
                "input",
                id=prefix + ".connection",
                value=question.connection if question else "",
                disabled=disabled,
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
                disabled=disabled,
            ),
            for_=prefix + ".details",
            class_="description",
        ),
        class_="panel oc-grid type_" + (question.question_type if question else "text"),
        id=prefix,
    )


def clue_to_element(
    question: OnlyConnectQuestion | None,
    prefix: str,
    idx: int,
    disabled: str | None,
) -> Element:
    clue = question.elements[idx] if question else None
    clue_text: str = clue if isinstance(clue, str) else ""
    clue_blob: Blob | None = clue if isinstance(clue, Blob) else None

    return Element(
        "label",
        Element("span", "Element ", str(idx + 1)),
        Element(
            "input",
            id=prefix + "." + str(idx),
            value=clue_text,
            disabled=disabled,
            class_="type_text",
        ),
        Element(
            "input",
            id=prefix + ".m" + str(idx),
            type="file",
            disabled=disabled,
            class_="type_media",
        ),
        Element(
            "img",
            id=prefix + "." + str(idx) + "-preview",
            href=clue_blob.url if clue_blob else "",
            class_="type_media",
        ),
        for_=prefix + "." + str(idx),
        class_="element" + str(idx),
    )


def missing_vowels_to_element(
    missing_vowels: list[MissingVowelsGroup | None] | None,
    *,
    editable: bool = True,
) -> Element:
    enabled = missing_vowels is not None

    return Element(
        "details",
        Element("summary", Element("h2", "Missing Vowels")),
        Element(
            "p",
            "word word words.",
        ),
        Element(
            "fieldset",
            Element(
                "legend",
                Element(
                    "label",
                    Element(
                        "input",
                        type="checkbox",
                        checked="checked" if enabled else None,
                        disabled=None if editable else "disabled",
                    ),
                    "Enable Missing Vowels",
                ),
            ),
            *(
                missing_vowels_group_to_element(group, f"missing_vowels.{idx}", editable=editable)
                for idx, group in enumerate(missing_vowels or [])
                if group is not None
            ),
            (
                Element("button", "Add Group", id="missing_vowel_new_group", class_="button")
                if editable
                else ""
            ),
            id="missing_vowels",
            disabled="disabled" if not enabled else None,
        ),
        class_="panel",
        open="open",
    )


def missing_vowels_group_to_element(
    missing_vowels: MissingVowelsGroup,
    prefix: str,
    *,
    editable: bool = True,
) -> Element:
    return Element(
        "fieldset",
        Element(
            "label",
            Element("span", "Connection:"),
            Element(
                "input",
                id=f"{prefix}.connection",
                value=missing_vowels.connection,
                disabled=None if editable else "disabled",
            ),
            for_=f"{prefix}.connection",
        ),
        *(
            Element(
                "label",
                Element(
                    "input",
                    id=f"{prefix}.{idx}-prompt",
                    value=question,
                    pattern=missing_vowels.regexp(answer),
                    disabled=None if editable else "disabled",
                ),
                Element("span", " ⇒ "),
                Element(
                    "input",
                    id=f"{prefix}.{idx}",
                    value=answer,
                    disabled=None if editable else "disabled",
                ),
                row=str(idx),
                for_=f"{prefix}.{idx}",
            )
            for idx, answer, question, valid in missing_vowels.pairs
        ),
        (
            Element(
                "label",
                "New Entry: ",
                Element("input", id=f"{prefix}.new.0"),
                for_=f"{prefix}.new.0",
                class_="new",
            )
            if editable
            else ""
        ),
        id=prefix,
    )
