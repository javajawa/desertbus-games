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
    @property
    def html(self) -> str:
        return self


class Element(Node):  # pylint: disable=too-few-public-methods
    element: str
    attributes: dict[str, str]
    children: list[Node]

    def __init__(self, element: str, *children: Node | str, **attributes: str) -> None:
        self.element = element
        self.attributes = attributes
        self.children = [x if isinstance(x, Node) else TextNode(x) for x in children]

    @property
    def html(self) -> str:
        attributes = [
            f' {key.strip("_")}="{value}"' for key, value in self.attributes.items()
        ]

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

    def __init__(
        self,
        title: str,
        *elements: Node | str,
        styles: list[str] | None = None,
        scripts: list[str] | None = None,
    ) -> None:
        self.title = title
        self.styles = list(styles or [])
        self.scripts = list(scripts or [])
        self.children = [x if isinstance(x, Node) else TextNode(x) for x in elements]

    @property
    def html(self) -> str:
        styles = "".join(
            f'<link rel="stylesheet" href="{style}">' for style in self.styles
        )
        scripts = "".join(
            f'<script async defer src="{script}">' for script in self.scripts
        )
        content = "".join(x.html for x in self.children)

        return (
            "<!DOCTYPE html>"
            '<html lang="en">'
            f'<head><meta charset="utf-8"><title>{self.title}</title>{styles}{scripts}</head>'
            f"<body>{content}</body>"
            "</html>"
        )
