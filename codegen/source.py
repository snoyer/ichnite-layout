import re
from dataclasses import dataclass, replace
from typing import (Any, Callable, Collection, Generic, Iterable,
                    Sequence, TypeVar, cast)

from genericpath import commonprefix

from .asciitables import Table, TableShape, cjust, format_boxed_table

MODIFIERS_RE = r'([rl]?(ALT|CMD|CTRL|SHIFT))'


@dataclass
class Key:
    tap: str | None = None
    hold: str | None = None

    def map(self, f: Callable[[str], str]):
        return Key(tap = None if self.tap is None else f(self.tap), hold = None if self.hold is None else f(self.hold))

    def __bool__(self):
        return bool(self.tap) or bool(self.hold)

    def __str__(self) -> str:
        if not self:
            return ''
        elif not self.hold:
            return f'{self.tap}'
        elif not self.tap:
            return f'▼{self.hold}'
        else:
            return f'{self.tap} ▼{self.hold}'
    
    @classmethod
    def Empty(cls):
        return cls()

T = TypeVar('T')
T2 = TypeVar('T2')
T3 = TypeVar('T3')


@dataclass
class Keymap(Generic[T]):
    layers: dict[str, list[T]]
    titles: dict[str, str]
    table_shape: TableShape

    def reshape(self, src: Table[str], dst: Table[str], default: T):
        def new_layers():
            for k,v in self.layers.items():
                table = Table.Shape(self.table_shape, v, default).reshape(src, dst, default)
                yield k, table.values
        
        return replace(self, layers=dict(new_layers()), table_shape=dst.shape)
    
    def map_keys(self, f: Callable[[T], T2]) -> 'Keymap[T2]':
        new_layers = {name: [f(key) for key in keys] for name,keys in self.layers.items()}
        return cast(Keymap[T2], replace(self, layers=new_layers))

    @staticmethod
    def From_tables(layer_tables: Iterable[tuple[str, Table[str]]], f: Callable[[str], T]):

        def parse_layers():
            for i, (title, table) in enumerate(layer_tables):
                if m := re.search(r'`([^`]+)`', title):
                    name = m.group(1)
                else:
                    name = str(i)
                yield table.map_contents(str.strip), name, title

        layers = list(parse_layers())

        first_shape, *next_shapes = [t.shape for t, _, _ in layers]
        if not all(shape == first_shape for shape in next_shapes):
            raise ValueError('tables are not all the same shape')

        stacked_cells = zip(*(table.values for table, _, _ in layers))
        nonvoids = [index for index,values in zip(first_shape, stacked_cells) if any(values)]
        final_shape = {k:first_shape[k] for k in nonvoids}

        return Keymap(
            layers={name:[f(table[k]) for k in final_shape] for table, name, _title in layers},
            titles={name:title for _table, name, title in layers},
            table_shape=final_shape
        )


def make_multi_os_layers(layers: dict[str, list[Key]], os_specific_codes: dict[str, dict[str, str]]):
    first_layer_name = next(iter(layers))

    def add_os_to_name(name: str, os: str):
        return join_layer_name(name, [os])
    
    def new_layers():
        for name, keys in layers.items():
            for os, os_spcecific in os_specific_codes.items():
                def f(b: str) -> str:
                    if b in layers:
                        return add_os_to_name(b, os)
                    
                    if b.startswith('@'):
                        xxx = b.removeprefix('@')
                        if xxx in os_specific_codes:
                            return '@' + add_os_to_name(first_layer_name, xxx)

                    return os_spcecific.get(b,b)
                
                yield add_os_to_name(name, os), [key.map(f) for key in keys]
    
    return dict(new_layers())


def split_layer_name(layer_name: str) -> tuple[str, list[str]]:
    if '/' in layer_name:
        base_name, vars_str = layer_name.split('/', maxsplit=1)
        return base_name, vars_str.split(',')
    else:
        return layer_name, []


def join_layer_name(base_name: str, variations: Collection[str]):
    return '/'.join(filter(None, [base_name, ','.join(variations)]))


def keymap_from_md(lines: Iterable[str]):
    return Keymap.From_tables(extract_tables_from_md(lines), str)


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
        return re.match(r'^(\s*[|+].+)', line)

    subsection = ''
    in_table = False
    table_lines: list[str] = []

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


def extract_os_specifics_from_md(f: Iterable[str]):
    for _, table in extract_tables_from_md(f, layout_section_re=r'OS specific'):
        for c in range(1, table.col_count):
            name = table[0,c]
            aliases: dict[str, str] = {}
            for r in range(1, table.row_count):
                k = table[r,0]
                v = table[r,c]
                if v.strip(' -'):
                    aliases[k] = v
            yield name, aliases


def split_mods(kc: str) -> tuple[list[str], str]:
    mods: list[str] = []
    pattern = re.compile(MODIFIERS_RE+r'\+', re.I)
    i = 0
    while m := pattern.match(kc, i):
        mods.append(m.group(1))
        i = m.end()

    return mods, kc[i:]


def split_common_prefix(names: Sequence[str]) -> tuple[str, list[str]]:
    prefix = commonprefix(names)
    return prefix, [name[len(prefix):] for name in names]


def format_layer(table: Table[Any]):
    def g(s: Key):
        return cjust(str(s).strip(), 5)
    
    return format_boxed_table(table.map_contents(g))

