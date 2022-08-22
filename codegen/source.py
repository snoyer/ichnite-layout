
from dataclasses import dataclass, replace
from genericpath import commonprefix
from itertools import count
import re
from typing import (Any, Callable, Dict, Generic, Iterable, List, Sequence,
                    Tuple, TypeVar, Union)


from tables import Table, cjust, format_boxed_table


NUMROW = r'''1! 2@ 3# 4$ 5% 6^ 7& 8* 9( 0) -_ =+ [{ ]} ;: '" ,< .> /? \| `~'''.split()
SHIFTED = {k: v for k, v in NUMROW}
UNSHIFTED = {v: k for k, v in NUMROW}


@dataclass
class HoldTap:
    tap: str
    hold: str

    def __str__(self):
        return f'{self.tap} ⇩{self.hold}'

    def replace(self, **kwargs: Dict[str, str]):
        return replace(self, **kwargs)


class ModTap(HoldTap):
    pass


class LayerTap(HoldTap):
    @property
    def layer(self):
        return self.hold


@dataclass
class ToLayer:
    layer: str

    def __str__(self):
        return self.layer


SourceBinding = Union[HoldTap, ToLayer, str]
T = TypeVar('T')
T2 = TypeVar('T2')
T3 = TypeVar('T3')


@dataclass
class Layer(Generic[T]):
    table: Table[T]
    name: str
    title: str

    def map_table(self, f: Callable[[T], T2]) -> 'Layer[T2]':
        new_table = self.table.copy(map(f, self.table.cells))
        return Layer(new_table, name=self.name, title=self.title)


def layers_from_tables(layer_tables: Iterable[Tuple[str, Table[str]]]):

    def parse_paths(title: str):
        for code in re.findall(r'`([^`]+)`', title):
            if m := re.match(r'([\w+]+)(?:([>,])|([+&]))([\w+]+)', code):
                a, _, f2, b = m.groups()
                yield [str(a), str(b)]
                if f2:
                    yield [str(b), str(a)]
            else:
                yield [str(code)]

    def parse_layers():
        for i, (title, table) in enumerate(layer_tables):
            paths = set(tuple(path) for path in parse_paths(title))

            name = str(i)
            if paths:
                minpath = min(paths, key=len)
                if len(minpath) < 2:
                    name = minpath[0]

            title = re.sub(r' +\(`\w+`\)', r'', title)

            yield table, name, title, paths

    layers = list(parse_layers())

    first, *others = [t.shape for t, _, _, _ in layers]
    if not all(other == first for other in others):
        raise ValueError('table are not all the same shape')

    nonvoid = [any(cells) for cells in zip(*(table.cells for table, _, _, _ in layers))]

    def f(c: str, b: bool):
        return c if b else None
    new_shape = Table.Shape(map(f, map(str, count()), nonvoid), first).shape

    by_id = {name: (Table.Shape(map(f, table.cells, nonvoid), first),
                    title, paths) for table, name, title, paths in layers}

    def make_taphold(tap: str, hold: str):
        if hold:
            if hold in by_id:
                return LayerTap(tap, hold)
            else:
                return ModTap(tap, hold)
        else:
            return tap

    base_table, base_title, _ = by_id.pop('base')
    taphold_table, _, _ = by_id.pop('hold-tap')

    tmp_by_id = dict(
        base=(list(map(make_taphold, base_table.cells, taphold_table.cells)),
              base_title),
        **{name: (table.cells, title) for name, (table, title, _) in by_id.items()}
    )

    for name, (cells, _, paths) in by_id.items():
        for path in paths:
            for a, b in zip(path, path[1:]):
                cells, _ = tmp_by_id[a]
                for i in [i for i, c in enumerate(taphold_table.cells) if c == b]:
                    c = cells[i]
                    if isinstance(c, str):
                        cells[i] = LayerTap(c, name)
    
    def make_layer(cells: Sequence[SourceBinding], name: str, title: str):
        return Layer(Table.Shape([c or 'XXX' for c in cells], new_shape), name, title)


    return [make_layer(cells, name, title) for name, (cells, title) in tmp_by_id.items()]


def extract_tables_from_md(f: Iterable[str], layout_section_re: str = r'layout definition'):
    def md_header_depth(line: str):
        line = line.strip()
        return len(line) - len(line.lstrip('#'))

    def md_find_section(predicate: Callable[[str], bool]):
        lines = iter(f)
        depth = 0
        for line in lines:
            if predicate(line):
                depth = md_header_depth(line)
                break

        for line in lines:
            d = md_header_depth(line)
            if d and d <= depth:
                break
            else:
                yield line

    def match_head(line: str):
        return re.match(r'^[#]+ +(.+)', line)

    def match_table(line: str):
        return re.match(r'^([|].*)+', line)

    subsection = ''
    in_table = False
    table_lines: List[str] = []

    def pred(s: str):
        return bool(re.search(layout_section_re, s, flags=re.I))

    for line in md_find_section(pred):
        if m := match_head(line):
            subsection = m.group(1).rstrip()
        elif match_table(line):
            in_table = True
            table_lines.append(line.strip('\t\r\n'))
        else:
            if in_table:
                yield str(subsection), Table.Parse(table_lines)
                table_lines = []
            in_table = False


def extract_layers_from_md(f: Iterable[str], make_3x5: bool = False):
    layers = layers_from_tables(extract_tables_from_md(f))

    if make_3x5:
        def g(table: Table[SourceBinding]):
            return type(table)([row[:5]+[None]+row[-5:] for row in table.rows])
        return [replace(layer, table=g(layer.table)) for layer in layers]
    else:
        return layers


def extract_os_specifics_from_md(f: Iterable[str]):
    for _, table in extract_tables_from_md(f, layout_section_re=r'OS specific'):
        for c in range(1, table.col_count):
            name = table.rows[0][c]
            if isinstance(name, str):
                aliases: Dict[str, str] = {}
                for r in range(1, table.row_count):
                    k = table.rows[r][0]
                    v = table.rows[r][c]
                    if isinstance(k, str) and isinstance(v, str) and v.strip(' -'):
                        aliases[k] = v
                yield name, aliases


MODIFIERS_RE = re.compile(r'([rl]?(ALT|CMD|CTRL|SHIFT))\+', flags=re.I)


def split_combo(kc: str) -> Tuple[List[str], str]:
    mods: List[str] = []
    i = 0
    while m := MODIFIERS_RE.match(kc, i):
        mods.append(m.group(1))
        i = m.end()

    return mods, kc[i:]


def split_common_prefix(names: Sequence[str]) -> Tuple[str, List[str]]:
    prefix = commonprefix(names)
    return prefix, [name[len(prefix):] for name in names]


def format_layer(table: Table[Any], blank: str = 'XXX'):
    def f(s: Any):
        return cjust('' if s == blank else str(s), 5)
    return format_boxed_table(table.copy(map(f, table.cells)))

