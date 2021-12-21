import argparse
import logging
import re
from dataclasses import dataclass, field, replace
from itertools import chain, groupby
from os.path import dirname
from os.path import join as path_join
from typing import (Any, Callable, Dict, Iterable, List, Optional, Sequence,
                    Set, Tuple)

from data import (UNSHIFTED, IntermediateBinding, Layer, TranslatedLayer,
                  Translator, extract_layers_from_md,
                  extract_os_specifics_from_md, format_layer,
                  make_os_specific_layers, split_combo)
from dt import Comment, Node, NodeOrComment, Raw
from tables import format_table

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='generate ZMK keymap code from markdown tables')

    parser.add_argument('readme',
        metavar='README.MD', help='readme markdown filename')
    parser.add_argument('output', nargs='?',
        metavar='OUTPUT.keymap', help='output .keymap filename')
    parser.add_argument('--3x5', action='store_true', dest='is_3x5',
        help='discard extra keys and make 3x5+3 layout')
    parser.add_argument('--transform', default='default_transform',
        metavar='NAME', help='ZMK transform name')

    args = parser.parse_args()

    layers = extract_layers_from_md(open(args.readme), make_3x5=args.is_3x5)
    os_specific_codes = dict(extract_os_specifics_from_md(open(args.readme)))

    if args.output:
        with open(args.output, 'w') as f:
            f.write(generate_zmk_code(layers, os_specific_codes, args.transform))
            f.write('\n')
    else:
        print(generate_zmk_code(layers, os_specific_codes, args.transform))




def generate_zmk_code(
    layers: Sequence[Layer[IntermediateBinding]],
    os_specific_aliases: Dict[str, Dict[str, str]],
    transform_name: str,
) -> str:
   
    ZMK_KEYCODES = ZmkKeycodes()
    aliases: Dict[str, Any] = {
        'PSCR': 'PRINTSCREEN',
        'SLCK': 'SCROLLLOCK',
        'PAUSE': 'PAUSE_BREAK',
        'APP': 'K_APP',

        'PLAY': 'C_PLAY_PAUSE',
        'STOP': 'C_STOP',
        'PAUSE': 'C_PAUSE',
        'PREV': 'C_PREV',
        'NEXT': 'C_NEXT',
        'FFW' : 'C_FF',
        'RWD' : 'C_RW',
        'VOL+': 'C_VOL_UP',
        'VOL-': 'C_VOL_DN',
        'MUTE': 'C_MUTE',

        'BRI+': 'C_BRI_UP',
        'BRI-': 'C_BRI_DN',

        'MYCOMP': 'C_AL_MY_COMPUTER',
        'WWW'   : 'C_AL_WWW',
        'CALC'  : 'C_AL_CALCULATOR',

        'RESET': '&reset',
        'BOOTL': '&bootloader',

        r'BT[0-5]$': lambda x: bt_macro(int(x[2:])), #type: ignore
        'BTCLR': '&bt BT_CLR',
        'USB': '&out OUT_USB',

        '\'"': "'",
        ',;' : shiftmorph_node(',', ';', ZMK_KEYCODES),
        '.?' : shiftmorph_node('.', '?', ZMK_KEYCODES),
        '/\\': shiftmorph_node('/', '\\', ZMK_KEYCODES),

        'XXX': '&none',
        '___': '&trans',
    }


    aliases_by_os = {os:{**aliases, **os_aliases} for os,os_aliases in os_specific_aliases.items()}
    for os,macro in (
        ('linux', utf8_linux_macro_node),
        ('mac'  , utf8_mac_macro_node),
        ('win'  , utf8_win_macro_node),
    ):
        aliases_by_os[os][r'[\u0080-\uffff]$'] = macro

    translated_layers, _ = make_os_specific_layers(
        layers, aliases_by_os,
        lambda s: ZmkTranslator(ZMK_KEYCODES, s)
    )


    layer_nodes, behavior_nodes, headers = make_zmk_layers(translated_layers)

    includes: Set[str] = set([
        '<behaviors.dtsi>',
        '<dt-bindings/zmk/keys.h>',
    ])
    includes |= set(chain.from_iterable(
        getattr(node, 'required_includes', []) for node in behavior_nodes #type: ignore
    ))

    return join_lines((
        join_lines(f'#include {include}' for include in sorted(includes)),

        join_lines(headers),

        Node('/', [
            Node('chosen', properties={
                'zmk,matrix_transform': Raw(f'&{transform_name}')
            }),
            Node('keymap', layer_nodes, properties={
                'compatible': 'zmk,keymap',
            }),
            Node('behaviors', behavior_nodes)
        ]),

        Node('&lt', properties={
            'flavor': "hold-preferred",
            'tapping-term-ms': 150,
            'quick-tap-ms': 200,
        }),

        Node('&hrm', properties={
            'flavor': "tap-preferred",
            'tapping-term-ms': 150,
            'quick-tap-ms': 200,
        }),
    ), 2)



