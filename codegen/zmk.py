import argparse
import logging
import re
from dataclasses import dataclass, replace
from functools import cache
from itertools import groupby
from os.path import dirname
from os.path import join as path_join
from typing import (Any, Callable, Dict, Iterable, List, Optional, Sequence,
                    Tuple, Union)

from dt import Comment, Node, NodeOrComment, Raw, format_value
from source import (Layer, SourceBinding, extract_layers_from_md,
                    extract_os_specifics_from_md, format_layer, split_combo)
from tables import Shape, Table, format_table
from translation import TranslatedLayer, Translator, make_os_specific_layers

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
    layers: Sequence[Layer[SourceBinding]],
    os_specific_aliases: Dict[str, Dict[str, str]],
    transform_name: str,
) -> str:

    ZMK_KEYCODES = ZmkKeycodes()
    aliases: Dict[str, Any] = {
        'PSCR': 'PRINTSCREEN',
        'SLOCK': 'SCROLLLOCK',
        'NLOCK': 'KP_NUMLOCK',
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

        'RESET': binding('reset'),
        'BOOTL': binding('bootloader'),

        r'BT[0-5]$': lambda x: bt_macro(int(x[2:])), #type: ignore
        'BTCLR': binding('bt', 'BT_CLR'),
        'USB': binding('out', 'OUT_USB'),

        '\'"': "'",
        ',;' : shiftmorph_node(',', ';', ZMK_KEYCODES),
        '.?' : shiftmorph_node('.', '?', ZMK_KEYCODES),
        '/\\': shiftmorph_node('/', '\\', ZMK_KEYCODES),

        'XXX': binding('none'),
        '___': binding('trans'),
    }


    aliases_by_os = {os:{**aliases, **os_aliases} for os,os_aliases in os_specific_aliases.items()}
    for os,macro in (
        ('linux', utf8_linux_macro_node),
        ('mac'  , utf8_mac_macro_node),
        ('win'  , utf8_win_macro_node),
    ):
        aliases_by_os[os][r'[\u0080-\uffff]$'] = macro
    
    translator_by_os = {os:ZmkTranslator(ZMK_KEYCODES, aliases)
                        for os,aliases in aliases_by_os.items()}

    translated_layers, _ = make_os_specific_layers(layers, translator_by_os)

    layer_nodes, behavior_nodes, headers = make_zmk_layers(translated_layers)

    def find_includes():
        dt_bindings = {
            'kp': ['keys.h'],
            'bt': ['bt.h'],
            'out': ['outputs.h'],
        }
        yield '<behaviors.dtsi>'
        for node in behavior_nodes:
            for v in dt_bindings.get(node.name, []):
                yield f'<dt-bindings/zmk/{v}>'

    includes = sorted(set(find_includes()))

    return join_lines((
        join_lines(f'#include {include}' for include in includes),

        join_lines(headers),

        Node('/', [
            Node('chosen', properties={
                'zmk,matrix_transform': Raw(f'&{transform_name}')
            }),
            Node('keymap', layer_nodes, properties={
                'compatible': 'zmk,keymap',
            }),
            Node('behaviors', [node for node in behavior_nodes if node.label])
        ]).format_dt(),

        Node('&lt', properties={
            'flavor': "hold-preferred",
            'tapping-term-ms': 150,
            'quick-tap-ms': 200,
        }).format_dt(),

        Node('&hrm', properties={
            'flavor': "tap-preferred",
            'tapping-term-ms': 150,
            'quick-tap-ms': 200,
        }).format_dt(),
    ), 2) + '\n'



@dataclass(frozen=True)
class Binding:
    behavior: Node
    param1: Optional[str] = None
    param2: Optional[str] = None

    def behavior_is(self, *labels: Sequence[str]) -> bool:
        return self.behavior.name in labels
    
    def format_dt(self):
        return ' '.join(map(format_value, filter(None, (self.behavior, self.param1, self.param2))))


