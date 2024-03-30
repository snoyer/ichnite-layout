import logging
import re
from dataclasses import dataclass, replace
from itertools import chain, groupby
from os.path import abspath, dirname
from os.path import join as path_join
from typing import Callable, Optional, Union

from jinja2 import Environment, FileSystemLoader

from .asciitables import Table, format_table
from .source import Key, Keymap, format_layer, split_layer_name, split_mods
from .translation import Translator

logger = logging.getLogger(__name__)


def qmk_translator_for_os(os: str):
    translator = QmkTranslator(QmkKeycodes())

    translator.register_aliases(
        {
            "PLAY": "MPLY",
            "STOP": "MSTP",
            "MUTE": "MUTE",
            "PREV": "MPRV",
            "NEXT": "MNXT",
            "FFW": "MFFD",
            "RWD": "MRWD",
            "VOL+": "VOLU",
            "VOL-": "VOLD",
            "BRI+": "BRIU",
            "BRI-": "BRID",
            "PG_UP": "PGUP",
            "PG_DN": "PGDOWN",
            "SLOCK": "KC_SCRL",
            "NLOCK": "KC_NUM_LOCK",
            "MYCOMP": "MYCM",
            "CALC": "CALC",
            "WWW": "WHOM",
            "RESET": "QK_BOOT",
            "BOOTL": "QK_REBOOT",
            "DEBUG": "DB_TOGG",
            "XXXXX": "XXX",
        }
    )

    def unicode_binding(m: re.Match[str]):
        return QmkKey("UC", "0x%04x" % ord(m.group(1)))

    translator.register_translations(
        {
            r"([\u0080-\uffff])$": unicode_binding,
        }
    )

    return translator


def generate_qmk_code(
    translated_layers: dict[str, list["QmkBinding"]],
    source_keymap: Keymap[Key],
    layout_name: Optional[str] = "LAYOUT",
    uc_modes_by_base: Optional[dict[str, str]] = None,
) -> str:
    table_shape = source_keymap.table_shape

    def format_qmk_layer(name: str, bindings: list[QmkBinding]) -> str:
        bindings_str = format_table(
            Table.Shape(
                table_shape,
                [f"{QmkTranslator.map_layer_names(fix_c_name, s)}," for s in bindings],
                "",
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
        return f"[{fix_c_name(name)}] = {layout_name}(\n{args}\n)"

    def make_layer_blocks():
        for src, layers in groupby(
            translated_layers.items(), key=lambda kv: split_layer_name(kv[0])[0]
        ):
            table = Table.Shape(table_shape, source_keymap.layers[src], "")
            first_layer, *next_layers = layers
            comment = source_keymap.titles[src] + "\n" + format_layer(table)
            yield fix_c_name(first_layer[0]), f"/* {comment} */\n" + format_qmk_layer(
                *first_layer
            )
            for name, bindings in next_layers:
                yield fix_c_name(name), format_qmk_layer(name, bindings)

    all_keycodes = set(filter(None, chain.from_iterable(translated_layers.values())))
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


class QmkTranslator(Translator[QmkBinding]):
    def __init__(self, qmk_keycodes: "QmkKeycodes"):
        super().__init__()
        self.native_keycodes = qmk_keycodes

    def translate(self, key: Key, is_layer_name: Callable[[str], bool]) -> QmkBinding:
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
                    return QmkKey(self.native_keycodes[t])
                except KeyError:
                    logger.warning(f"not implemented {t!r}")
                    return QmkKey("KC_NO")

        if key.hold:
            if is_layer_name(key.hold):
                layer = key.hold
                if key.tap:
                    tap = g(key.tap)
                    if isinstance(tap, QmkKey):
                        if not self.native_keycodes.is_simple_keycode(tap.value):
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
                        return QmkModtap(self.native_keycodes.MODTAPS[hold], tap.value)
                    raise ValueError(f"cannot nodtap for {hold}, {tap}")
                else:
                    return QmkKey(hold)

        if key.tap and is_layer_name(key.tap.removeprefix("@")):
            return QmkTO(key.tap.removeprefix("@"))

        if key.tap and not key.hold:
            return g(key.tap)

        return QmkKey("KC_NO")

    @classmethod
    def map_layer_names(
        cls, f: Callable[[str], str], binding: QmkBinding
    ) -> QmkBinding:
        if isinstance(binding, (QmkMO, QmkLT, QmkTO)):
            return replace(binding, layer=f(binding.layer))
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