def make_zmk_layers(
    translated_layers: Iterable[TranslatedLayer['ZmkBinding']]
) -> Tuple[List[NodeOrComment], List[NodeOrComment], List[str]]:

    behavior_nodes: Dict[str, Node] = {}
    layer_nodes: List[NodeOrComment] = []
    headers = [f'#define {layer.name} {i}' for i,layer in enumerate(translated_layers) if not isinstance(layer.name, int)]


    def make_comment(layer: TranslatedLayer['ZmkBinding']) -> str:
        return layer.title + '\n' + format_layer(layer.src_table)
    
    for comment,layers in groupby(translated_layers, key=make_comment):
        layer_nodes.append(Comment(comment))

        for layer in layers:
            bindings = format_table(layer.new_table, sep=' ', pad=' ', just=str.ljust)
            layer_nodes.append(Node(f'{layer.name}',
                properties = {
                    'bindings': Raw('<\n' + '\n'.join(l.rstrip() for l in bindings.splitlines()) + '\n>'),
                },
            ))

            for cell in filter(None, layer.new_table.cells()):
                for v in cell.nodes:
                    if not v.label is None:
                        behavior_nodes[v.label] = v
                    else:
                        raise ValueError('node has no label')


    return layer_nodes, list(behavior_nodes.values()), headers










@dataclass(frozen=True)
class ZmkBinding:
    behavior: object
    param1: Optional[str] = None
    param2: Optional[str] = None
    extra_nodes: List[Node] = field(default_factory=list)


    def __str__(self):
        return ' '.join(map(str, (
            '&'+self.label, *filter(None, (self.param1, self.param2))
        )))

    def behavior_is(self, *labels: Sequence[str]) -> bool:
        return self.label in labels
 
    @property
    def label(self) -> str:
        if isinstance(self.behavior, Node):
            if not self.behavior.label is None:
                return self.behavior.label
            else:
                raise ValueError('behavior has no label')
        else:
            return str(self.behavior).lstrip('&')
    
    @property
    def nodes(self):
        if isinstance(self.behavior, Node):
            return (self.behavior, *self.extra_nodes)
        else:
            return self.extra_nodes
    


class ZmkTranslator(Translator[ZmkBinding]):
    def __init__(self, zmk_keycodes: 'ZmkKeycodes', aliases: Any):
        super().__init__()
        self.native_keycodes = zmk_keycodes
        self._register_aliases(aliases)


    def _base_translate(self, k: IntermediateBinding) -> ZmkBinding:
        if isinstance(k, ZmkBinding):
            return k
        elif isinstance(k, Node):
            return ZmkBinding(k)
        elif isinstance(k, str):
            if re.match(r'&\w+', k):
                return ZmkBinding(k)
            else:
                try:
                    return ZmkBinding('kp', self.native_keycodes[k])
                except KeyError:
                    logger.warning(f'not implemented {k}')
                    return ZmkBinding('&none')
        else:
            raise ValueError(f'cannot make binding for {k}')



    def make_modtap(self, mod: ZmkBinding, tap: ZmkBinding) -> ZmkBinding:
        if mod.behavior_is('kp') and tap.behavior_is('kp'):
            HRM_NODE = Node('modtap', label='hrm', properties={
                'compatible': 'zmk,behavior-hold-tap',
                'label': 'HOMEROWMOD',
                '#binding-cells': 2,
                'bindings': Raw('<&kp>, <&kp>'),
            })
            return ZmkBinding(HRM_NODE, mod.param1, tap.param1)
        else:
            raise ValueError(f'cannot make modtap for {mod}, {tap}')


    def make_layertap(self, layer: str, tap: Optional[ZmkBinding]) -> ZmkBinding:
        if tap:
            if tap.behavior_is('kp'):
                return ZmkBinding('lt', layer, tap.param1)
            else:
                raise ValueError(f'cannot make layertap for {tap}')
        else:
            return ZmkBinding('mo', layer)


    def make_tolayer(self, layer: str) -> ZmkBinding:
        return ZmkBinding('to', layer)



    def replace_layer_ids(self, binding: ZmkBinding, f: Callable[[str], str]) -> ZmkBinding:
        if binding.behavior_is('lt','mo','to') and not binding.param1 is None:
            return replace(binding, param1=f(binding.param1))
        else:
            return binding



def macro_node(identifier: str, behaviors: Iterable[str], sleep: int=0, label: Optional[str]=None) -> Node:

    def fixed_behaviors():
        for b in behaviors:
            yield b if b.startswith('&') else f'&kp {b}'

    if not label:
        label = f'macro_{identifier}'

    properties = {
        'compatible': 'zmk,behavior-macro',
        'label': label,
        '#binding-cells': 0,
        'bindings': Raw(', '.join(f'<{x}>' for x in fixed_behaviors())),
    }
    if sleep:
        properties['sleep'] = sleep

    return Node(identifier, label=identifier, 
        properties = properties,
        comment = 'https://github.com/okke-formsma/zmk/tree/macros'
    )


