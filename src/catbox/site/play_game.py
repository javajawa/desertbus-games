# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from catbox.engine import EpisodeVersion, GameEngine, OptionSupport
from catbox.room import RoomOptions
from catbox.static import DocResponse
from dom import Document, Element, Node, NodeList
from webapp import Request, ResponseProtocol


def setup_page(engine: GameEngine[EpisodeVersion], episode: EpisodeVersion) -> ResponseProtocol:
    return DocResponse(
        Document(
            f"Create Room - {episode.title}",
            Element(
                "section",
                Element(
                    "header",
                    Element("h1", f"Create Room - {episode.title}"),
                    class_="left-slant",
                ),
                Element(
                    "main",
                    Element(
                        "form",
                        Element("h2", "Game Options"),
                        _scoring_box(engine),
                        _audience_box(engine),
                        Element("input", type="submit", value="Play", class_="button button-large"),
                        method="POST",
                    ),
                    class_="panel",
                ),
            ),
            styles=["/defs.css", "/style.css"],
        ),
    )


def _scoring_box(engine: GameEngine[EpisodeVersion]) -> Node:
    if engine.scoring_mode == OptionSupport.NOT_SUPPORTED:
        return Element("ul", Element("li", "Scoring + Teams are not supported."))

    return NodeList(
        Element(
            "fieldset",
            Element(
                "Legend",
                Element(
                    "label",
                    Element(
                        "input",
                        type="checkbox",
                        id="scoring",
                        name="scoring",
                        checked="checked",
                        disabled=(
                            "disabled" if engine.scoring_mode == OptionSupport.REQUIRED else None
                        ),
                    ),
                    "Enable Scoring",
                ),
            ),
            Element("h3", "Team Names"),
            *(
                Element(
                    "label",
                    "Team ",
                    str(i + 1),
                    Element("input", type="text", id=f"team-{i}", name="team"),
                    for_=f"team-{i}",
                )
                for i in range(engine.max_teams)
            ),
            id="teams",
        ),
        Element(
            "script",
            "const tog = document.getElementById('scoring');"
            "const target = document.getElementById('teams');"
            "tog.addEventListener('change',()=>target.toggleAttribute('disabled',!tog.checked));",
        ),
    )


def _audience_box(engine: GameEngine[EpisodeVersion]) -> Node:
    if engine.supports_audience == OptionSupport.NOT_SUPPORTED:
        return Element("ul", Element("li", "Audience/Chat is not supported."))

    return Element(
        "fieldset",
        Element("legend", "Audience / Chat"),
        Element(
            "label",
            Element("input", type_="checkbox", id="audience", name="audience", checked="checked"),
            "Enable Audience/Chat",
            for_="audience",
        ),
    )


async def process_options(engine: GameEngine[EpisodeVersion], request: Request) -> RoomOptions:
    post_data = await request.post()

    if engine.scoring_mode == OptionSupport.REQUIRED:
        scoring = True
    elif engine.scoring_mode == OptionSupport.NOT_SUPPORTED:
        scoring = False
    else:
        scoring = post_data.get("scoring", None) == "on"

    if engine.supports_audience == OptionSupport.REQUIRED:
        audience = True
    elif engine.supports_audience == OptionSupport.NOT_SUPPORTED:
        audience = False
    else:
        audience = post_data.get("audience", None) == "on"

    if scoring:
        raw_teams = post_data.getall("team", [])
        teams = [str(name) for name in raw_teams if name]
        if not teams:
            teams = ["Players"]
    else:
        teams = []

    return RoomOptions(
        scoring=scoring,
        teams=teams,
        audience=audience,
    )
