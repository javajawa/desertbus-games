from typing import Any

import pathlib
from abc import ABC, abstractmethod

from aiohttp import web


class Game(ABC):
    state: Any

    @classmethod
    @abstractmethod
    def description(cls) -> str:
        return str(cls)

    @classmethod
    @abstractmethod
    async def audit(cls) -> web.Response:
        pass

    def __init__(self, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def path(self, name: str) -> pathlib.Path:
        pass

    @abstractmethod
    def redirect(self) -> str:
        pass
