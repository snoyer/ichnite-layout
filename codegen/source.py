import re
from collections import defaultdict
from dataclasses import dataclass, replace
from functools import partial
from itertools import tee
from operator import __not__
from typing import (
    Callable,
    Collection,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    TypeVar,
    cast,
)

from .asciitables import Table, TableShape

MODIFIERS_RE = r"([rl]?(ALT|CMD|CTRL|SHIFT))"


class LayerName(str):
    def __repr__(self) -> str:
        return f"Layer({super().__repr__()})"


@dataclass
class Key:
    tap: str | None = None
    hold: str | None = None

    def map(self, f: Callable[[str], str]):
        return Key(
            tap=None if self.tap is None else f(self.tap),
            hold=None if self.hold is None else f(self.hold),
        )

    def __bool__(self):
        return bool(self.tap) or bool(self.hold)

    def __str__(self) -> str:
        if not self:
            return ""
        elif not self.hold:
            return f"{self.tap}"
        elif not self.tap:
            return f"▼{self.hold}"
        else:
            return f"{self.tap} ▼{self.hold}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.tap!r}, {self.hold!r})"

    @classmethod
    def Empty(cls):
        return cls()


K = TypeVar("K")
K2 = TypeVar("K2")
L = TypeVar("L")


@dataclass
class Keymap(Generic[L, K]):
    layers: dict[L, list[K]]
    table_shape: TableShape

    def reshape(self, src: Table[str], dst: Table[str], default: K):
        def new_layers():
            for k, v in self.layers.items():
                table = Table.Shape(self.table_shape, v, default).reshape(
                    src, dst, default
                )
                yield k, table.values

        return replace(self, layers=dict(new_layers()), table_shape=dst.shape)

    def map_keys(self, f: Callable[[K], K2]) -> "Keymap[L, K2]":
        new_layers = {
            name: [f(key) for key in keys] for name, keys in self.layers.items()
        }
        return cast(Keymap[L, K2], replace(self, layers=new_layers))

    @staticmethod
    def From_tables(tables: Mapping[str, Table[str]]):
        first_shape, *next_shapes = (t.shape for t in tables.values())
        if not all(shape == first_shape for shape in next_shapes):
            raise ValueError("tables are not all the same shape")

        stacked_cells = zip(*(table.values for table in tables.values()))
        nonvoids = [
            index for index, values in zip(first_shape, stacked_cells) if any(values)
        ]
        final_shape = {k: first_shape[k] for k in nonvoids}

        return Keymap(
            layers={
                name: [table[k] for k in final_shape] for name, table in tables.items()
            },
            table_shape=final_shape,
        )


def make_multi_os_layers(
    layers: dict[str, list[Key]], os_specific_codes: dict[str, dict[str, str]]
):
    first_layer_name = next(iter(layers))

    def add_os_to_name(name: str, os: str):
        return join_layer_name(name, [os])

    for name, keys in layers.items():
        for os, os_spcecific in os_specific_codes.items():

            def f(b: str) -> str:
                if b in layers:
                    return LayerName(add_os_to_name(b, os))

                if b.startswith("@"):
                    target_os = b.removeprefix("@")
                    if target_os in os_specific_codes:
                        return "@" + add_os_to_name(first_layer_name, target_os)

                return os_spcecific.get(b, b)

            yield (name, os), [key.map(f) for key in keys]


def join_layer_name(base_name: str, variations: Collection[str]):
    return "/".join(filter(None, [base_name, ",".join(variations)]))


def split_layer_name(layer_name: str) -> tuple[str, list[str]]:
    if "/" in layer_name:
        base_name, vars_str = layer_name.split("/", maxsplit=1)
        return base_name, vars_str.split(",")
    else:
        return layer_name, []


def merge_layer_names(layer_names: Iterable[str]):
    by_basename: dict[str, list[str]] = defaultdict(list)
    for layer_name in layer_names:
        base, os = split_layer_name(layer_name)
        by_basename[base] += os
    return "+".join(join_layer_name(base, os) for base, os in by_basename.items())


def extract_tables_from_md(
    f: Iterable[str], layout_section_re: str = r"layout definition"
):
    def md_header_depth(line: str):
        line = line.strip()
        return len(line) - len(line.lstrip("#"))

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
        return re.match(r"^[#]+ +(.+)", line)

    def match_table(line: str):
        return re.match(r"^(\s*[|+].+)", line)

    subsection = ""
    in_table = False
    table_lines: list[str] = []

    def pred(s: str):
        return bool(re.search(layout_section_re, s, flags=re.I))

    for line in md_find_section(pred):
        if m := match_head(line):
            subsection = m.group(1).rstrip()
        elif match_table(line):
            in_table = True
            table_lines.append(line.strip("\t\r\n"))
        else:
            if in_table:
                yield str(subsection), Table.Parse(table_lines)
                table_lines = []
            in_table = False

    if in_table:
        yield str(subsection), Table.Parse(table_lines)


def extract_os_specifics_from_md(f: Iterable[str]):
    for _, table in extract_tables_from_md(f, layout_section_re=r"OS specific"):
        for c in range(1, table.col_count):
            name = table[0, c]
            aliases: dict[str, str] = {}
            for r in range(1, table.row_count):
                k = table[r, 0]
                v = table[r, c]
                if v.strip(" -"):
                    aliases[k] = v
            yield name, aliases


