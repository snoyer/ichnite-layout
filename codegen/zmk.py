from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, replace
from itertools import chain, groupby
from typing import (
    Callable,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Self,
    Sequence,
    TypeVar,
)

from .asciitables import Table, TableShape, cjust, format_boxed_table, format_table
from .dt import Comment, Node, Raw, format_value
from .source import (
    Key,
    Keymap,
    LayerName,
    join_layer_name,
    merge_layer_names,
    split_layer_name,
    split_mods,
)
from .zmk_keycodes import ZMK_KEYCODES, ZMK_KEYCODES_ALIASES

BINDINGS_INCLUDES = {
    "kp": ["<dt-bindings/zmk/keys.h>"],
    "bt": ["<dt-bindings/zmk/bt.h>"],
    "out": ["<dt-bindings/zmk/outputs.h>"],
    "mmv": ["<dt-bindings/zmk/pointing.h>"],
    "mkb": ["<dt-bindings/zmk/pointing.h>"],
}


def generate_zmk_keymap_code(
    keymap: Keymap[str, Key],
    titles: Mapping[str, str],
    multi_os_layers: Iterable[tuple[tuple[str, str], list[Key]]],
    *,
    transform_name: str = "default_transform",
    aliases_for_os: Callable[
        [str], dict[str, str | Binding | Callable[[re.Match[str]], str | Binding]]
    ]
    | None = None,
    extra_includes: Iterable[str] = (),
) -> Iterator[str]:
    binding_layers = [
        Layer(
            join_layer_name(source_layer, [os]),
            list(
                map(
                    BindingTranslator(
                        aliases_for_os(os) if callable(aliases_for_os) else {}
                    ),
                    keys,
                )
            ),
            source_layer,
            display_name=os if source_layer == "base" else source_layer,
        )
        for (source_layer, os), keys in multi_os_layers
    ]

    binding_layers = [
        layer.rename_layers_in_bindings(layer.Shorten_name)
        for layer in Layer.Deduplicate(binding_layers)
    ]

    defines = [(layer.name, i) for i, layer in enumerate(binding_layers)]

    def keymap_contents():
        for source_layer, layers in groupby(
            binding_layers, lambda layer: layer.source_layer
        ):
            source_table = Table.Shape(
                keymap.table_shape, keymap.layers[source_layer], Key.Empty()
            )
            formatted_table = format_boxed_table(
                source_table.map_contents(lambda s: cjust(str(s).strip(), 5))
            )
            yield Comment(f"{titles[source_layer]}\n{formatted_table}")
            for layer in layers:
                yield layer.formatted_bindings(keymap.table_shape)

    behaviors = {
        repr(x): x
        for x in chain.from_iterable(
            binding.behavior_nodes or []
            for layer in binding_layers
            for binding in layer.bindings
        )
    }.values()

    nodes = [
        Node(
            "/",
            children=[
                Node(
                    "chosen",
                    properties={
                        "zmk,matrix_transform": Raw(f"&{transform_name}"),
                    },
                ),
                Node(
                    "keymap",
                    properties={"compatible": "zmk,keymap"},
                    children=list(keymap_contents()),
                ),
                Node(
                    "behaviors",
                    children=list(behaviors),
                ),
            ],
        ),
        Node(
            "&lt",
            properties={
                "flavor": "hold-preferred",
                "tapping-term-ms": 150,
                "quick-tap-ms": 200,
            },
        ),
        Node(
            "&hrm",
            properties={
                "flavor": "tap-preferred",
                "tapping-term-ms": 150,
                "quick-tap-ms": 200,
            },
        ),
    ]

    def find_includes():
        yield "<behaviors.dtsi>"
        for layer in binding_layers:
            for binding in layer.bindings:
                for b in binding.find_all_behaviors():
                    for v in BINDINGS_INCLUDES.get(b, []):
                        yield v

    for include in chain(sorted(set(find_includes())), extra_includes):
        if not include.startswith("<") or include.startswith('"'):
            include = f'"{include}"'
        yield f"#include {include}"
    yield ""

    for name, value in defines:
        yield f"#define {name} {value}"

    for node in nodes:
        yield ""
        yield node.format_dt()


