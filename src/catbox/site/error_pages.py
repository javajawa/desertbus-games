# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from catbox.static import DocResponse
from dom import Document, Element


class HTTPNotFoundError(DocResponse, Exception):
    def __init__(self, reason: str = "") -> None:
        super().__init__(doc("Page not found ", reason), status=404)


class HTTPInternalServerError(DocResponse, Exception):
    def __init__(self, reason: str = "") -> None:
        super().__init__(doc("We encountered an issue: ", reason), status=503)


class HTTPUnauthorizedError(DocResponse, Exception):
    def __init__(self, reason: str = "") -> None:
        super().__init__(
            doc("You are not authorized to access this page: ", reason),
            status=404,
        )


def doc(*body: str) -> Document:
    return Document(
        "CatBox - Error",
        Element(
            "header",
            Element("a", Element("h1", "🏠 CatBox Games"), href="/"),
            class_="left-slant",
        ),
        Element(
            "main",
            Element("article", *body, class_="panel"),
            Element(
                "article",
                Element(
                    "ul",
                    Element("li", Element("a", "CatBox Home", href="/")),
                    Element("li", Element("a", "Content Management Home", href="/cms")),
                ),
                class_="panel",
            ),
        ),
        styles=["/defs.css", "/style.css"],
    )
