from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from itertools import chain, groupby
from os.path import abspath, dirname
from os.path import join as path_join
from typing import Callable, Iterable, Mapping, Optional, Union

from jinja2 import Environment, FileSystemLoader

from .asciitables import Table, cjust, format_boxed_table, format_table
from .source import (
    Key,
    Keymap,
    LayerName,
    join_layer_name,
    split_mods,
)
from .zmk import LayerBase

logger = logging.getLogger(__name__)


def generate_qmk_layout_code(
    keymap: Keymap[str, Key],
    titles: Mapping[str, str],
    multi_os_layers: Iterable[tuple[tuple[str, str], list[Key]]],
    *,
    layout_name: Optional[str] = "LAYOUT",
    aliases_for_os: Callable[
        [str], dict[str, str | QmkBinding | Callable[[re.Match[str]], str | QmkBinding]]
    ]
    | None = None,
) -> str:
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
        )
        for (source_layer, os), keys in multi_os_layers
    ]

    base_name = binding_layers[0].source_layer
    uc_modes_by_base = {
        Layer.Shorten_name(join_layer_name(base_name, ["mac"])): "UNICODE_MODE_MACOS",
        Layer.Shorten_name(
            join_layer_name(base_name, ["linux"])
        ): "UNICODE_MODE_WINDOWS",
        Layer.Shorten_name(join_layer_name(base_name, ["win"])): "UNICODE_MODE_LINUX",
    }

    binding_layers = [
        layer.rename_layers_in_bindings(layer.Shorten_name)
        for layer in Layer.Deduplicate(binding_layers, exceptions=("base",))
    ]

    def format_qmk_layer(layer: Layer, with_comment: bool = True) -> str:
        bindings_str = format_table(
            Table.Shape(
                keymap.table_shape, [f"{binding}," for binding in layer.bindings], ""
            ),
            sep=" ",
            pad="",
            just=str.ljust,
        )
        args = indent_lines(
            "\n".join(layer.rstrip() for layer in bindings_str.splitlines()).rstrip(
                " ,"
            ),
            "\t",
        )
        if with_comment:
            table = Table.Shape(
                keymap.table_shape, keymap.layers[layer.source_layer], ""
            )
            formatted = format_boxed_table(
                table.map_contents(lambda x: cjust(str(x).strip(), 5))
            )
            comment = f"/* {titles[layer.source_layer]}\n{formatted} */\n"
        else:
            comment = ""

        return f"{comment}[{fix_c_name(layer.name)}] = {layout_name}(\n{args}\n)"

    def make_layer_blocks():
        for _source_layer, layers in groupby(
            binding_layers, key=lambda layer: layer.source_layer
        ):
            for i, layer in enumerate(layers):
                yield (
                    fix_c_name(layer.name),
                    format_qmk_layer(layer, with_comment=i == 0),
                )

    all_keycodes = set(chain.from_iterable(layer.bindings for layer in binding_layers))
    customLTs = set(k for k in all_keycodes if isinstance(k, CustomLT))
    customShifts = set(k for k in all_keycodes if isinstance(k, CustomShift))

    env = Environment(
        "/*%",
        "*/",
        "/*=",
        "*/",
        "/*#",
        "*/",
        loader=FileSystemLoader(abspath(dirname(__file__))),
    )
    template = env.get_template("qmk.template.h")
    return template.render(
        layer_blocks=dict(make_layer_blocks()),
        uc_modes=(
            sorted((fix_c_name(k), v) for k, v in uc_modes_by_base.items())
            if uc_modes_by_base
            else []
        ),
        custom_shifts=sorted(customShifts),
        custom_LTs=sorted(customLTs),
    )


def indent_lines(s: str, indent: str = "\t"):
    return "\n".join(indent + layer for layer in s.splitlines())


def fix_c_name(name: str):
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


@dataclass(frozen=True, order=True)
class CustomShift:
    normal: str
    shifted: str

    def __str__(self):
        return self.normal


@dataclass(frozen=True, order=True)
class QmkKey:
    value: str
    param: Optional[str] = None

    def __str__(self):
        if self.param is not None:
            return f"{self.value}({self.param})"
        else:
            return self.value


class QmkModtap(QmkKey):
    pass


@dataclass(frozen=True, order=True)
class QmkLT:
    layer: str
    keycode: str

    def __str__(self):
        return f"LT({self.layer},{self.keycode})"


@dataclass(frozen=True)
class QmkMO:
    layer: str

    def __str__(self):
        return f"MO({self.layer})"


@dataclass(frozen=True)
class QmkTO:
    layer: str

    def __str__(self):
        return f"TO({self.layer})"


@dataclass(frozen=True)
class CustomLT(QmkLT):
    @property
    def identifier(self):
        k = fix_c_name(re.sub(r"(KC_|\))", "", self.keycode))
        return f"LT_{self.layer}_{k}"

    def __str__(self):
        return f"TD({self.identifier})"


