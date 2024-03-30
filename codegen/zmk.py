import logging
import re
from dataclasses import dataclass, replace
from functools import cache
from itertools import groupby
from os.path import dirname
from os.path import join as path_join
from typing import Any, Callable, Iterable, Optional, Sequence, Union

from .asciitables import Table, format_table
from .dt import Comment, Node, NodeOrComment, Raw, format_value
from .source import Key, Keymap, format_layer, split_layer_name, split_mods
from .translation import Translator

logger = logging.getLogger(__name__)


def generate_zmk_code(
    translated_layers: dict[str, list["Binding"]],
    source_keymap: Keymap[Key],
    transform_name: Optional[str] = "default_transform",
):
    layer_nodes, behavior_nodes, defines = make_zmk_layers(
        translated_layers, source_keymap
    )

    def find_includes():
        dt_bindings = {
            "kp": ["<dt-bindings/zmk/keys.h>"],
            "bt": ["<dt-bindings/zmk/bt.h>"],
            "out": ["<dt-bindings/zmk/outputs.h>"],
            "capslock_word": ['"behaviors/capslock.dtsi"'],
            "base": ['"behaviors/base_layer.dtsi"'],
        }
        yield "<behaviors.dtsi>"
        for node in behavior_nodes:
            for v in dt_bindings.get(node.name, []):
                yield v

    includes = sorted(set(find_includes()))

    return (
        join_lines(
            (
                join_lines(f"#include {include}" for include in includes),
                join_lines(defines),
                Node(
                    "/",
                    [
                        Node(
                            "chosen",
                            properties={
                                "zmk,matrix_transform": Raw(f"&{transform_name}")
                            },
                        ),
                        Node(
                            "keymap",
                            layer_nodes,
                            properties={
                                "compatible": "zmk,keymap",
                            },
                        ),
                        Node(
                            "behaviors", [node for node in behavior_nodes if node.label]
                        ),
                    ],
                ).format_dt(),
                Node(
                    "&lt",
                    properties={
                        "flavor": "hold-preferred",
                        "tapping-term-ms": 150,
                        "quick-tap-ms": 200,
                    },
                ).format_dt(),
                Node(
                    "&hrm",
                    properties={
                        "flavor": "tap-preferred",
                        "tapping-term-ms": 150,
                        "quick-tap-ms": 200,
                    },
                ).format_dt(),
            ),
            2,
        )
        + "\n"
    )


def zmk_translator_for_os(os: str):
    translator = ZmkTranslator(ZmkKeycodes())

    translator.register_aliases(
        {
            "PSCR": "PRINTSCREEN",
            "SLOCK": "SCROLLLOCK",
            "NLOCK": "KP_NUMLOCK",
            "CLOCK": "CAPSLOCK",
            "BREAK": "PAUSE_BREAK",
            "APP": "K_APP",
            "PLAY": "C_PLAY_PAUSE",
            "STOP": "C_STOP",
            "PAUSE": "C_PAUSE",
            "PREV": "C_PREV",
            "NEXT": "C_NEXT",
            "FFW": "C_FF",
            "RWD": "C_RW",
            "MUTE": "C_MUTE",
            "VOL+": "C_VOL_UP",
            "VOL-": "C_VOL_DN",
            "BRI+": "C_BRI_UP",
            "BRI-": "C_BRI_DN",
            "MYCOMP": "C_AL_MY_COMPUTER",
            "WWW": "C_AL_WWW",
            "CALC": "C_AL_CALCULATOR",
        }
    )

    def make_bt(m: re.Match[str]):
        return Binding(bt_macro(int(m.group(1))))

    translator.register_translations(
        {
            "RESET": make_binding("sys_reset"),
            "BOOTL": Binding(bootloader_tapdance()),
            r"BT(\d+)": make_bt,
            "BTCLR": make_binding("bt", "BT_CLR"),
            "USB": make_binding("out", "OUT_USB"),
            "___": make_binding("trans"),
            "XXX": make_binding("none"),
            "CAPS": make_binding(
                "capslock_word_mac" if os == "mac" else "capslock_word"
            ),
        }
    )

    utf8_macros = {
        "linux": utf8_linux_macro_node,
        "mac": utf8_mac_macro_node,
        "win": utf8_win_macro_node,
    }
    if os in utf8_macros:

        def make_unicode(m: re.Match[str]):
            return Binding(utf8_macros[os](m.group(1)))

        translator.register_translations({r"([\u0080-\uffff])$": make_unicode})

    return translator