class Bindings(List[Binding]):
    def format_dt(self):
        values_str = ' '.join(map(format_value, self))
        return f'<{values_str}>'


class NestedBindings(List[Bindings]):
    def format_dt(self):
        return ', '.join(map(format_value, self))


def reference_nodes_in_properties(node: Node):
    referenced_nodes: Dict[str,Node] = {}

    def replace_node_by_ref(node: Union[Node,Raw]):
        if isinstance(node, Node):
            newnode = update_node_properties(node)
            referenced_nodes[repr(newnode)] = newnode
            return Raw(f'&{node.label or node.name}')
        else:
            return node

    def update_node_properties(node: Node):
        def f(prop_value:Any):
            if isinstance(prop_value, Bindings):
                return Bindings(replace(b, behavior=replace_node_by_ref(b.behavior)) for b in prop_value)
            elif isinstance(prop_value, NestedBindings):
                return NestedBindings(Bindings(replace(b, behavior=replace_node_by_ref(b.behavior)) for b in bindings) for bindings in prop_value)
            else:
                return prop_value
        
        return replace(node, 
            properties={k:f(v) for k,v in node.properties.items()},
        )

    return update_node_properties(node), list(referenced_nodes.values())



def make_zmk_layers(
    translated_layers: Iterable[TranslatedLayer['Binding']]
) -> Tuple[List[NodeOrComment], List[Node], List[str]]:

    def make_comment(layer: TranslatedLayer['Binding']) -> str:
        return layer.title + '\n' + format_layer(layer.src_table)
    
    def format_bindings(layer_node: Node, shape: Shape):
        bindings = [b.format_dt() for b in layer_node.properties['bindings']]
        formated = format_table(Table.Shape(bindings, shape), sep=' ', pad=' ', just=str.ljust)
        formated = '\n'.join(l.rstrip() for l in formated.splitlines())
        layer_node.properties['bindings'] = Raw(f'<\n{formated}\n>')

    headers = [f'#define {layer.name} {i}' for i,layer in enumerate(translated_layers) if not isinstance(layer.name, int)]
    layer_nodes: List[NodeOrComment] = []
    behavior_nodes: Dict[str, Node] = {}

    for comment,layers in groupby(translated_layers, key=make_comment):
        layer_nodes.append(Comment(comment))

        for layer in layers:
            layer_node = Node(f'{layer.name}',
                properties = {
                    'bindings': Bindings(layer.new_table.cells),
                },
            )

            new_layer_node, refs = reference_nodes_in_properties(layer_node)
            format_bindings(new_layer_node, layer.new_table.shape)
            layer_nodes.append(new_layer_node)
            
            for ref in refs:
                behavior_nodes[repr(ref)] = ref

    return layer_nodes, list(behavior_nodes.values()), headers






HRM_NODE = Node('modtap', label='hrm', properties={
    'compatible': 'zmk,behavior-hold-tap',
    'label': 'HOMEROWMOD',
    '#binding-cells': 2,
    'bindings': Raw('<&kp>, <&kp>'),
})

@cache
def binding(node_name: str, param1: Optional[str]=None, param2: Optional[str]=None):
    return Binding(Node(node_name), Raw(param1) if param1 else None, Raw(param2) if param2 else None)

@cache
def kp_binding(param1: str):
    return Binding(Node('kp'), Raw(param1))


