from functools import partial
import re
from dataclasses import replace
from operator import __not__
from typing import Mapping, Optional, Sequence, TypeVar, cast


from codegen.__main__ import argument_parser
from codegen.__main__ import main as codegen_main
from codegen.asciitables import Table
from codegen.qmk import CustomShift, QmkTranslator
from codegen.source import MODIFIERS_RE, Keymap, Key
from codegen.translation import Translator
from codegen.zmk import Binding, ZmkTranslator, kp_binding, shiftmorph_node

T = TypeVar('T')

def main():
    parser = argument_parser()
    parser.add_argument('--reshape', dest='reshape',
        help='alternative layout to reshape to', choices=ALT_LAYOUTS.keys())

    args = parser.parse_args()

    return codegen_main(args, partial(combine_keymap, reshape=args.reshape), customize_translator, default_key=Key.Empty())

def customize_translator(translator: Translator[T]) -> Translator[T]:
    if isinstance(translator, ZmkTranslator):
        translator.register_translations({
            '\'"': kp_binding(translator.native_keycodes["'"]),
            ',;' : Binding(shiftmorph_node(',', ';', translator.native_keycodes)),
            '.?' : Binding(shiftmorph_node('.', '?', translator.native_keycodes)),
            '/\\': Binding(shiftmorph_node('/', '\\', translator.native_keycodes)),
        })
    elif isinstance(translator, QmkTranslator):
        translator.register_translations({
            '\'"': CustomShift('KC_QUOT', 'KC_DQUO'),
            ',;' : CustomShift('KC_COMM', 'KC_SCLN'),
            '.?' : CustomShift('KC_DOT', 'KC_QUES'),
            '/\\': CustomShift('KC_SLSH', 'KC_BSLS'),
        })
    return translator

def combine_keymap(source_keymap: Keymap[str], reshape: Optional[str] = None):
    keymap = add_holdtaps(source_keymap)
    keymap = add_paths_from_titles(keymap)
    if reshape:
        src = Table.Parse(ALT_LAYOUTS['source'])
        dst = Table.Parse(ALT_LAYOUTS[reshape]).remove_cells(__not__)
        keymap = keymap.reshape(src, dst, Key.Empty())
    return keymap


def add_holdtaps(txt_keymap: Keymap[str], holdtap_table_name: str='hold-tap', mods_on_all_layers: bool=False):
    def make_taphold(tap: str, hold: str, layers: bool=True, mods: bool=True):
        if hold:
            if hold in txt_keymap.layers:
                if layers:
                    return Key(hold=hold, tap=tap)
            elif re.match(MODIFIERS_RE, hold):
                if mods and tap != hold:
                    return Key(hold=hold, tap=tap)
            else:
                raise ValueError(f'hold-tap key ie neither layer-tap or mod-tap: {hold}')

        return Key(tap=tap)

    if holdtap_table_name in txt_keymap.layers:
        taphold = txt_keymap.layers.pop(holdtap_table_name)
        def new_layers():
            for i, (name, keys) in enumerate(txt_keymap.layers.items()):
                first = i==0
                f = partial(make_taphold, layers=first, mods=first or mods_on_all_layers)
                yield name, list(map(f, keys, taphold))
        keymap = replace(txt_keymap, layers=dict(new_layers()))
    else:
        keymap = txt_keymap

    return cast(Keymap[Key], keymap)


def add_paths_from_titles(keymap: Keymap[Key]):
    def parse_paths(title: str):
        for code in re.findall(r'`([^`]+)`', title):
            if m := re.match(r'([\w+]+)(?:([>,])|([+&]))([\w+]+)', code):
                a, _, f2, b = m.groups()
                yield [str(a), str(b)]
                if f2:
                    yield [str(b), str(a)]
            else:
                yield [str(code)]

    paths_by_id = {name:list(parse_paths(title)) for name,title in keymap.titles.items()}
    print(f'{paths_by_id = }')
    return add_paths(keymap, paths_by_id)


def add_paths(keymap: Keymap[Key], paths_by_id: Mapping[str, Sequence[Sequence[str]]]):
    layertaps = {i:x.hold for i,x in enumerate(keymap.layers['base']) if x.hold in keymap.layers}

    for layer_name, cells in keymap.layers.items():
        for path in paths_by_id.get(layer_name, []):
            for src, dst in zip(path, path[1:]):
                cells = keymap.layers[src]
                for i,layer in layertaps.items():
                    if layer == dst:
                        cells[i].hold = layer_name

    return keymap


ALT_LAYOUTS = {
    'source': r'''
    |a|b|c|d|e|     |E|D|C|B|A|
    |f|g|h|i|j|k| |K|J|I|H|G|F|
    |l|m|n|o|p|q| |Q|P|O|N|M|L|
    |   |r|s|t|     |T|S|R|   |
    ''',

    'split3x5+3': r'''
    |a|b|c|d|e| |E|D|C|B|A|
    |f|g|h|i|j| |J|I|H|G|F|
    |l|m|n|o|p| |P|O|N|M|L|
    |   |r|s|t| |T|S|R|   |
    ''',
    
    'ortho4x12': r'''
    |a|b|c|d|e|-|-|E|D|C|B|A|
    |f|g|h|i|j|k|K|J|I|H|G|F|
    |l|m|n|o|p|q|Q|P|O|N|M|L|
    |-|-|-|r|s|t|T|S|R|-|-|-|
    ''',
}


if __name__ == '__main__':
    main()
