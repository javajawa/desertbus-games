from __future__ import annotations

from typing import Any

import dataclasses
import pathlib
from abc import ABC, abstractmethod

from aiohttp import web


class GameEngine(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    async def available(self) -> dict[str, GameInfo]:
        pass

    @abstractmethod
    async def create(self, ident: str) -> Game:
        pass

    @abstractmethod
    async def audit(self, ident: str) -> web.Response:
        pass


@dataclasses.dataclass
class GameInfo:
    title: str
    credits: str
    description: str
    valid_teams: list[int]

    def html(self, engine_slug: str, game_slug: str) -> str:
        return (
            f'<article class="gl-game-panel">'
            f"<h3>{self.title}</h3>"
            f"<p class='gl-credit'>{self.credits}</p>"
            f"<p>{self.description}</p>"
            f"<ul>"
            f'<li><a href="/audit/{engine_slug}/{game_slug}">Audit Content</a></li>'
            f'<li><a href="create/{engine_slug}/{game_slug}">Play</a></li>'
            f"</ul></article>"
        )


class Game(ABC):
    state: Any

    def __init__(self, **kwargs: Any) -> None:
        pass

    @classmethod
    @abstractmethod
    def description(cls) -> str:
        pass

    @abstractmethod
    def path(self, name: str) -> pathlib.Path:
        pass

    @abstractmethod
    def redirect(self) -> str:
        pass


class _IdMixin(ABC):  # pylint: disable=too-few-public-methods
    id: str