@dataclass(frozen=True)
class Binding:
    behavior: Node
    param1: Optional[str] = None
    param2: Optional[str] = None

    def behavior_is(self, *labels: Sequence[str]) -> bool:
        return self.behavior.name in labels

    def format_dt(self):
        return " ".join(
            map(format_value, filter(None, (self.behavior, self.param1, self.param2)))
        )


class Bindings(list[Binding]):
    def format_dt(self):
        values_str = " ".join(map(format_value, self))
        return f"<{values_str}>"


class NestedBindings(list[Bindings]):
    def format_dt(self):
        return ", ".join(map(format_value, self))


def reference_nodes_in_properties(node: Node):
    referenced_nodes: dict[str, Node] = {}

    def replace_node_by_ref(node: Union[Node, Raw]):
        if isinstance(node, Node):
            newnode = update_node_properties(node)
            referenced_nodes[repr(newnode)] = newnode
            return Raw(f"&{node.label or node.name}")
        else:
            return node

    def update_node_properties(node: Node):
        def f(prop_value: Any):
            if isinstance(prop_value, Bindings):
                return Bindings(
                    replace(b, behavior=replace_node_by_ref(b.behavior))
                    for b in prop_value
                )
            elif isinstance(prop_value, NestedBindings):
                return NestedBindings(
                    Bindings(
                        replace(b, behavior=replace_node_by_ref(b.behavior))
                        for b in bindings
                    )
                    for bindings in prop_value
                )
            else:
                return prop_value

        return replace(
            node,
            properties={k: f(v) for k, v in node.properties.items()},
        )

    return update_node_properties(node), list(referenced_nodes.values())


def make_zmk_layers(
    translated_layers: dict[str, list[Binding]],
    source_keymap: Keymap[Key],
) -> tuple[list[NodeOrComment], list[Node], list[str]]:
    table_shape = source_keymap.table_shape

    def format_bindings(layer_node: Node):
        bindings = [str(b.format_dt()) for b in layer_node.properties["bindings"]]
        formated = format_table(
            Table.Shape(table_shape, bindings, ""), sep="", pad=" ", just=str.ljust
        )
        formated = "\n".join(layer.rstrip() for layer in formated.splitlines())
        layer_node.properties["bindings"] = Raw(f"<\n{formated}\n>")

    defines = [
        f"#define {fix_layer_name(layer)} {i}"
        for i, layer in enumerate(translated_layers)
        if not isinstance(layer, int)
    ]
    layer_nodes: list[NodeOrComment] = []
    behavior_nodes: dict[str, Node] = {}

    for src, layers in groupby(
        translated_layers.items(), key=lambda kv: split_layer_name(kv[0])[0]
    ):
        table = Table.Shape(table_shape, map(str, source_keymap.layers[src]), "")
        layer_nodes.append(
            Comment(source_keymap.titles[src] + "\n" + format_layer(table))
        )

        for name, bindings in layers:
            layer_node = Node(
                f"{fix_layer_name(name)}",
                properties={
                    "bindings": Bindings(
                        [
                            ZmkTranslator.map_layer_names(fix_layer_name, b)
                            for b in bindings
                        ]
                    ),
                },
            )

            new_layer_node, refs = reference_nodes_in_properties(layer_node)
            format_bindings(new_layer_node)
            layer_nodes.append(new_layer_node)

            for ref in refs:
                behavior_nodes[repr(ref)] = ref

    return layer_nodes, list(behavior_nodes.values()), defines