T = TypeVar("T")


@dataclass
class LayerBase(Generic[T]):
    name: str
    bindings: list[T]
    source_layer: str

    def rename(self, name: str):
        return replace(self, name=name)

    def rename_layers_in_bindings(self, rename_func: Callable[[str], str]):
        return replace(
            self,
            name=rename_func(self.name),
            bindings=[
                self.Rename_layer_in_binding(binding, rename_func)
                for binding in self.bindings
            ],
        )

    @classmethod
    def Rename_layer_in_binding(
        cls, binding: T, rename_func: Callable[[str], str]
    ) -> T: ...

    @classmethod
    def Deduplicate(
        cls, binding_layers: Sequence[Self], exceptions: Iterable[str] = ()
    ) -> Sequence[Self]:
        exceptions_set = set(exceptions)
        for _ in range(len(binding_layers)):
            by_repr: dict[tuple[str, str], list[Self]] = defaultdict(list)
            for i, layer in enumerate(binding_layers):
                by_repr[
                    layer.source_layer,
                    str(i)
                    if layer.source_layer in exceptions_set
                    else repr(layer.bindings),
                ].append(layer)
            grouped = [vs for vs in by_repr.values()]

            new_names = {
                layer.name: merge_layer_names(layer.name for layer in layers)
                for layers in grouped
                for layer in layers
                if len(layers) > 1
            }
            if not new_names:
                break

            binding_layers = [
                layers[0].rename_layers_in_bindings(lambda k: new_names.get(k, k))
                for layers in grouped
            ]
        return binding_layers

    @classmethod
    def Shorten_name(cls, layer_name: str):
        base, os = split_layer_name(layer_name)
        short_name = join_layer_name(base, ["".join(s[0] for s in os)])
        return re.sub(r"[^a-z0-9]", "_", short_name, flags=re.I)


class BindingTranslator:
    def __init__(
        self,
        aliases: Mapping[str, str | Binding | Callable[[re.Match[str]], str | Binding]],
    ) -> None:
        self.aliases: dict[str, str | Binding] = {}
        self.callable_aliases: dict[
            re.Pattern[str], Callable[[re.Match[str]], str | Binding]
        ] = {}
        for k, v in aliases.items():
            if callable(v):
                self.callable_aliases[re.compile(k)] = v
            else:
                self.aliases[k] = v

    def __call__(self, key: Key):
        try:
            if isinstance(key.hold, LayerName):
                if key.tap:
                    return lt_binding(key.hold, self.translate_binding(key.tap))
                else:
                    return mo_binding(key.hold)
            elif key.hold and key.tap:
                return home_row_mod_binding(
                    lookup_keycode(key.hold), self.translate_binding(key.tap)
                )
            elif key.tap:
                return self.translate_binding(key.tap)
            else:
                return Binding("none")
        except KeyError:
            print("unimplemented: ", repr(key))
            return Binding("none")

    def follow_aliases(self, txt: str):
        seen: set[str] = set()
        while txt not in seen:
            try:
                found = self.aliases[txt]
            except KeyError:
                for k, v in self.callable_aliases.items():
                    if m := k.match(txt):
                        found = v(m)
                        break
                else:
                    break

            if isinstance(found, Binding):
                return found
            else:
                seen.add(found)
                txt = found
                break
        return txt

    def translate_binding(self, txt: str):
        found = self.follow_aliases(txt)
        if isinstance(found, Binding):
            return found
        else:
            txt_mods, text_key = split_mods(found)
            kc_key = lookup_keycode(text_key)
            kc_mods = [ZMK_MODIFIERS[lookup_keycode(mod)] for mod in txt_mods]
            kp = "(".join(map(str, (*kc_mods, kc_key))) + ")" * len(kc_mods)
            return kp_binding(kp)


def lookup_keycode(name: str):
    if name.upper() in ZMK_KEYCODES:
        return name.upper()
    else:
        try:
            return ZMK_KEYCODES_ALIASES[name]
        except KeyError:
            return ZMK_KEYCODES_ALIASES[name.upper()]


