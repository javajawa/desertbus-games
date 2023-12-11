from __future__ import annotations

from typing import Any, Mapping

import dataclasses
import pathlib
from abc import ABC, abstractmethod

from db_games.dom import Element, Node


class GameEngine(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    def path(self, name: str) -> pathlib.Path:
        return pathlib.Path(__file__).parent / "resources" / name

    @abstractmethod
    async def available(self) -> Mapping[str, GameInfo]:
        pass

    @abstractmethod
    async def create(self, ident: str) -> Game:
        pass

    @abstractmethod
    async def audit(self, engine_slug: str, ident: str) -> Node:
        pass


@dataclasses.dataclass
class GameInfo:
    title: str
    credit: str
    description: str
    valid_teams: list[int]

    def game_list_panel(self, engine_slug: str, game_slug: str) -> Node:
        return Element(
            "article",
            Element("h3", self.title),
            Element("p", self.credit, class_="game-credit"),
            Element("p", self.description),
            Element(
                "ul",
                Element(
                    "li",
                    Element(
                        "a", "Audit Content", href=f"/audit/{engine_slug}/{game_slug}"
                    ),
                ),
                Element(
                    "li",
                    Element("a", "Play", href=f"/create/{engine_slug}/{game_slug}"),
                ),
            ),
            class_="gl-game-panel",
        )


class Game(ABC):
    state: Any

    def __init__(self, **kwargs: Any) -> None:
        pass

    def path(self, name: str) -> pathlib.Path:
        return pathlib.Path(__file__).parent / "resources" / name

    @abstractmethod
    def redirect(self) -> str:
        pass


@dataclasses.dataclass
class _IdMixin(ABC):  # pylint: disable=too-few-public-methods
    id: str
