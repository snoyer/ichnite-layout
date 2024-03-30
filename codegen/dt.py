from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence, Union, cast

NodeOrComment = Union["Node", "Comment"]


@dataclass
class Node:
    name: str
    children: list[NodeOrComment] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    label: Optional[str] = None
    address: Optional[int] = None
    comment: Optional[str] = None

    def format_dt(self):
        return "\n".join(format_dtnode(self))

    def __iadd__(self, node: Union[NodeOrComment, Iterable[NodeOrComment]]):
        if isinstance(node, (Node, Comment)):
            self.children.append(node)
        else:
            try:
                self.children += node
            except TypeError:
                raise ValueError(f"cannot add {node}")
        return self

    def __setitem__(self, k: str, v: Any):
        self.properties[k] = v


class PHandle(str):
    pass


class PHandles(list[str]):
    pass


class Raw(str):
    pass


class Comment(str):
    pass


def format_value(v: Any):
    if hasattr(v, "format_dt"):
        return v.format_dt()

    if isinstance(v, Raw):
        return str(v)

    if isinstance(v, PHandle):
        return str(v)

    if isinstance(v, int):
        return f"<{v}>" if v >= 0 else f"<({v})>"

    if isinstance(v, str):
        return f'"{v}"'

    return repr(v)


def format_dtproperty(k: str, v: Any):

    if hasattr(v, "format_dt"):
        return f"{k} = {v.format_dt()};"

    if isinstance(v, bool):
        if v is True:
            return f"{k};"
        else:
            return f"/* {k} = false */"

    if isinstance(v, str):
        return f"{k} = {format_value(v)};"

    if isinstance(v, Sequence):
        v = cast(Sequence[Any], v)
        return f'{k} = <{" ".join(map(format_value, v))}>;'

    return f"{k} = {format_value(v)};"


def format_dtnode(node: Node, depth: int = 0, indentation: str = "\t") -> Iterable[str]:
    def indent(line: str):
        return indentation * depth + line

    def indent_more(line: str):
        return indentation * (depth + 1) + line

    name = node.name
    if node.label:
        name = f"{node.label}: {name}"
    if node.address is not None:
        name += f"@{node.address:x}"

    if node.comment:
        comment_lines = f"/* {node.comment} */".splitlines()
        yield indent(name + " { " + comment_lines[0])
        yield from map(indent_more, comment_lines[1:])
    else:
        yield indent(name + " {")

    for name, value in node.properties.items():
        if value is not None:
            yield from map(indent_more, format_dtproperty(name, value).splitlines())

    for child in node.children:
        if isinstance(child, Node):
            yield from format_dtnode(child, depth + 1, indentation=indentation)
        else:
            comment_lines = f"/* {child} */".splitlines()
            yield from map(indent_more, comment_lines)

    yield indent("};")