def kp_binding(keycode: str):
    return Binding("kp", keycode)


def lt_binding(layer: str, keycode_binding: Binding):
    if keycode_binding.behavior not in ("kp", "none"):
        raise ValueError(keycode_binding)
    return Binding("lt", layer, keycode_binding.param1)


def mo_binding(layer: str):
    return Binding("mo", layer)


def shiftmorph_binding(regular: str, shifted: str) -> Binding:
    regular = lookup_keycode(regular)
    shifted = lookup_keycode(shifted)

    name = f"{regular.lower()}_{shifted.lower()}"
    return Binding(
        name,
        behavior_nodes=(
            Node(
                name,
                label=name,
                properties={
                    "compatible": "zmk,behavior-mod-morph",
                    "#binding-cells": 0,
                    "bindings": Raw(f"<&kp {regular}>, <&kp {shifted}>"),
                    "mods": Raw("<(MOD_LSFT|MOD_RSFT)>"),
                },
            ),
        ),
    )


def bootloader_binding() -> Binding:
    tapdance_node = Node(
        "bootl",
        label="bootl",
        properties={
            "compatible": "zmk,behavior-tap-dance",
            "#binding-cells": 0,
            "tapping-term-ms": 200,
            "bindings": Raw("<&trans>, <&bootloader>"),
        },
    )
    return Binding("bootl", behavior_nodes=(tapdance_node,))


BTSEL_NODE = Node(
    "btsel",
    label="btsel",
    properties={
        "compatible": "zmk,behavior-macro-one-param",
        "#binding-cells": 1,
        "bindings": Raw(
            "<&macro_param_1to2>, <&bt BT_SEL MACRO_PLACEHOLDER>, <&out OUT_BLE>"
        ),
    },
)


def bt_binding(i: int):
    bt_sel_binding = Binding("btsel", str(i - 1), behavior_nodes=(BTSEL_NODE,))
    bt_disc_binding = Binding("bt", "BT_DISC", str(i - 1))
    bt_clr_binding = Binding("bt", "BT_CLR")

    bt_node = Node(
        f"bt{i}",
        label=f"bt{i}",
        properties={
            "compatible": "zmk,behavior-tap-dance",
            "#binding-cells": 0,
            "tapping-term-ms": 200,
            "bindings": NestedBindings(
                (
                    Bindings([bt_sel_binding]),
                    Bindings([bt_disc_binding]),
                    Bindings([bt_clr_binding]),
                )
            ),
        },
    )

    return Binding(f"bt{i}", behavior_nodes=(*bt_sel_binding.behavior_nodes, bt_node))


def macro_node(
    identifier: str,
    *behaviors: Sequence[Binding],
    tap_ms: Optional[int] = None,
    wait_ms: Optional[int] = None,
) -> Node:
    return Node(
        identifier,
        label=identifier,
        properties={
            "compatible": "zmk,behavior-macro",
            "#binding-cells": 0,
            "bindings": NestedBindings(Bindings(b) for b in behaviors),
            "tap-ms": tap_ms,
            "wait-ms": wait_ms,
        },
    )


def macro_binding(
    identifier: str,
    *behaviors: Sequence[Binding],
    tap_ms: Optional[int] = None,
    wait_ms: Optional[int] = None,
) -> Binding:
    return Binding(
        identifier,
        behavior_nodes=(
            macro_node(identifier, *behaviors, tap_ms=tap_ms, wait_ms=wait_ms),
        ),
    )


def utf8_linux_macro_binding(char: str) -> Binding:
    hexstr = "%04x" % ord(char)
    keycodes = [d.upper() if d in "abcdef" else f"N{d}" for d in hexstr]
    keycodes = "LC(LS(U))", *keycodes, "SPACE"
    return macro_binding(
        f"u{hexstr}_L",
        [Binding("macro_tap"), *map(kp_binding, keycodes)],
        tap_ms=30,
        wait_ms=0,
    )


