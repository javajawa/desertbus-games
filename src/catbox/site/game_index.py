# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Iterable

import asyncio

from catbox.engine import EpisodeState, EpisodeVersion
from catbox.engine.engine import GameEngine, OptionSupport
from dom import Document, Element


async def game_index(engines: Iterable[GameEngine[EpisodeVersion]]) -> Document:
    available = await asyncio.gather(*(engine_index(engine) for engine in engines))

    return Document(
        "CatBox Games",
        Element("header", Element("h1", "CatBox Games"), class_="left-slant"),
        *available,
        styles=["/defs.css", "/style.css"],
    )


async def engine_index(engine: GameEngine[EpisodeVersion]) -> Element:
    rule_summary = "Game rules: "

    match engine.scoring_mode:
        case OptionSupport.NOT_SUPPORTED:
            rule_summary += "no teams, no scoring"
        case OptionSupport.REQUIRED:
            rule_summary += f"1-{engine.max_teams} teams"
        case OptionSupport.OPTIONAL:
            rule_summary += f"optional scoring for 1-{engine.max_teams} teams"

    match engine.scoring_mode:
        case OptionSupport.REQUIRED:
            rule_summary += ", with audience"
        case OptionSupport.OPTIONAL:
            rule_summary += ", with optional audience"

    return Element(
        "section",
        Element(
            "header",
            Element("h2", engine.name),
            Element("p", engine.description),
            Element("p", rule_summary),
            class_="left-slant",
        ),
        Element(
            "main",
            *(episode_panel(episode) for episode in engine.list_episodes(EpisodeState.PUBLISHED)),
        ),
        class_="gl-game-list",
    )


def episode_panel(episode: EpisodeVersion) -> Element:
    return Element(
        "article",
        Element("h3", episode.title),
        Element("p", episode.author, class_="game-credit"),
        Element("p", episode.full_description, class_="usertext"),
        Element(
            "p",
            Element(
                "a",
                "Play",
                href=f"/play/{episode.engine_ident}/{episode.id}/{episode.version}",
                class_="button",
            ),
            Element(
                "a",
                "Audit Content",
                href=f"/view/{episode.engine_ident}/{episode.id}",
                class_="button",
            ),
        ),
        class_="panel gl-game-panel",
    )


__all__ = ["game_index"]