QmkBinding = Union[QmkKey, QmkLT, QmkMO, QmkTO, CustomShift]


@dataclass
class Layer(LayerBase[QmkBinding]):
    @classmethod
    def Rename_layer_in_binding(
        cls, binding: QmkBinding, rename_func: Callable[[str], str]
    ):
        if isinstance(binding, (QmkMO, QmkLT, QmkTO)):
            return replace(binding, layer=rename_func(binding.layer))
        else:
            return binding


class QmkKeycodes:
    def __init__(self, fn: str = path_join(dirname(__file__), "qmk-keycodes.txt")):
        self.basic_keycodes: set[str] = set()
        self.mapping: dict[str, str] = dict()

        section = ""

        for line in open(fn):
            line = line.strip()

            if m := re.match(r"\#+ +(.+)", line):
                section = m.group(1)

            elif line and not line.startswith("#"):
                if "\t" in line:
                    left, right = line.split("\t")
                else:
                    left, right = line, ""

                left = left.split()
                right = right.split()
                shortest = min(left, key=len)
                for k in left + right:
                    self.mapping[k.lower()] = shortest

                if "basic" in section:
                    self.basic_keycodes |= set(left)

        self.MODIFIERS = {
            self.mapping["kc_" + v.lower()]: v
            for v in [
                "LCTL",
                "LSFT",
                "LALT",
                "LGUI",
                "RCTL",
                "RSFT",
                "RALT",
                "RGUI",
            ]
        }

        self.MODTAPS = {
            f"KC_{c}": f"{c}_T"
            for c in [
                "LSFT",
                "RSFT",
                "LCTL",
                "RCTL",
                "LALT",
                "RALT",
                "LGUI",
                "RGUI",
            ]
        }

        self.MODIFIERS_RE = re.compile(
            r"^\s*(" + r"|".join(self.MODIFIERS.values()) + r")\s*\(\s*(.+)\s*\)\s*$"
        )

    def is_simple_keycode(self, kc: str) -> bool:
        return kc in self.basic_keycodes

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
        if "kc_" + k.lower() in self.mapping:
            return self.mapping["kc_" + k.lower()]
        raise KeyError(f"unknown QMK keycode: {k}")

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
            raise KeyError(f"unknown QMK keycode: {k}")

    def __getitem__(self, k: str) -> str:
        return self.lookup(k)


QMK_KEYCODES = QmkKeycodes()


class BindingTranslator:
    def __init__(
        self,
        aliases: Mapping[
            str, str | QmkBinding | Callable[[re.Match[str]], str | QmkBinding]
        ],
    ) -> None:
        self.aliases: dict[str, str | QmkBinding] = {}
        self.callable_aliases: dict[
            re.Pattern[str], Callable[[re.Match[str]], str | QmkBinding]
        ] = {}
        for k, v in aliases.items():
            if callable(v):
                self.callable_aliases[re.compile(k)] = v
            else:
                self.aliases[k] = v

    def __call__(self, key: Key):
        def f(s: str):
            t = self.follow_aliases(s)
            try:
                return QMK_KEYCODES[t]
            except KeyError:
                return t

        def g(s: str):
            t = self.follow_aliases(s)
            if isinstance(t, QmkBinding):
                return t
            else:
                try:
                    return QmkKey(QMK_KEYCODES[t])
                except KeyError:
                    logger.warning(f"not implemented {t!r}")
                    return QmkKey("KC_NO")

        if key.hold:
            if isinstance(key.hold, LayerName):
                layer = key.hold
                if key.tap:
                    tap = g(key.tap)
                    if isinstance(tap, QmkKey):
                        if not QMK_KEYCODES.is_simple_keycode(tap.value):
                            return CustomLT(layer, tap.value)
                        else:
                            return QmkLT(layer, tap.value)
                else:
                    return QmkMO(layer)

                raise ValueError(f"cannot make LT for {layer}, {key.tap}")

            hold = f(key.hold)
            if re.match(r"KC_[LR]?(GUI|ALT|CTR?L|SH?I?FT)", hold):
                if key.tap:
                    tap = g(key.tap)
                    if isinstance(tap, QmkKey):
                        return QmkModtap(QMK_KEYCODES.MODTAPS[hold], tap.value)
                    raise ValueError(f"cannot nodtap for {hold}, {tap}")
                else:
                    return QmkKey(hold)

        if key.tap and isinstance(key.tap.removeprefix("@"), LayerName):
            return QmkTO(key.tap.removeprefix("@"))

        if key.tap and not key.hold:
            return g(key.tap)

        return QmkKey("KC_NO")

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

            if isinstance(found, QmkBinding):
                return found
            else:
                seen.add(found)
                txt = found
                break
        return txt

    def translate_binding(self, txt: str):
        found = self.follow_aliases(txt)
        if isinstance(found, QmkBinding):
            return found
        else:
            return QmkKey(QMK_KEYCODES.lookup(found))
