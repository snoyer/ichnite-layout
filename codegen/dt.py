from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Union

NodeOrComment = Union['Node','Comment']

@dataclass
class Node:
    name: str
    children: List[NodeOrComment] = field(default_factory=list)
    properties: Dict[str,Any] = field(default_factory=dict)
    label: Optional[str] = None
    address: Optional[int] = None
    comment: Optional[str] = None

    def __str__(self):
        return '\n'.join(format_dtnode(self))

    def __iadd__(self, node: Union[NodeOrComment, Iterable[NodeOrComment]]):
        if isinstance(node, NodeOrComment):
            self.children.append(node)
        else:
            try:
                self.children += node
            except TypeError:
                raise ValueError(f'cannot add {node}')
        return self

    def __setitem__(self, k: str, v: Any):
        self.properties[k] = v


class PHandle(str): pass
class PHandles(List[str]): pass
class Raw(str): pass
class Comment(str): pass


def format_dtproperty(k: str, v: Any):
    if isinstance(v, Raw):
        return f'{k} = {v};'

    if isinstance(v, PHandle):
        return f'{k} = <{v}>;'

    if isinstance(v, PHandles):
        return f'{k} = <{" ".join(v)}>;'



    if isinstance(v, bool):
        if v == True:
            return f'{k};'
        else:
            return f'/* {k} = false */';
    if isinstance(v, int):
        return f'{k} = <{v}>;'
    if isinstance(v, str):
        return f'{k} = "{v}";'

    return f'{k} = {v};'



def format_dtnode(node: Node, depth: int=0, indentation: str='\t') -> Iterable[str]:
    def indent     (line: str): return indentation* depth    + line
    def indent_more(line: str): return indentation*(depth+1) + line

    name = node.name
    if node.label:
        name = node.label + ': ' + name
    if node.address != None:
        name += '@%x' % node.address
     
    if node.comment:
        comment_lines = f'/* {node.comment} */'.splitlines()
        yield indent(name + ' { ' + comment_lines[0])
        yield from map(indent_more, comment_lines[1:])
    else:
        yield indent(name + ' {')

    for name,value in node.properties.items():
        if value != None:
            yield from map(indent_more, format_dtproperty(name, value).splitlines())

    for child in node.children:
        if isinstance(child, Node):
            yield from format_dtnode(child, depth+1, indentation=indentation)
        else:
            comment_lines = f'/* {child} */'.splitlines()
            yield from map(indent_more, comment_lines)

    yield indent('};')