class ZmkTranslator(Translator[Binding]):
    def __init__(self, zmk_keycodes: 'ZmkKeycodes', aliases: Any):
        super().__init__()
        self.native_keycodes = zmk_keycodes
        self._register_aliases(aliases)

    def _base_translate(self, k: SourceBinding) -> Binding:
        if not k:
            return binding('trans')
        elif isinstance(k, Binding):
            return k
        elif isinstance(k, Node):
            return Binding(k)
        elif isinstance(k, str):
            try:
                return kp_binding(self.native_keycodes[k])
            except KeyError:
                logger.warning(f'not implemented {k!r}')
                return binding('none')
        else:
            raise ValueError(f'cannot make binding for {k!r}')

    def make_modtap(self, mod: Binding, tap: Binding) -> Binding:
        if mod.behavior_is('kp') and tap.behavior_is('kp'):
            return Binding(HRM_NODE, mod.param1, tap.param1)
        else:
            raise ValueError(f'cannot make modtap for {mod}, {tap}')

    def make_layertap(self, layer: str, tap: Optional[Binding]) -> Binding:
        if tap:
            if tap.behavior_is('kp'):
                return binding('lt', layer, tap.param1)
            else:
                raise ValueError(f'cannot make layertap for {tap}')
        else:
            return binding('mo', layer)

    def make_tolayer(self, layer: str) -> Binding:
        return binding('to', layer)

    def replace_layer_ids(self, binding: Binding, f: Callable[[str], str]) -> Binding:
        if binding.behavior_is('lt','mo','to') and binding.param1 is not None:
            return replace(binding, param1=Raw(f(binding.param1)))
        else:
            return binding



def macro_node(identifier: str, *behaviors: Sequence[Binding], tap_ms: Optional[int]=None, wait_ms: Optional[int]=None, label: Optional[str]=None) -> Node:

    properties = {
        'compatible': 'zmk,behavior-macro',
        'label': label or f'macro_{identifier}',
        '#binding-cells': 0,
        'bindings': NestedBindings(Bindings(b) for b in behaviors),
        'tap-ms': tap_ms,
        'wait-ms': wait_ms,
    }

    return Node(identifier, label=identifier,
        properties = properties,
    )


def utf8_linux_macro_node(char: str) -> Node:
    hexstr = '%04x' % ord(char)
    keycodes = [d.upper() if d in 'abcdef' else f'N{d}' for d in hexstr]
    keycodes = 'LC(LS(U))', *keycodes, 'SPACE'
    return macro_node(f'u{hexstr}_L',
        [binding('macro_tap'), *map(kp_binding, keycodes)],
        label = f'Linux {char} macro',
        tap_ms=30,
        wait_ms=0,
    )

def utf8_mac_macro_node(char: str) -> Node:
    hexstr = '%04x' % ord(char)
    keycodes = [d.upper() if d in 'abcdef' else f'N{d}' for d in hexstr]
    return macro_node(f'u{hexstr}_M',
        [binding('macro_press'), kp_binding('LALT')],
        [binding('macro_tap'), *map(kp_binding, keycodes)],
        [binding('macro_release'),kp_binding('LALT')],
        label = f'Mac {char} macro',
        tap_ms=30,
        wait_ms=30,
    )

def utf8_win_macro_node(char: str) -> Node:
    hexstr = '%04x' % ord(char)
    keycodes = [d.upper() if d in 'abcdef' else f'N{d}' for d in hexstr]
    keycodes = 'RALT', 'U', *keycodes, 'RET'
    return macro_node(f'u{hexstr}_W',
        [binding('macro_tap'), *map(kp_binding, keycodes)],
        label = f'Wincompose {char} macro',
    )


def bt_macro(i: int) -> Node:
    return macro_node(f'bt{i}',
        [binding('bt', 'BT_SEL', f'{i-1}')],
        [binding('out', 'OUT_BLE')], 
        [binding('to', '(-1)')],
    )


def shiftmorph_node(default: str, shifted: str, zmk_keycodes: 'ZmkKeycodes') -> Node:
    a = zmk_keycodes[default]
    b = zmk_keycodes[shifted]

    return Node(f'{a.lower()}_{b.lower()}', label=f'{a.lower()}_{b.lower()}',
        properties={
            'compatible': 'zmk,behavior-mod-morph',
            'label': f'shift-morph {a} {b}',
            '#binding-cells': 0,
            'bindings': Raw(f'<&kp {a}>, <&kp {b}>'),
            'mods': Raw('<(MOD_LSFT|MOD_RSFT)>'),
        },
    )



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
