# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import abc


class Node(abc.ABC):
    @property
    @abc.abstractmethod
    def html(self) -> str:
        pass

    def __str__(self) -> str:
        return self.__str__()


class NodeList(Node):  # pylint: disable=too-few-public-methods
    nodes: tuple[Node, ...]

    def __init__(self, *nodes: Node) -> None:
        self.nodes = nodes

    @property
    def html(self) -> str:
        return "".join(node.html for node in self.nodes)


class TextNode(Node, str):
    __slots__ = ()

    @property
    def html(self) -> str:
        return self


class Element(Node):  # pylint: disable=too-few-public-methods
    element: str
    attributes: dict[str, str | None]
    children: list[Node]

    def __init__(self, element: str, *children: Node | str, **attributes: str | None) -> None:
        self.element = element
        self.attributes = attributes
        self.children = [x if isinstance(x, Node) else TextNode(x) for x in children]

    @property
    def html(self) -> str:
        attributes = (
            f' {key.strip("_")}="{value}"' for key, value in self.attributes.items() if value
        )

        return (
            f"<{self.element}{''.join(attributes)}>"
            f"{''.join(x.html for x in self.children)}"
            f"</{self.element}>"
        )


class Document(Node):  # pylint: disable=too-few-public-methods
    title: str
    styles: list[str]
    scripts: list[str]
    children: list[Node]
    attributes: dict[str, str]

    def __init__(
        self,
        title: str,
        *elements: Node | str,
        styles: list[str] | None = None,
        scripts: list[str] | None = None,
        **attributes: str,
    ) -> None:
        self.title = title
        self.styles = list(styles or [])
        self.scripts = list(scripts or [])
        self.children = [x if isinstance(x, Node) else TextNode(x) for x in elements]
        self.attributes = {k.strip("_"): v for k, v in attributes.items()}

    @property
    def html(self) -> str:
        attributes = [f' {key.strip("_")}="{value}"' for key, value in self.attributes.items()]
        styles = "".join(f'<link rel="stylesheet" href="{style}">' for style in self.styles)
        scripts = "".join(
            f'<script type="module" async defer src="{script}"></script>' for script in self.scripts
        )
        content = "".join(x.html for x in self.children)

        return (
            "<!DOCTYPE html>"
            '<html lang="en">'
            f'<head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{self.title}</title>{styles}{scripts}</head>"
            f"<body{''.join(attributes)}>{content}</body>"
            "</html>"
        )
