# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import asyncio
import gzip
import hashlib
import mimetypes
import os
import pathlib
import re

import aiohttp.web
import asyncinotify
import brotli  # type: ignore[import-untyped]
import multidict
import rcssmin  # type: ignore[import-untyped]
import rjsmin  # type: ignore[import-untyped]

import dom
from webapp import ResponseProtocol

if TYPE_CHECKING:
    from catbox.site.state import CatBoxContext, CatBoxState, PublicEndpoint

_PRELOAD_REGEXP = re.compile(r'<link rel="preload" href="(.+)" as="(.+)">')
_DEFAULT_HTTPS_PORT = 443


def enable_optimisation(public: PublicEndpoint) -> None:
    StaticResponse.ENABLE_OPTIMISATION = True
    StaticResponse.PUBLIC_URL = (
        f"https://{public.host}/"
        if public.port == _DEFAULT_HTTPS_PORT
        else f"http://{public.host}:{public.port}/"
    )


class Content:
    headers: multidict.CIMultiDict[str]
    content: bytes

    def __init__(self, headers: dict[str, str], content: bytes) -> None:
        self.headers = multidict.CIMultiDict(headers)
        self.content = content


class StaticResponse:
    ENABLE_OPTIMISATION: bool = False
    PUBLIC_URL: str = ""

    _task: asyncio.Future[None]
    _watcher: asyncio.Task[None]
    _tag: str | None
    _versions: dict[str, Content]
    _headers: multidict.CIMultiDict[str]

    def __init__(
        self,
        context: CatBoxState,
        loop: asyncio.AbstractEventLoop,
        file: pathlib.Path,
        *,
        mime: str | None = None,
    ) -> None:
        self._tag = None
        self._versions = {}
        self._task = loop.run_in_executor(None, self._init_info, file, mime)

        if not self.ENABLE_OPTIMISATION:
            context.add_task(
                loop.create_task(self._watch(loop, file, mime), name=f"inotify[{file}]"),
            )

    def _init_info(self, file: pathlib.Path, mime: str | None) -> None:
        mime = mime or mimetypes.guess_type(str(file))[0] or "text/plain"

        with file.open("rb") as in_stream:
            content = in_stream.read()

        self._tag = self._tag or hashlib.sha1(content, usedforsecurity=False).hexdigest()
        base_headers = {
            "Content-Type": mime,
            "Cache-Control": (
                "public, max-age=3600, stale-if-error=86400"
                if self.ENABLE_OPTIMISATION
                else "max-age=0, nostore"
            ),
            "ETag": self._tag,
        }

        if self.ENABLE_OPTIMISATION and mime == "text/html":
            preloads = self.extract_preloads(content)
            if preloads:
                base_headers["Link"] = ", ".join(preloads)
        elif self.ENABLE_OPTIMISATION and mime == "text/javascript":
            content = rjsmin.jsmin(content)
        elif self.ENABLE_OPTIMISATION and mime == "text/css":
            content = rcssmin.cssmin(content)

        options = {"": content}

        if not mime.startswith(("image/", "video/")):
            base_headers["Vary"] = "accept-encoding"
            options = {
                "br": brotli.compress(content),
                "gzip": gzip.compress(content),
                "": content,
            }

        for mode, data in options.items():
            headers = {"Content-Encoding": mode, "Content-Length": str(len(data))}
            headers.update(base_headers)
            self._versions[mode] = Content(headers, data)

    def extract_preloads(self, content: bytes) -> list[str]:
        preloads = []
        for preload in _PRELOAD_REGEXP.finditer(content.decode("utf-8")):
            href = preload.group(1)
            if not href.startswith("http"):
                href = self.PUBLIC_URL + href.removeprefix("/")
            preloads.append(f"<{href}>; rel=preload; as={preload.group(2)}; crossorigin")
        return preloads

    async def _watch(
        self,
        loop: asyncio.AbstractEventLoop,
        file: pathlib.Path,
        mime: str | None,
    ) -> None:
        inotify = asyncinotify.Inotify()
        inotify.add_watch(file, asyncinotify.Mask.MODIFY)

        try:
            async for _ in inotify:
                loop.run_in_executor(None, self._init_info, file, mime)
        except asyncio.CancelledError:
            return

    async def prepare(self, request: aiohttp.web.Request) -> None:
        await self._task
        writer = request.writer

        if self._tag and self._tag in request.headers.getall("if-none-match", []):
            await writer.write_headers(
                _http_status_line(request, 304, "Not Modified"),
                multidict.CIMultiDict(),
            )
            await writer.write_eof()
            return

        accept_encoding = request.headers.get("Accept-Encoding", "")

        for encoding, content in self._versions.items():
            if encoding not in accept_encoding:
                continue

            await writer.write_headers(
                _http_status_line(request, 200, "Ok"),
                content.headers,
            )
            await writer.write_eof(content.content)

    async def write_eof(self, data: bytes = b"") -> None:
        pass

    @property
    def keep_alive(self) -> bool:
        return True

    def force_close(self) -> None:
        pass

    async def __call__(
        self,
        _: CatBoxContext,
        __: aiohttp.web.Request,
    ) -> ResponseProtocol:
        return self