HRM_NODE = Node(
    "modtap",
    label="hrm",
    properties={
        "compatible": "zmk,behavior-hold-tap",
        "#binding-cells": 2,
        "bindings": Raw("<&kp>, <&kp>"),
    },
)


@cache
def make_binding(
    node_name: str, param1: Optional[str] = None, param2: Optional[str] = None
):
    return Binding(
        Node(node_name),
        Raw(param1) if param1 else None,
        Raw(param2) if param2 else None,
    )


@cache
def kp_binding(param1: str):
    return Binding(Node("kp"), Raw(param1))


class ZmkTranslator(Translator[Binding]):
    def __init__(self, zmk_keycodes: "ZmkKeycodes"):
        super().__init__()
        self.native_keycodes = zmk_keycodes

    def translate(self, key: Key, is_layer_name: Callable[[str], bool]) -> Binding:
        def f(s: str):
            t = self._alias_lookup(s)
            try:
                return self.native_keycodes[t]
            except KeyError:
                return t

        def g(s: str):
            t = self._alias_lookup(s)
            try:
                return self._translation_lookup(t)
            except KeyError:
                try:
                    return kp_binding(self.native_keycodes[t])
                except KeyError:
                    logger.warning(f"not implemented {t!r}")
                    return make_binding("none")

        if key.hold:
            if is_layer_name(key.hold):
                layer = key.hold
                if key.tap:
                    tap = g(key.tap)
                    return make_binding("lt", layer, tap.param1)
                else:
                    return make_binding("mo", layer)

            hold = f(key.hold)
            if re.match(r"[LR]?(GUI|ALT|CTRL|SHI?FT)", hold):
                if key.tap:
                    tap = g(key.tap)
                    return Binding(HRM_NODE, Raw(hold), tap.param1)
                else:
                    return kp_binding(hold)

            raise ValueError(f"cannot make hold-tap for {key}")

        if key.tap and is_layer_name(key.tap.removeprefix("@")):
            return make_binding("base", key.tap.removeprefix("@"))

        if key.tap and not key.hold:
            return g(key.tap)

        return make_binding("none")

    @classmethod
    def map_layer_names(cls, f: Callable[[str], str], binding: Binding) -> Binding:
        if binding.behavior_is("lt", "mo", "to", "base") and binding.param1 is not None:
            return replace(binding, param1=Raw(f(binding.param1)))
        else:
            return binding


def macro_node(
    identifier: str,
    *behaviors: Sequence[Binding],
    tap_ms: Optional[int] = None,
    wait_ms: Optional[int] = None,
    label: Optional[str] = None,
) -> Node:

    properties = {
        "compatible": "zmk,behavior-macro",
        "#binding-cells": 0,
        "bindings": NestedBindings(Bindings(b) for b in behaviors),
        "tap-ms": tap_ms,
        "wait-ms": wait_ms,
    }

    return Node(
        identifier,
        label=identifier,
        properties=properties,
    )


def utf8_linux_macro_node(char: str) -> Node:
    hexstr = "%04x" % ord(char)
    keycodes = [d.upper() if d in "abcdef" else f"N{d}" for d in hexstr]
    keycodes = "LC(LS(U))", *keycodes, "SPACE"
    return macro_node(
        f"u{hexstr}_L",
        [make_binding("macro_tap"), *map(kp_binding, keycodes)],
        tap_ms=30,
        wait_ms=0,
    )


def utf8_mac_macro_node(char: str) -> Node:
    hexstr = "%04x" % ord(char)
    keycodes = [d.upper() if d in "abcdef" else f"N{d}" for d in hexstr]
    return macro_node(
        f"u{hexstr}_M",
        [make_binding("macro_press"), kp_binding("LALT")],
        [make_binding("macro_tap"), *map(kp_binding, keycodes)],
        [make_binding("macro_release"), kp_binding("LALT")],
        tap_ms=30,
        wait_ms=30,
    )