def utf8_mac_macro_binding(char: str) -> Binding:
    hexstr = "%04x" % ord(char)
    keycodes = [d.upper() if d in "abcdef" else f"N{d}" for d in hexstr]
    return macro_binding(
        f"u{hexstr}_M",
        [Binding("macro_press"), kp_binding("LALT")],
        [Binding("macro_tap"), *map(kp_binding, keycodes)],
        [Binding("macro_release"), kp_binding("LALT")],
        tap_ms=30,
        wait_ms=30,
    )


def utf8_win_macro_binding(char: str) -> Binding:
    hexstr = "%04x" % ord(char)
    keycodes = [d.upper() if d in "abcdef" else f"N{d}" for d in hexstr]
    keycodes = "RALT", "U", *keycodes, "RET"
    return macro_binding(
        f"u{hexstr}_W",
        [Binding("macro_tap"), *map(kp_binding, keycodes)],
    )


HRM_NODE = Node(
    "modtap",
    label="hrm",
    properties={
        "compatible": "zmk,behavior-hold-tap",
        "#binding-cells": 2,
        "bindings": Raw("<&kp>, <&kp>"),
    },
)


def home_row_mod_binding(mod_keycode: str, tap_keycode_binding: Binding):
    if not tap_keycode_binding.behavior == "kp":
        raise ValueError()
    return Binding(
        "hrm", mod_keycode, tap_keycode_binding.param1, behavior_nodes=(HRM_NODE,)
    )


@dataclass(frozen=True)
class Binding:
    behavior: str
    param1: Optional[str] = None
    param2: Optional[str] = None
    includes: tuple[str, ...] = ()
    behavior_nodes: tuple[Node, ...] = ()

    def format_dt(self):
        return " ".join(
            (
                f"&{self.behavior}",
                *map(str, filter(None, (self.param1, self.param2))),
            )
        )

    def find_all_behaviors(self) -> Iterator[str]:
        yield self.behavior

        def f(node: Node) -> Iterator[str]:
            yield node.name
            for child in node.children:
                if isinstance(child, Node):
                    yield from f(child)
            yield from re.findall(r"\W&(\w+)\W", node.format_dt())

        for node in self.behavior_nodes:
            yield from f(node)


@dataclass
class Layer(LayerBase[Binding]):
    display_name: str

    @classmethod
    def Rename_layer_in_binding(
        cls, binding: Binding, rename_func: Callable[[str], str]
    ):
        if binding.behavior in ("mo", "to", "lt", "base"):
            return replace(
                binding, param1=rename_func(binding.param1) if binding.param1 else None
            )
        else:
            return binding

    def formatted_bindings(self, table_shape: TableShape):
        formatted_bindings = [str(b.format_dt()) for b in self.bindings]
        formated = format_table(
            Table.Shape(table_shape, formatted_bindings, ""),
            sep="",
            pad=" ",
            just=str.ljust,
        )
        formated = "\n".join(layer.rstrip() for layer in formated.splitlines())
        return Node(
            self.name,
            properties={
                "bindings": Raw(f"<\n{formated}\n>"),
                "display-name": self.display_name,
            },
        )


class Bindings(list[Binding]):
    def format_dt(self):
        values_str = " ".join(map(format_value, self))
        return f"<{values_str}>"


class NestedBindings(list[Bindings]):
    def format_dt(self):
        return ", ".join(map(format_value, self))


ZMK_MODIFIERS = {
    lookup_keycode(k): v
    for k, v in dict(
        LSHFT="LS",
        LCTRL="LC",
        LALT="LA",
        LGUI="LG",
        RSHFT="RS",
        RCTRL="RC",
        RALT="RA",
        RGUI="RG",
    ).items()
}
ZMK_MODIFIERS_RE = re.compile(
    r"^\s*(" + r"|".join(ZMK_MODIFIERS.values()) + r")\s*\(\s*(.+)\s*\)\s*$"
)


def split_zmk_keycode_mods(zmk_keycode: str) -> list[str]:
    if m := ZMK_MODIFIERS_RE.match(zmk_keycode):
        return [m.group(1), *split_zmk_keycode_mods(m.group(2))]
    else:
        return [zmk_keycode]
