import os
import re
from itertools import chain, zip_longest
import string
import argparse

from data import *



def main():

    parser = argparse.ArgumentParser(description='generate QMK keymap code from markdown tables')

    parser.add_argument('readme', nargs='?', default='readme.md',
        metavar='README.MD', help='readme.md filename')
    parser.add_argument('output', nargs='?',
        metavar='OUTPUT.H', help='output.h filename')

    args = parser.parse_args()

    layers = layers_from_tables(extract_tables_from_md(open(args.readme)))

    if args.output:
        with open(args.output, 'w') as f:
            f.write('// generated from `%s`\n\n' % os.path.relpath(args.readme, os.path.dirname(args.output)))
            f.write(generate_qmk_code(layers))
            f.write('\n')
    else:
        print(generate_qmk_code(layers))



def generate_qmk_code(layers):

    qmk_layers = {fix_c_name(k):list(map(lambda c:to_qmk_keycode(c, 'KC_NO', layers.keys()), v)) for k,v in layers.items()}

    shifts = {c['default']:c['shift'] for c in layers['base']
                                      if isinstance(c, dict) and 'shift' in c and 'default' in c}

    kcs = chain.from_iterable(qmk_layers.values())
    customs = list(chain.from_iterable(re.findall(r'(?:\W|^)(_\w+)', kc) for kc in kcs))


    def format_layer(layer):
        name, keys = layer
        table = [keys[i:i+10] for i in range(0, len(keys), 10)]
        ws = [max(map(len,col)) for col in zip_longest(*table, fillvalue=[])]
        args = ',\n'.join('\t\t'+(', '.join(c.ljust(max(8,w)) for c,w in zip(row,ws))) for row in table)
        return f'\t[{name}] = LAYOUT_split_3x5_3(\n{args}\n\t)'

    return '\n'.join([
        'enum layers {',
        '\t' + ', '.join(x+y for x,y in zip_longest(qmk_layers, ['=0'], fillvalue='')),
        '};',

        'enum custom_keys {',
        '\t' + ', '.join(x+y for x,y in zip_longest(customs, ['=SAFE_RANGE'], fillvalue='')),
        '};',

        'const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {',
        ',\n'.join(map(format_layer, qmk_layers.items())),
        '};',

        'const uint16_t PROGMEM shifty_shifts[][2] = {',
        ',\n'.join(['\t{ %-8s, %-8s }' % tuple(map(to_qmk_keycode, pair)) for pair in shifts.items()]),
        '};',
    ])



def fix_c_name(name):
    return re.sub(r'[^A-Za-z0-9_]','_', name)


def gen_keycodes():
    for c in string.ascii_lowercase:
        yield c, f'KC_{c.upper()}'
        yield c.upper(), f'KC_{c.upper()}'
    for i in range(10):
        yield f'{i}', f'KC_{i}'
    for i in range(24):
        yield f'F{i}', f'KC_F{i}'

    for k,v in {
        'SHIFT': 'LSFT',
        'CTRL' : 'LCTL',
        'ALT'  : 'LALT',
        'GUI'  : 'LGUI',
        'SUPER': 'LGUI',
        'OS'   : 'LGUI',
        'APP'  : 'APP',

        'ESC'  : 'ESC',
        'TAB'  : 'TAB',
        'BSPC' : 'BSPC',
        'DEL'  : 'DEL',
        'SPACE': 'SPC',
        'ENTER': 'ENT',

        'PAUSE': 'PAUS',
        'INS'  : 'INS',
        'PSCR' : 'PSCR',
        'SLCK' : 'SLCK',

        'LEFT' : 'LEFT',
        'RIGHT': 'RIGHT',
        'UP'   : 'UP',
        'DOWN' : 'DOWN',

        'HOME' : 'HOME',
        'END'  : 'END',
        'PG_U' : 'PGUP',
        'PG_D' : 'PGDOWN',

        'WH_L': 'WH_L',
        'WH_R': 'WH_R',
        'WH_U': 'WH_U',
        'WH_D': 'WH_D',

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

        'MYCOMP': 'MYCM',
        'CALC'  : 'CALC',
        'WWW'   : 'WHOM',

        "PIPE": 'PIPE',
        "|": 'PIPE',
        "'": 'QUOT',
        ' ': 'SPC',
        '"': 'DQUO',
        '`': 'GRV',
        '~': 'TILD',
        '+': 'PLUS',
        '-': 'MINS',
        '*': 'ASTR',
        '_': 'UNDS',
        '=': 'EQL',
        '(': 'LPRN',
        ')': 'RPRN',
        '[': 'LBRC',
        ']': 'RBRC',
        '{': 'LCBR',
        '}': 'RCBR',
        '<': 'LT',
        '>': 'GT',
       '\\': 'BSLS',
        '.': 'DOT',
        ',': 'COMM',
        ':': 'COLN',
        ';': 'SCLN',
        '/': 'SLSH',
        '|': 'PIPE',
        '?': 'QUES',
        '!': 'EXLM',
        '@': 'AT',
        '#': 'HASH',
        '$': 'DLR',
        '%': 'PERC',
        '^': 'CIRC',
        '&': 'AMPR',

        'XXX': 'NO',
    }.items():
        yield k, f'KC_{v}'


    yield from {
        'OSX'  : 'UC_M_MA',
        'LINUX': 'UC_M_LN',
        'WIN'  : 'UC_M_WI',

        'RESET': 'RESET',
        'DEBUG': 'DEBUG',

        'FIND+': '_FINDNEXT',
        'FIND-': '_FINDPREV',

        'COPY' : '_COPY',
        'CUT'  : '_CUT',
        'PASTE': '_PASTE',
        'UNDO' : '_UNDO',
        'REDO' : '_REDO',
    }.items()





KEYCODES = dict(gen_keycodes())
MODTAPS = {f'KC_{c}':f'{c}_T' for c in [
    'LSFT', 'RSFT',
    'LCTL', 'RCTL',
    'LALT', 'RALT',
    'LGUI', 'RGUI',
]}


def to_qmk_keycode(kc, none='KC_NO', layer_ids=None):
    if not kc:
        return none

    if isinstance(kc, dict):
        kc = {k:to_qmk_keycode(v, none=none, layer_ids=layer_ids) if v else v for k,v in kc.items()}
        default = kc.get('default')
        hold = kc.get('hold')
        if hold:
            if layer_ids and hold in layer_ids:
                if default:
                    return f'LT({fix_c_name(hold)},{default})'
                else:
                    return f'MO({fix_c_name(hold)})'

            if hold in MODTAPS:
                return f'{MODTAPS[hold]}({default})'

            raise ValueError(kc)
        else:
            return default
    elif layer_ids and kc in layer_ids:
        return kc
    elif kc in KEYCODES:
        return KEYCODES[kc]
    elif kc and len(kc)==1:
        return 'UC(0x%04x)'%ord(kc)
    else:
        raise ValueError(kc)



if __name__ == '__main__':
    main()
