# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import asyncio
import dataclasses
import hashlib
import json
import pathlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import lru
from aiohttp.web_exceptions import (
    HTTPCreated,
    HTTPNotAcceptable,
    HTTPNotFound,
    HTTPNotModified,
)
from PIL import Image, UnidentifiedImageError

from catbox.static import ImmutableFileResponse

if TYPE_CHECKING:
    from catbox.engine import JSONDict
    from webapp import Request, ResponseProtocol


@dataclasses.dataclass
class Blob:
    blob_id: str
    mimetype: str
    width: int
    height: int

    @property
    def url(self) -> str:
        return f"/blob/{self.blob_id}"

    def json(self) -> JSONDict:
        base = dataclasses.asdict(self)
        base["url"] = self.url
        return base


class BlobManager:
    _loop: asyncio.AbstractEventLoop
    _executor: ThreadPoolExecutor
    _connection: sqlite3.Connection
    _cursor: sqlite3.Cursor
    _response_cache: lru.LRU[str, ImmutableFileResponse]

    def __init__(self, loop: asyncio.AbstractEventLoop, database: sqlite3.Connection) -> None:
        self._loop = loop
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="blobs-")
        self._connection = database
        self._cursor = database.cursor()
        self._response_cache = lru.LRU(1024)

    def blob(self, blob_id: str) -> Blob | None:
        self._cursor.execute(
            "SELECT blob_id, mime, width, height FROM Blob WHERE blob_id = ?",
            (blob_id,),
        )
        data = self._cursor.fetchone()

        if not data:
            return None

        return Blob(*data)

    async def handle(self, request: Request) -> ResponseProtocol:
        if request.method == "POST" and request.path == "/blob":
            return await self._blob_upload(request)

        try:
            _, _, blob_id = request.path.split("/", 2)
        except ValueError:
            return HTTPNotFound()

        if not blob_id or "." in blob_id or "/" in blob_id:
            return HTTPNotFound()

        if blob_id in (tag.value for tag in request.if_match or []):
            return HTTPNotModified()

        if blob_id in self._response_cache:
            return self._response_cache[blob_id]

        path = pathlib.Path("blobs") / blob_id
        response = ImmutableFileResponse(asyncio.get_running_loop(), path, blob_id, "image/png")
        self._response_cache[blob_id] = response
        return response

    async def _blob_upload(self, request: Request) -> ResponseProtocol:
        content = await request.read()

        blob_id = hashlib.sha256(content, usedforsecurity=False).hexdigest()
        file = pathlib.Path("blobs") / blob_id
        exists = file.exists()

        if exists:
            return HTTPCreated(body=json.dumps({"id": blob_id}))

        try:
            image = await self._loop.run_in_executor(
                self._executor,
                lambda: Image.open(BytesIO(content)),
            )
        except UnidentifiedImageError as ex:
            return HTTPNotAcceptable(body=json.dumps(str(ex)))

        self._cursor.execute(
            "INSERT INTO Blob (blob_id, mime, width, height) VALUES (?, ?, ?, ?)",
            (blob_id, image.get_format_mimetype(), image.width, image.height),
        )

        with file.open("wb") as blob_file:
            blob_file.write(content)

        return HTTPCreated(body=json.dumps({"id": blob_id}))
