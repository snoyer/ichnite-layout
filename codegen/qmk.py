import argparse
import logging
import re
from dataclasses import dataclass, replace
from itertools import chain, groupby
from os.path import abspath, dirname
from os.path import join as path_join
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Union

from jinja2 import Environment, FileSystemLoader

from data import (IntermediateBinding, Layer, TranslatedLayer, Translator,
                  extract_layers_from_md, extract_os_specifics_from_md,
                  format_layer, make_os_specific_layers, split_combo)
from tables import format_table

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='generate QMK keymap code from markdown tables')

    parser.add_argument('readme',
        metavar='README.MD', help='readme markdown filename')
    parser.add_argument('output', nargs='?',
        metavar='OUTPUT.H', help='output .h filename')
    parser.add_argument('--3x5', action='store_true', dest='is_3x5',
        help='discard extra keys and make 3x5+3 layout')
    parser.add_argument('--layout', default='LAYOUT',
        metavar='NAME', help='QMK layout macro name')

    args = parser.parse_args()

    layers = extract_layers_from_md(open(args.readme), make_3x5=args.is_3x5)
    os_specific_aliases = dict(extract_os_specifics_from_md(open(args.readme)))

    layout_name = 'LAYOUT_split_3x5_3' if args.is_3x5 else args.layout

    if args.output:
        with open(args.output, 'w') as f:
            f.write(generate_qmk_code(layers, os_specific_aliases, layout_name))
    else:
        print(generate_qmk_code(layers, os_specific_aliases, layout_name))



def generate_qmk_code(
    layers: Sequence[Layer[IntermediateBinding]],
    os_specific_aliases: Dict[str, Dict[str, str]],
    layout_name: str,
) -> str:

    QMK_KEYCODES = QmkKeycodes()
    aliases: Dict[str, Any] = {
        'PLAY': 'MPLY',
        'STOP': 'MSTP',
        'MUTE': 'MUTE',
        'PREV': 'MPRV',
        'NEXT': 'MNXT',
        'FFW' : 'MFFD',
        'RWD' : 'MRWD',
        'VOL+': 'VOLU',
        'VOL-': 'VOLD',
        'BRI+': 'BRIU',
        'BRI-': 'BRID',

        'PG_UP': 'PGUP',
        'PG_DN': 'PGDOWN',

        'MYCOMP': 'MYCM',
        'CALC'  : 'CALC',
        'WWW'   : 'WHOM',

        'RESET': 'RESET',
        'BOOTL': 'RESET',
        'DEBUG': 'DEBUG',

        '\'"': CustomShift('KC_QUOT', 'KC_DQUO'),
        ',;' : CustomShift('KC_COMM', 'KC_SCLN'),
        '.?' : CustomShift('KC_DOT', 'KC_QUES'),
        '/\\': CustomShift('KC_SLSH', 'KC_BSLS'),

        r'[\u0080-\uffff]$': lambda k: QmkKey('UC', '0x%04x'%ord(k)), #type: ignore
    }

    aliases_by_os = {os:{**aliases, **os_aliases} for os,os_aliases in os_specific_aliases.items()}
    translated_layers, bases_by_os = make_os_specific_layers(
        layers, aliases_by_os,
        lambda s: QmkTranslator(QMK_KEYCODES, s)
    )

    uc_modes_by_os = {
        'mac'  : 'UC_OSX',
        'linux': 'UC_LNX',
        'win'  : 'UC_WIN',
    }
    uc_modes = {base:uc_modes_by_os[os] for os,base in bases_by_os.items()}

    def format_qmk_layer(layer: TranslatedLayer[QmkBinding]) -> str:
        bindings = format_table(layer.new_table.map(lambda s: (str(s)+',') if s else s), sep=' ', pad='', just=str.ljust)
        args = indent_lines(
            '\n'.join(l.rstrip() for l in bindings.splitlines()).rstrip(' ,'),
            '\t'
        )
        return f'[{layer.name}] = {layout_name}(\n{args}\n)'

    def make_layer_blocks():
        for comment,layers in groupby(translated_layers, key=lambda x:x.title + '\n' + format_layer(x.src_table)):
            layer = next(layers)
            yield  layer.name, f'/* {comment} */\n' + format_qmk_layer(layer)
            for layer in layers:
                yield layer.name, format_qmk_layer(layer)

    all_keycodes = set(filter(None, chain.from_iterable(l.new_table.cells() for l in translated_layers)))
    customLTs = set(k for k in all_keycodes if isinstance(k, CustomLT))
    customShifts = set(k for k in all_keycodes if isinstance(k,CustomShift))


    env = Environment('/*%', '*/', '/*=', '*/', '/*#', '*/',
        loader = FileSystemLoader(abspath(dirname(__file__)))
    )
    template = env.get_template("qmk.template.h")
    return template.render(
        layer_blocks = dict(make_layer_blocks()),
        uc_modes = uc_modes.items(),
        custom_shifts = customShifts,
        custom_LTs = customLTs,
    )



def indent_lines(s: str, indent: str='\t'):
    return '\n'.join(indent+l for l in s.splitlines())


def fix_c_name(name: str):
    return re.sub(r'[^A-Za-z0-9_]','_', name)


@dataclass(frozen=True)
class CustomShift:
    normal: str
    shifted: str

    def __str__(self):
        return self.normal