def split_mods(kc: str) -> tuple[list[str], str]:
    mods: list[str] = []
    pattern = re.compile(MODIFIERS_RE + r"\+", re.I)
    i = 0
    while m := pattern.match(kc, i):
        mods.append(m.group(1))
        i = m.end()

    return mods, kc[i:]


####


def keymap_from_md(lines: Iterable[str], reshape: Optional[str] = None):
    lines1, lines2 = tee(lines)

    keymap, titles = base_keymap_from_md(lines1)
    if reshape:
        src = Table.Parse(ALT_LAYOUTS["source"])
        dst = Table.Parse(ALT_LAYOUTS[reshape]).remove_cells(__not__)
        keymap = keymap.reshape(src, dst, Key.Empty())

    os_specifics = dict(extract_os_specifics_from_md(lines2))
    multi_os_layers = make_multi_os_layers(keymap.layers, os_specifics)

    return keymap, titles, multi_os_layers


def base_keymap_from_md(lines: Iterable[str], reshape: Optional[str] = None):
    def id_from_title(title: str, default: str):
        if m := re.search(r"`([^`]+)`", title):
            return str(m.group(1))
        else:
            return default

    parsed = [
        (id_from_title(title, f"layer#{i + 1}"), table, title)
        for i, (title, table) in enumerate(extract_tables_from_md(lines))
    ]
    source_keymap = Keymap.From_tables({k: table for k, table, _ in parsed})
    titles = {k: title for k, _, title in parsed}

    keymap = add_holdtaps(source_keymap)
    keymap = add_paths_from_titles(keymap, titles)

    if reshape:
        src = Table.Parse(ALT_LAYOUTS["source"])
        dst = Table.Parse(ALT_LAYOUTS[reshape]).remove_cells(__not__)
        keymap = keymap.reshape(src, dst, Key.Empty())

    return keymap, titles


def add_holdtaps(
    txt_keymap: Keymap[str, str],
    holdtap_table_name: str = "hold-tap",
    mods_on_all_layers: bool = False,
):
    def make_taphold(tap: str, hold: str, layers: bool = False, mods: bool = True):
        if hold:
            if hold in txt_keymap.layers:
                if layers:
                    return Key(hold=LayerName(hold), tap=tap or None)
            elif re.match(MODIFIERS_RE, hold):
                if mods and tap != hold:
                    return Key(hold=hold, tap=tap or None)
            else:
                raise ValueError(
                    f"hold-tap key is neither layer-tap nor mod-tap: {hold}"
                )

        return Key(tap=tap)

    if holdtap_table_name in txt_keymap.layers:
        taphold = txt_keymap.layers.pop(holdtap_table_name)

        def new_layers():
            for i, (name, keys) in enumerate(txt_keymap.layers.items()):
                is_first = i == 0
                f = partial(
                    make_taphold, layers=is_first, mods=is_first or mods_on_all_layers
                )
                yield name, list(map(f, keys, taphold))

        keymap = replace(txt_keymap, layers=dict(new_layers()))
    else:
        keymap = txt_keymap

    return cast(Keymap[str, Key], keymap)


def add_paths_from_titles(keymap: Keymap[str, Key], titles: dict[str, str]):
    def parse_paths(title: str):
        for code in re.findall(r"`([^`]+)`", title):
            if m := re.match(r"([\w+]+)(?:([>,])|([+&]))([\w+]+)", code):
                a, _, f2, b = m.groups()
                yield [str(a), str(b)]
                if f2:
                    yield [str(b), str(a)]
            else:
                yield [str(code)]

    paths_by_id = {
        layer_id: list(parse_paths(title)) for layer_id, title in titles.items()
    }
    return add_paths(keymap, paths_by_id)


def add_paths(
    keymap: Keymap[str, Key], paths_by_id: Mapping[str, Sequence[Sequence[str]]]
):
    layertaps = {
        i: LayerName(x.hold)
        for i, x in enumerate(keymap.layers["base"])
        if x.hold in keymap.layers
    }

    for layer_name, cells in keymap.layers.items():
        for path in paths_by_id.get(layer_name, []):
            for src, dst in zip(path, path[1:]):
                cells = keymap.layers[src]
                for i, layer in layertaps.items():
                    if layer == dst:
                        cells[i].hold = LayerName(layer_name)

    return keymap


ALT_LAYOUTS = {
    "source": r"""
    |a|b|c|d|e|     |E|D|C|B|A|
    |f|g|h|i|j|k| |K|J|I|H|G|F|
    |l|m|n|o|p|q| |Q|P|O|N|M|L|
    |   |r|s|t|     |T|S|R|   |
    """,
    "split3x5+3": r"""
    |a|b|c|d|e| |E|D|C|B|A|
    |f|g|h|i|j| |J|I|H|G|F|
    |l|m|n|o|p| |P|O|N|M|L|
    |   |r|s|t| |T|S|R|   |
    """,
    "ortho4x12": r"""
    |a|b|c|d|e|-|-|E|D|C|B|A|
    |f|g|h|i|j|k|K|J|I|H|G|F|
    |l|m|n|o|p|q|Q|P|O|N|M|L|
    |-|-|-|r|s|t|T|S|R|-|-|-|
    """,
}