def utf8_linux_macro_node(char: str) -> Node:
    hexstr = '%04x' % ord(char)
    return macro_node(f'u{hexstr}_L', 
        label = f'Linux {char} macro',
        behaviors = [
            'LC(LS(U))',
            *(d.upper() if d in 'abcdef' else 'N'+d for d in hexstr),
            'SPACE',
        ],
    )

def utf8_mac_macro_node(char: str) -> ZmkBinding:
    hexstr = '%04x' % ord(char)
    node = macro_node(f'u{hexstr}_M', 
        label = f'Mac {char} macro',
        behaviors = [
            '&sk4 LALT',
            *(d.upper() if d in 'abcdef' else 'N'+d for d in hexstr),
        ],
    )
    sk4_node = Node('sk4', label='sk4', properties={
            'compatible': "zmk,behavior-sticky-key",
            'label': "STICKY_KEY x4",
            '#binding-cells': 1,
            'release-after-ms': 200,
            'count': 4,
            'bindings': Raw('<&kp>'),
        },
        comment = 'https://github.com/snoyer/zmk/tree/stickier-keys'
    )
    return ZmkBinding(node, extra_nodes=[sk4_node])

def utf8_win_macro_node(char: str) -> Node:
    hexstr = '%04x' % ord(char)
    return macro_node(f'u{hexstr}_W', 
        label = f'Wincompose {char} macro',
        behaviors = [
            'RALT', 
            'U',
            *(d.upper() if d in 'abcdef' else 'N'+d for d in hexstr),
            'RET',
        ],
    )



def shiftmorph_node(default: str, shifted: str, zmk_keycodes: 'ZmkKeycodes') -> Node:
    a = zmk_keycodes[default]
    b = zmk_keycodes[shifted]
    is_custom_shift = not shifted in UNSHIFTED
    return Node(f'{a.lower()}_{b.lower()}', label=f'{a.lower()}_{b.lower()}',
        properties={
            'compatible': 'zmk,behavior-mod-morph',
            'label': f'shift-morph {a} {b}',
            '#binding-cells': 0,
            'bindings': Raw(f'<&kp {a}>, <&kp {b}>'),
            'mods': Raw('<(MOD_LSFT|MOD_RSFT)>'),
            'masked_mods': Raw('<(MOD_LSFT|MOD_RSFT)>') if is_custom_shift else None,
        }, 
        # comment = 'wont work because mod-morph doesnt clear modifiers :(' if is_custom_shift else ''
        comment = 'https://github.com/snoyer/zmk/tree/masked-mods' if is_custom_shift else ''
    )


def bt_macro(i: int) -> Node:
    node = macro_node(f'bt{i}',
        behaviors = [f'&bt BT_SEL {i-1}', '&out OUT_BLE'],
    )
    setattr(node, 'required_includes', [
        '<dt-bindings/zmk/bt.h>',
        '<dt-bindings/zmk/outputs.h>',
    ])
    return node


class ZmkKeycodes:
    def __init__(self, fn: str=path_join(dirname(__file__), 'zmk-keycodes.txt')):
        self.mapping: Dict[str, str] = dict()

        for line in open(fn):
            line = line.strip()
            if line and not line.startswith('#'):
                if '\t' in line:
                    left,right = line.split('\t')
                else:
                    left,right = line, ''

                left = left.split()
                right = right.split()
                shortest = min(left, key=len)
                for k in left + right:
                    self.mapping[k.lower()] = shortest

        self.MODIFIERS = {self[k]:v for k,v in dict(
            LEFT_SHIFT = 'LS',
            LEFT_CONTROL = 'LC',
            LEFT_ALT = 'LA',
            LEFT_GUI = 'LG',
            RIGHT_SHIFT = 'RS',
            RIGHT_CONTROL = 'RC',
            RIGHT_ALT = 'RA',
            RIGHT_GUI = 'RG',
        ).items()}
        self.MODIFIERS_RE = re.compile(r'^\s*(' + r'|'.join(self.MODIFIERS.values()) + r')\s*\(\s*(.+)\s*\)\s*$')


    def split_modified(self, k:str)  -> List[str]:
        if m := self.MODIFIERS_RE.match(k):
            return [m.group(1), *self.split_modified(m.group(2))]
        else:
            return [k,]

    def _base_lookup(self, k: str) -> str:
        if k.lower() in self.mapping:
            return self.mapping[k .lower()]
        else:
            raise KeyError(f'unknown ZMK keycode: {k}')

    def lookup(self, k: str) -> str:
        try:
            mods, kc = split_combo(k)
            kc = self._base_lookup(kc)
            mods = [self.MODIFIERS.get(self._base_lookup(mod)) for mod in mods]
            return '('.join(map(str, (*mods, kc))) + ')'*len(mods)
        except KeyError:
            *mods,kc = self.split_modified(k)
            if kc.lower() in self.mapping:
                return k
            else:
                raise KeyError(f'unknown ZMK keycode: {k}')

    def __getitem__(self, k: str) -> str:
        return self.lookup(k)




def join_lines(lines: Iterable[Any], n: int=1) -> str:
    return ('\n'*n).join(map(str, lines))



if __name__ == '__main__':
    main()