class ImmutableFileResponse:
    _loop: asyncio.AbstractEventLoop
    _file: pathlib.Path
    _etag: str
    _mime: str

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        file: pathlib.Path,
        tag: str,
        mime: str | None = None,
    ) -> None:
        self._loop = loop
        self._file = file
        self._etag = tag
        self._mime = mime or mimetypes.guess_type(str(file))[0] or "text/plain"

    async def prepare(self, request: aiohttp.web.Request) -> None:
        writer = request.writer

        if self._etag == request.headers.get("if-none-match"):
            await writer.write_headers(
                _http_status_line(request, 304, "Not Modified"),
                multidict.CIMultiDict(),
            )
            await writer.write_eof()
            return

        if not self._file.exists():
            await writer.write_headers(
                _http_status_line(request, 404, "Not Found"),
                multidict.CIMultiDict(),
            )
            await writer.write_eof()
            return

        transport = request.transport
        if not transport:
            await writer.write_eof()
            return

        with self._file.open("rb") as fobj:
            headers = {
                "Content-Type": self._mime,
                "Content-Length": str(os.fstat(fobj.fileno()).st_size),
                "Cache-Control": "public, max-age=10368000, stale-if-error=10368000, immutable",
                "ETag": self._etag,
            }

            await writer.write_headers(
                _http_status_line(request, 200, "Ok"),
                multidict.CIMultiDict(headers),
            )
            await self._loop.sendfile(transport, fobj)
        await writer.write_eof()

    async def write_eof(self, data: bytes = b"") -> None:
        pass

    @property
    def keep_alive(self) -> bool:
        return True

    def force_close(self) -> None:
        pass


class DocResponse:
    _doc: dom.Document
    _status: int

    def __init__(self, document: dom.Document, status: int = 200) -> None:
        self._doc = document
        self._status = status

    async def prepare(self, request: aiohttp.web.Request) -> None:
        writer = request.writer

        content = self._doc.html.encode("utf-8")

        headers = {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "must-revalidate, no-cache, no-store, private",
        }

        if StaticResponse.ENABLE_OPTIMISATION:
            headers["Link"] = ", ".join(
                ["<https://fonts.gstatic.com>; rel=preconnect"]
                + [_preload_string(style, "style") for style in self._doc.styles]
                + [_preload_string(script, "script") for script in self._doc.scripts],
            )

        accept_encoding = request.headers.get("Accept-Encoding", "")
        if "br" in accept_encoding:
            content = brotli.compress(content)
            headers["Content-Encoding"] = "br"

        headers["Content-Length"] = str(len(content))

        await writer.write_headers(
            _http_status_line(request, self._status, ""),
            multidict.CIMultiDict(headers),
        )
        await writer.write_eof(content)

    async def write_eof(self, data: bytes = b"") -> None:
        pass

    @property
    def keep_alive(self) -> bool:
        return True

    def force_close(self) -> None:
        pass


def _http_status_line(request: aiohttp.web.Request, status: int, message: str) -> str:
    return f"HTTP/{request.version.major}.{request.version.minor} {status} {message}"


def _preload_string(href: str, as_type: str) -> str:
    if not href.startswith("http"):
        href = StaticResponse.PUBLIC_URL + href.removeprefix("/")

    return f'<{href}>; rel="prefetch"; as="{as_type}"; crossOrigin="anonymous"'