def utf8_win_macro_node(char: str) -> Node:
    hexstr = "%04x" % ord(char)
    keycodes = [d.upper() if d in "abcdef" else f"N{d}" for d in hexstr]
    keycodes = "RALT", "U", *keycodes, "RET"
    return macro_node(
        f"u{hexstr}_W",
        [make_binding("macro_tap"), *map(kp_binding, keycodes)],
    )


def bt_macro(i: int) -> Node:
    return macro_node(
        f"bt{i}",
        [make_binding("bt", "BT_SEL", f"{i-1}")],
        [make_binding("out", "OUT_BLE")],
    )


def shiftmorph_node(default: str, shifted: str, zmk_keycodes: "ZmkKeycodes") -> Node:
    a = zmk_keycodes[default]
    b = zmk_keycodes[shifted]

    return Node(
        f"{a.lower()}_{b.lower()}",
        label=f"{a.lower()}_{b.lower()}",
        properties={
            "compatible": "zmk,behavior-mod-morph",
            "#binding-cells": 0,
            "bindings": Raw(f"<&kp {a}>, <&kp {b}>"),
            "mods": Raw("<(MOD_LSFT|MOD_RSFT)>"),
        },
    )


def bootloader_tapdance() -> Node:
    return Node(
        "bl_td",
        label="bootl_td",
        properties={
            "compatible": "zmk,behavior-tap-dance",
            "#binding-cells": 0,
            "tapping-term-ms": 200,
            "bindings": Raw("<&trans>, <&bootloader>"),
        },
    )


class ZmkKeycodes:
    def __init__(self, fn: str = path_join(dirname(__file__), "zmk-keycodes.txt")):
        self.mapping: dict[str, str] = dict()

        for line in open(fn):
            line = line.strip()
            if line and not line.startswith("#"):
                if "\t" in line:
                    left, right = line.split("\t")
                else:
                    left, right = line, ""

                left = left.split()
                right = right.split()
                shortest = min(left, key=len)
                for k in left + right:
                    self.mapping[k.lower()] = shortest

        self.MODIFIERS = {
            self[k]: v
            for k, v in dict(
                LEFT_SHIFT="LS",
                LEFT_CONTROL="LC",
                LEFT_ALT="LA",
                LEFT_GUI="LG",
                RIGHT_SHIFT="RS",
                RIGHT_CONTROL="RC",
                RIGHT_ALT="RA",
                RIGHT_GUI="RG",
            ).items()
        }
        self.MODIFIERS_RE = re.compile(
            r"^\s*(" + r"|".join(self.MODIFIERS.values()) + r")\s*\(\s*(.+)\s*\)\s*$"
        )

    def split_modified(self, k: str) -> list[str]:
        if m := self.MODIFIERS_RE.match(k):
            return [m.group(1), *self.split_modified(m.group(2))]
        else:
            return [
                k,
            ]

    def _base_lookup(self, k: str) -> str:
        if k.lower() in self.mapping:
            return self.mapping[k.lower()]
        else:
            raise KeyError(f"unknown ZMK keycode: {k}")

    def lookup(self, k: str) -> str:
        try:
            mods, kc = split_mods(k)
            kc = self._base_lookup(kc)
            mods = [self.MODIFIERS.get(self._base_lookup(mod)) for mod in mods]
            return "(".join(map(str, (*mods, kc))) + ")" * len(mods)
        except KeyError:
            *mods, kc = self.split_modified(k)
            if kc.lower() in self.mapping:
                return k
            else:
                raise KeyError(f"unknown ZMK keycode: {k}")

    def __getitem__(self, k: str) -> str:
        return self.lookup(k)


def fix_layer_name(name: str):
    return re.sub(r"[^0-9a-zA-Z]", "_", name)


def join_lines(lines: Iterable[Any], n: int = 1) -> str:
    return ("\n" * n).join(map(str, lines))
