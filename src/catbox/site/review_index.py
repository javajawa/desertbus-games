# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Iterable

import asyncio

from catbox.engine import EpisodeMeta, EpisodeState, EpisodeVersion
from catbox.engine.engine import GameEngine
from dom import Document, Element


async def review_index(engines: Iterable[GameEngine[EpisodeVersion]]) -> Document:
    available = await asyncio.gather(*(engine_index(engine) for engine in engines))

    if not any(bool(block) for block in available):
        available = [
            Element(
                "section",
                Element("main", "Nothing pending review"),
                class_="gl-game-list",
            ),
        ]

    return Document(
        "CatBox Games - Pending Moderation",
        Element(
            "header",
            Element("h1", "CatBox Games - Episodes Pending Moderation"),
            class_="left-slant",
        ),
        *available,
        styles=["/defs.css", "/style.css"],
    )


async def engine_index(engine: GameEngine[EpisodeVersion]) -> Element | str:
    panels = [
        panel(episode, engine.get_episode_meta(episode.id))
        for episode in engine.list_episodes(EpisodeState.PENDING_REVIEW)
    ]

    if not panels:
        return ""

    return Element(
        "section",
        Element(
            "header",
            Element("h2", engine.name),
            Element("p", engine.description),
            class_="left-slant",
        ),
        Element("main", *panels),
        class_="gl-game-list",
    )


def panel(episode: EpisodeVersion, meta: EpisodeMeta | None) -> Element:
    published = "Unknown"
    if meta:
        published = str(meta.version(EpisodeState.PUBLISHED))

    return Element(
        "article",
        Element("h3", episode.title, " - Version ", str(episode.version)),
        Element("p", episode.author, class_="game-credit"),
        Element("p", "Current Published Version: ", published),
        Element("p", episode.full_description, class_="usertext"),
        Element(
            "p",
            Element(
                "a",
                "Audit Content",
                href=f"/view/{episode.engine_ident}/{episode.id}/{episode.version}",
                class_="button",
            ),
            Element(
                "a",
                "Approve",
                class_="button",
                href=f"/approve/{episode.engine_ident}/{episode.id}/{episode.version}",
            ),
            Element(
                "a",
                "Reject",
                class_="button",
                href=f"/reject/{episode.engine_ident}/{episode.id}/{episode.version}",
            ),
        ),
        class_="panel gl-game-panel",
    )


def approved(episode: EpisodeVersion) -> Document:
    return Document(
        "CatBox Games - Approved",
        Element("header", Element("h2", "CatBox Games - Approved"), class_="left-slant"),
        Element(
            "main",
            Element(
                "div",
                Element("p", f"Version {episode.version} of {episode.title} has been approved!"),
                Element(
                    "p",
                    Element("a", "Back to Review", href="/review", class_="button"),
                    Element(
                        "a",
                        "Play Now",
                        href=f"/play/{episode.engine_ident}/{episode.id}/{episode.version}",
                        class_="button",
                    ),
                ),
            ),
        ),
        styles=["/defs.css", "/style.css"],
    )


__all__ = ["review_index", "approved"]
