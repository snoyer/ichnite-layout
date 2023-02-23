from argparse import ArgumentParser, Namespace
from dataclasses import replace
from functools import partial
from typing import Callable, Optional, TypeVar, cast

from .qmk import generate_qmk_code, qmk_translator_for_os
from .source import (Key, Keymap, extract_os_specifics_from_md,
                     join_layer_name, keymap_from_md, make_multi_os_layers,
                     split_layer_name)
from .translation import (Translator, dedup_keymaps_layers,
                          shorten_layers_names, translate_multi_os_layers)
from .zmk import generate_zmk_code, zmk_translator_for_os


def argument_parser():
    parser = ArgumentParser(description='generate ZMK/QMK keymap code from markdown tables')
    subparsers = parser.add_subparsers(dest='command', required=True)

    parser.add_argument('readme',
        metavar='README.MD', help='readme markdown filename')
    parser.add_argument('output',
        metavar='OUTPUT', help='output keymap filename')
    
    zmk = subparsers.add_parser('ZMK', help='create a ZMK keymap')
    zmk.add_argument('--transform', default='default_transform',
        metavar='NAME', help='matrix transform name')

    qmk = subparsers.add_parser('QMK', help='create a QMK layout')
    qmk.add_argument('--layout', default='LAYOUT',
        metavar='NAME', help='layout macro name')

    return parser

T = TypeVar('T')

def main(
    args: Namespace,
    keymap_preproc: Optional[Callable[[Keymap[str]], Keymap[Key]]]=None,
    translators_postproc: Optional[Callable[[Translator[T]], Translator[T]]] = None,
    default_key: Optional[Key]=None,
):
    source_keymap = keymap_from_md(open(args.readme))
    os_specific_codes = dict(extract_os_specifics_from_md(open(args.readme)))
    if not os_specific_codes:
        os_specific_codes[''] = {}
    
    if callable(keymap_preproc):
        source_keymap = keymap_preproc(source_keymap)
    else:
        source_keymap = cast(Keymap[Key], source_keymap)
    
    if default_key is not None:
        layers = source_keymap.layers.items()
        new_layers = {name:[b if b else default_key for b in layer] for name,layer in layers}
        keymap = replace(source_keymap, layers=new_layers)
    else:
        keymap = source_keymap
    
    def shorten_layer_name(name: str):
        base, variations = split_layer_name(name)
        if set(variations) == set(os_specific_codes):
            variations.clear()
        return join_layer_name(base, [''.join(v[:1] for v in variations)])

    def first_os_from_layer_name(name: str):
        _base, variations = split_layer_name(name)
        return variations[0] if variations else ''


    source_multi_layers = make_multi_os_layers(keymap.layers, os_specific_codes)


    dont_dedup: Callable[[str], bool] | None = None
    if args.command == 'ZMK':
        translator_for_os = zmk_translator_for_os
        generate_code = partial(generate_zmk_code, transform_name=args.transform)
    elif args.command == 'QMK':
        translator_for_os = qmk_translator_for_os
        base_name = 'base'
        dont_dedup = lambda name: name.startswith(base_name)

        uc_modes_by_os = {
            shorten_layer_name(join_layer_name(base_name, ['mac']))  : 'UNICODE_MODE_MACOS',
            shorten_layer_name(join_layer_name(base_name, ['linux'])): 'UNICODE_MODE_WINDOWS',
            shorten_layer_name(join_layer_name(base_name, ['win']))  : 'UNICODE_MODE_LINUX',
        }
        generate_code = partial(generate_qmk_code, layout_name=args.layout, uc_modes_by_base=uc_modes_by_os)
    else:
        raise ValueError(f'unsuported command: {args.command}')

    if not translators_postproc:
        translators_postproc = lambda x: x

    translators_by_os = {os:translators_postproc(translator_for_os(os)) for os in os_specific_codes.keys()}
    first_translator = next(iter(translators_by_os.values()))
    translated_layers = translate_multi_os_layers(source_multi_layers, translators_by_os.__getitem__, first_os_from_layer_name)
    translated_layers = dedup_keymaps_layers(translated_layers, first_translator.map_layer_names, ignore=dont_dedup)
    translated_layers = shorten_layers_names(translated_layers, first_translator.map_layer_names, shorten_layer_name)
    code = generate_code(translated_layers, source_keymap)
    

    if args.output == '-':
        print(code)
    else:
        with open(args.output, 'w') as f:
            f.write(code)
            f.write('\n')


if __name__ == '__main__':
    exit(main(argument_parser().parse_args()))