# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Iterable

import asyncio

from catbox.engine import EpisodeMeta, EpisodeState, EpisodeVersion
from catbox.engine.engine import GameEngine
from catbox.user import User
from dom import Document, Element


async def cms_index(engines: Iterable[GameEngine[EpisodeVersion]], user: User) -> Document:
    available: list[BaseException | Element] = await asyncio.gather(
        *(engine_index(engine, user) for engine in engines if engine.cms_enabled),
        return_exceptions=True,
    )
    title = f"CatBox Games - {user.user_name}'s Episodes"

    return Document(
        title,
        Element("header", Element("h1", title), class_="left-slant"),
        *[v.html if isinstance(v, Element) else str(v) for v in available],
        styles=["/defs.css", "/style.css"],
    )


async def engine_index(engine: GameEngine[EpisodeVersion], user: User) -> Element:
    return Element(
        "section",
        Element(
            "header",
            Element("h2", engine.name),
            Element("p", engine.description),
            class_="left-slant",
        ),
        Element(
            "main",
            create_new_episode_panel(engine),
            *(episode_panel(episode) for episode in engine.list_user_episodes(user)),
        ),
        class_="gl-game-list",
    )


def create_new_episode_panel(engine: GameEngine[EpisodeVersion]) -> Element:
    return Element(
        "article",
        Element("h3", "Create new ", engine.name, " episode"),
        Element("p", engine.description),
        Element(
            "a",
            "Create!",
            href=f"/cms/create/{engine.ident}",
            class_="button button-large",
        ),
        class_="panel gl-game-panel",
    )


def version_link(
    verb: str,
    episode: EpisodeMeta,
    version: int,
    text: str | None = None,
    title: str | None = None,
) -> Element:
    return Element(
        "a",
        text or verb.title(),
        href=f"/{verb}/{episode.engine_ident}/{episode.id}/{version}",
        class_="button",
        title=title or f"{verb.title()} version {version}",
    )


def episode_panel(episode: EpisodeMeta) -> Element:
    published = episode.version(EpisodeState.PUBLISHED)
    reviewing = episode.version(EpisodeState.PENDING_REVIEW)
    drafting = episode.version(EpisodeState.DRAFT)

    panel = Element(
        "article",
        Element("h3", episode.title),
        Element("p", episode.full_description, class_="usertext"),
        class_="panel gl-game-panel",
    )

    if published:
        panel.children.append(
            Element(
                "p",
                f"Published version {published}",
                version_link(
                    "play",
                    episode,
                    published,
                    title="Create a game from the current public version",
                ),
                version_link("view", episode, published, "View"),
                version_link(
                    "discord",
                    episode,
                    published,
                    "Remove",
                    title=(
                        "Remove this version from being published. "
                        "Your episode will no longer be available."
                    ),
                ),
            ),
        )
    else:
        panel.children.append(Element("p", "Not currently published."))

    if reviewing:
        panel.children.append(
            Element(
                "p",
                f"Version {reviewing} pending moderator review",
                version_link("view", episode, reviewing),
                version_link("edit", episode, reviewing) if not drafting else "",
            ),
        )

    if drafting:
        panel.children.append(
            Element(
                "p",
                f"Draft version {drafting}",
                version_link("edit", episode, drafting),
                (
                    version_link("discard", episode, drafting, title="Delete this draft.")
                    if reviewing
                    else ""
                ),
            ),
        )
    else:
        panel.children.append(
            Element(
                "p",
                "No draft version. ",
                version_link("edit", episode, 0, "Create new Version"),
            ),
        )

    if episode:
        panel.children.append(
            Element(
                "details",
                Element("summary", "All Versions"),
                *(
                    Element(
                        "p",
                        "Version ",
                        str(version),
                        ": ",
                        status,
                        ", updated ",
                        updated.isoformat(),
                        version_link("view", episode, version),
                        (
                            version_link("discard", episode, version)
                            if status != EpisodeState.DISCARDED
                            else ""
                        ),
                    )
                    for version, (status, updated) in episode
                ),
            ),
        )

    return panel


__all__ = ["cms_index"]