@dataclass(frozen=True)
class QmkKey:
    value: str
    param: Optional[str] = None

    def __str__(self):
        if self.param != None:
            return f'{self.value}({self.param})'
        else:
            return self.value

class QmkModtap(QmkKey): pass


@dataclass(frozen=True)
class QmkLT:
    layer: str
    keycode: str

    def __str__(self):
        return f'LT({self.layer},{self.keycode})'


@dataclass(frozen=True)
class QmkMO:
    layer: str

    def __str__(self):
        return f'MO({self.layer})'


@dataclass(frozen=True)
class QmkTO:
    layer: str

    def __str__(self):
        return f'TO({self.layer})'


@dataclass(frozen=True)
class CustomLT(QmkLT):
    @property
    def identifier(self):
        k = fix_c_name(re.sub(r'(KC_|\))', '', self.keycode))
        return f'LT_{self.layer}_{k}'

    def __str__(self):
        return f'TD({self.identifier})'



QmkBinding = Union[QmkKey, QmkLT, QmkMO, QmkTO, CustomShift]

class QmkTranslator(Translator[QmkBinding]):

    def __init__(self, qmk_keycodes: 'QmkKeycodes', aliases: Any):
        super().__init__()
        self.native_keycodes = qmk_keycodes
        self._register_aliases(aliases)



    def _base_translate(self, k: IntermediateBinding) -> QmkBinding:
        if isinstance(k, (QmkKey, QmkLT, QmkMO, QmkTO, CustomShift)):
            return k
        if isinstance(k, str):
            try:
                return QmkKey(self.native_keycodes[k])
            except KeyError:
                logger.warning('not implemented %s', k)
                return QmkKey('KC_NO')
        raise ValueError(k)


    def make_layertap(self, layer: str, tap: Optional[QmkBinding]) -> QmkBinding:
        if tap is None:
            return QmkMO(layer)
        if isinstance(tap, QmkKey):
            if not self.native_keycodes.is_simple_keycode(tap.value):
                return CustomLT(layer, tap.value)
            return QmkLT(layer, tap.value)
        raise ValueError(f'cannot make LT for {layer}, {tap}')
    

    def make_modtap(self, mod: QmkBinding, tap: QmkBinding) -> QmkBinding:
        if isinstance(mod, QmkKey) and isinstance(tap, QmkKey):
            return QmkModtap(self.native_keycodes.MODTAPS[mod.value], tap.value)
        else:
            raise ValueError(f'cannot nodtap for {mod}, {tap}')


    def make_tolayer(self, layer: str) -> QmkBinding:
        return QmkTO(layer)


    def replace_layer_ids(self, binding: QmkBinding, f: Callable[[str], str]) -> QmkBinding:
        if isinstance(binding, (QmkMO, QmkLT, QmkTO)):
            return replace(binding, layer=f(binding.layer))
        else:
            return binding


class QmkKeycodes:
    def __init__(self, fn: str = path_join(dirname(__file__), 'qmk-keycodes.txt')):
        self.basic_keycodes: Set[str] = set()
        self.mapping: Dict[str, str] = dict()

        section = ''

        for line in open(fn):
            line = line.strip()

            if m := re.match(r'\#+ +(.+)', line):
                section = m.group(1)
            
            elif line and not line.startswith('#'):
                if '\t' in line:
                    left, right = line.split('\t')
                else:
                    left, right = line, ''

                left = left.split()
                right = right.split()
                shortest = min(left, key=len)
                for k in left + right:
                    self.mapping[k.lower()] = shortest
                
                if 'basic' in section:
                    self.basic_keycodes |= set(left)

        self.MODIFIERS = {self.mapping['kc_'+v.lower()]: v for v in [
            'LCTL', 'LSFT', 'LALT', 'LGUI',
            'RCTL', 'RSFT', 'RALT', 'RGUI',
        ]}

        self.MODTAPS = {f'KC_{c}': f'{c}_T' for c in [
            'LSFT', 'RSFT',
            'LCTL', 'RCTL',
            'LALT', 'RALT',
            'LGUI', 'RGUI',
        ]}

        self.MODIFIERS_RE = re.compile(
            r'^\s*(' + r'|'.join(self.MODIFIERS.values()) +
            r')\s*\(\s*(.+)\s*\)\s*$'
        )
    

    def is_simple_keycode(self, kc: str) -> bool:
        return kc in self.basic_keycodes


    def split_modified(self, k: str) -> List[str]:
        if m := self.MODIFIERS_RE.match(k):
            return [m.group(1), *self.split_modified(m.group(2))]
        else:
            return [k,]


    def _base_lookup(self, k: str) -> str:
        if k.lower() in self.mapping:
            return self.mapping[k.lower()]
        if 'kc_'+k.lower() in self.mapping:
            return self.mapping['kc_'+k.lower()]
        raise KeyError(f'unknown QMK keycode: {k}')


    def lookup(self, k: str) -> str:
        try:
            mods, kc = split_combo(k)
            kc = self._base_lookup(kc)
            mods = [self.MODIFIERS.get(self._base_lookup(mod)) for mod in mods]
            return '('.join(map(str, (*mods, kc))) + ')'*len(mods)
        except KeyError:
            *mods, kc = self.split_modified(k)
            if kc.lower() in self.mapping:
                return k
            raise KeyError(f'unknown QMK keycode: {k}')
    

    def __getitem__(self, k: str) -> str:
        return self.lookup(k)



if __name__ == '__main__':
    main()
