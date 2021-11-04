import re
from collections import defaultdict
from dataclasses import dataclass, replace
from functools import reduce
from os.path import commonprefix
from typing import (Any, Callable, Dict, Generic, Iterable, List, Optional,
                    Sequence, Set, Tuple, TypeVar, Union)

from tables import Table, cjust, format_boxed_table


SHIFTED = {k:v for k,v in r'''1! 2@ 3# 4$ 5% 6^ 7& 8* 9( 0) -_ =+ [{ ]} ;: '" ,< .> /? \| `~'''.split()}
UNSHIFTED = {v:k for k,v in SHIFTED.items()}


@dataclass
class HoldTap:
    tap: str
    hold: str

    def __str__(self):
        return f'{self.tap} ⇩{self.hold}'

    def replace(self, **kwargs: Dict[Any,Any]):
        return replace(self, **kwargs)


class ModTap(HoldTap): pass


class LayerTap(HoldTap):
    @property
    def layer(self):
        return self.hold


@dataclass
class ToLayer:
    layer: str


IntermediateBinding = Union[HoldTap, ToLayer, str]
T = TypeVar('T')
T2 = TypeVar('T2')
T3 = TypeVar('T3')


@dataclass
class Layer(Generic[T]):
    table: Table[T]
    name: str
    title: str

    def map_table(self, f:Callable[[T],T2]) -> 'Layer[T2]':
        return Layer(self.table.map(f), name=self.name, title=self.title)

    def map_table2(self, f:Callable[[T,T2],T3], other:'Layer[T2]') -> 'Layer[T3]':
        return Layer(self.table.map2(f, other.table), name=self.name, title=self.title)
       


def layers_from_tables(layer_tables: Iterable[Tuple[str, Table[str]]]) -> List[Layer[IntermediateBinding]]:

    def parse_layers() -> Iterable[Tuple[Table[str], str, str, Set[Tuple[str,...]]]]:
        for i,(title,table) in enumerate(layer_tables):
            paths: Set[Tuple[str,...]] = set()
            name = None
            for code in re.findall(r'`([^`]+)`', title):
                if m:= re.match(r'([\w+]+)(?:([>,])|([+&]))([\w+]+)', code):
                    a,_,f2,b = m.groups()
                    paths.add((a,b))
                    if f2:
                        paths.add((b,a))
                else:
                    paths.add((code,))

            if paths:
                minpath = min(paths, key=len)
                if len(minpath) < 2:
                    name = minpath[0]

            if not name:
                name = str(i)

            title = re.sub(r' +\(`\w+`\)',r'', title)
            yield table, name, title, paths


    src_layers_by_id = {layer[1]:layer for layer in parse_layers()}

    base_table, base_name, base_title, _   = src_layers_by_id.pop('base')
    taphold_table, _, _, _ = src_layers_by_id.pop('hold-tap')


    def make_taphold(tap:str, hold:str) -> IntermediateBinding:
        if hold:
            if hold in src_layers_by_id:
                return LayerTap(tap, hold)
            else:
                return ModTap(tap, hold)
        else:
            return tap

    layers_by_id: Dict[str,Layer[IntermediateBinding]] = dict(
        base = Layer(base_table.map2(make_taphold, taphold_table), base_name, base_title),
        **{name:Layer(table, name, title) for table,name,title,_ in src_layers_by_id.values()}
    )

    for _,name,_,paths in src_layers_by_id.values():
        for path in paths:
            for a,b in zip(path, path[1:]):
                for i,j in taphold_table.indices(b):
                    c = layers_by_id[a].table.rows[i][j]
                    if isinstance(c, str):
                        layers_by_id[a].table.rows[i][j] = LayerTap(c, name)
    
    nonvoid = Table([
        [any(cells) for cells in zip(*rows)] 
        for rows in zip(*(l.table.rows for l in layers_by_id.values()))
    ])
    
    def f(c:IntermediateBinding, b:bool):
        return None if not b else c if c else 'XXX'
    layers = [replace(l, table=l.table.map2(f, nonvoid)) for l in layers_by_id.values()]

    return layers





def extract_tables_from_md(f: Iterable[str], layout_section_re: str=r'layout definition'):
    def md_header_depth(line: str):
        line = line.strip()
        return len(line) - len(line.lstrip('#'))

    def md_find_section(predicate: Callable[[str],bool]):
        lines = iter(f)
        depth = 0
        for line in lines:
            if predicate(line):
                depth = md_header_depth(line)
                break

        for line in lines:
            d = md_header_depth(line)
            if d and d <= depth:
                break
            else:
                yield line

    def match_head(line: str):
        return re.match(r'^[#]+ +(.+)', line)

    def match_table(line: str):
        return re.match(r'^([|].*)+', line)

    subsection = ''
    in_table = False
    table_lines: List[str] = []

    def pred(s:str):
        return bool(re.search(layout_section_re, s, flags=re.I))
    
    for line in md_find_section(pred):
        if m:= match_head(line):
            subsection = m.group(1).rstrip()
        elif match_table(line):
            in_table = True
            table_lines.append(line.strip('\t\r\n'))
        else:
            if in_table:
                yield str(subsection), Table.Parse(table_lines)
                table_lines = []
            in_table = False



def format_layer(table:Table[Any], blank:str='XXX'):
    def f(s:Any):
        return cjust('' if s == blank else str(s), 5)
    return format_boxed_table(table.map(f))




MODIFIERS_RE = re.compile(r'([rl]?(ALT|CMD|CTRL|SHIFT))\+', flags=re.I)

def split_combo(kc:str) -> Tuple[List[str], str]:
    mods: List[str] = []
    i = 0
    while m := MODIFIERS_RE.match(kc,i):
        mods.append(m.group(1))
        i = m.end()

    return mods, kc[i:]



def split_common_prefix(names: Sequence[str]) -> Tuple[str, List[str]]:
    prefix = commonprefix(names)
    return prefix, [name[len(prefix):] for name in names]




def extract_layers_from_md(f: Iterable[str], make_3x5: bool=False):
    layers = layers_from_tables(extract_tables_from_md(f))
    if make_3x5:
        def g(table:Table[IntermediateBinding]):
            return type(table)([row[:5]+[None]+row[-5:] for row in table.rows])
        return [replace(layer, table=g(layer.table)) for layer in layers]
    else:
        return layers



def extract_os_specifics_from_md(f: Iterable[str]):
    for _,table in extract_tables_from_md(f, layout_section_re=r'OS specific'):
        for c in range(1,table.col_count):
            name = table.rows[0][c]
            if isinstance(name, str):
                aliases: Dict[str,str] = {}
                for r in range(1, table.row_count):
                    k = table.rows[r][0]
                    v = table.rows[r][c]
                    if isinstance(k, str) and isinstance(v, str) and v.strip(' -'):
                        aliases[k] = v
                yield name, aliases



B = TypeVar('B')

@dataclass(frozen=True)
class TranslatedLayer(Generic[B]):
    name : str
    new_table : Table[B]
    src_table : Table[IntermediateBinding]
    title : str



class Translator(Generic[B]):
    def __init__(self):
        self.aliases: Dict[str, str] = dict()
        self.aliases_callables: Dict[str, Callable[[str], Union[str,IntermediateBinding,B]]] = dict()

    def _register_aliases(self, aliases: Dict[str,Any]):
        for k,v in aliases.items():
            if callable(v):
                self.aliases_callables[k] = v
            else:
                self.aliases[k] = v


    def _alias_lookup(self, y: str) -> Union[str, IntermediateBinding, B]:
        def lookup1(x: str) -> Union[str, IntermediateBinding, B]:
            if x in self.aliases:
                return self.aliases[x]

            for k,v in self.aliases_callables.items():
                if re.match(k, x):
                    y = v(x)
                    if not y is None:
                        return y

            raise KeyError(x)

        seen: Set[str] = set()
        x = y
        try:
            while isinstance(x, str) and not x in seen:
                seen.add(x)
                x = lookup1(x)
        except KeyError:
            pass
        return x

    def _base_translate(self, k: IntermediateBinding) -> B:
        raise NotImplementedError()

    def replace_layer_ids(self, binding: B, f: Callable[[str], str]) -> B:
        raise NotImplementedError()

    def make_layertap(self, layer: str, tap: Optional[B]) -> B:
        raise NotImplementedError()

    def make_modtap(self, mod: B, tap: B) -> B:
        raise NotImplementedError()

    def make_tolayer(self, layer: str) -> B:
        raise NotImplementedError()


    def translate(self, x:IntermediateBinding) -> B:
        k: Union[str, IntermediateBinding, B] = x
        if isinstance(k, str):
            k = self._alias_lookup(k)

        if isinstance(k, LayerTap):
            if k.tap:
                tap = self.translate(k.tap)
                return self.make_layertap(k.hold, tap)
            else:
                return self.make_layertap(k.hold, None)

        elif isinstance(k, ModTap):
            mod = self.translate(k.hold)
            tap = self.translate(k.tap)
            return self.make_modtap(mod, tap)

        elif isinstance(k, ToLayer):
            return self.make_tolayer(k.layer)

        else:
            return self._base_translate(k) #type: ignore


    def translate_layer(self, layer:Layer[IntermediateBinding]) -> TranslatedLayer[B]:
        new_table: Table[B] = layer.table.map(self.translate)
        translated: TranslatedLayer[B] = TranslatedLayer(
            name = layer.name,
            new_table = new_table,
            src_table = layer.table,
            title = layer.title,
        )
        return translated


    def map_layer_names(self,
        layer: TranslatedLayer[B],
        f: Callable[[str], str],
        exclude: Optional[Sequence[str]]=None
    ) -> TranslatedLayer[B]:
        exclude2: Set[str] = set(exclude) if exclude else set()
        def g(name: str):
            return name if name in exclude2 else f(name)

        new_layer = replace(layer,
            name = g(layer.name),
            new_table = layer.new_table.map(lambda c: self.replace_layer_ids(c, g)),
        )
        return new_layer
    



    def optimize_translated_layers(self,
        layers: List[TranslatedLayer[B]],
        dont_merge: Optional[Sequence[str]]=None
    ) -> List[TranslatedLayer[B]]:
        layers_by_id = {layer.name:(i,layer) for i,layer in enumerate(layers)}


        def combine_names(names: Sequence[str]) -> str:
            prefix, suffixes = split_common_prefix(names)
            return prefix + ''.join(suffixes)


        while True:
            new_ids: Dict[str,str] = {}

            duplicates: Dict[Tuple[str,...], List[Tuple[int,str]]]  = defaultdict(list)
            for layer_id,(i,layer) in layers_by_id.items():
                hashable = tuple(map(str,layer.new_table.cells()))
                duplicates[hashable].append((i,layer_id))
            duplicates2 = [xs for xs in duplicates.values() if len(xs)>1]

            for indexed_names in duplicates2:
                names = [name for _,name in indexed_names]
                if not dont_merge or not any(name in dont_merge for name in names):
                    new_name = combine_names(names)

                    layers_by_id[new_name] = layers_by_id[names[0]]
                    for name in names:
                        new_ids[name] = new_name
                        del layers_by_id[name]

            if new_ids:
                for name,(i,layer) in layers_by_id.items():
                    layers_by_id[name] = i, self.map_layer_names(layer, lambda l:new_ids.get(l,l))
            else:
                break

        return [layer for _,layer in sorted(layers_by_id.values())]

        


Q = TypeVar('Q')
def make_os_specific_layers(
    layers: Sequence[Layer[IntermediateBinding]],
    aliases_by_os: Dict[str, Dict[str, str]],
    translator_factory: Callable[[Dict[str,Any]], Translator[Q]],
    optimize: bool = True,
    shorten_names: bool = True,
) -> Tuple[
    List[TranslatedLayer[Q]],
    Dict[str, str]
]:
    base = layers[0].name.upper()
    os_layers_codes = {
        f'@{os}'.upper(): ToLayer(f'{base}_{os}') for os in aliases_by_os.keys()
    }
    translators = {os:translator_factory({**aliases, **os_layers_codes})
                   for os,aliases in aliases_by_os.items()}
    translator = next(iter(translators.values()))

    bases_by_os = {os:f'{base}_{os}' for os in aliases_by_os.keys()}
    base_ids = list(bases_by_os.values())

    translated_layers: List[TranslatedLayer[Q]] = []
    for layer in layers:
        for os,translator in translators.items():
            translated_layer = translator.translate_layer(layer)
            def f(l: str):
                return f'{l.upper()}_{os}'
            translated_layers.append(translator.map_layer_names(translated_layer, f, exclude=base_ids))


    if optimize:
        translated_layers = translator.optimize_translated_layers(translated_layers, dont_merge=base_ids)


    if shorten_names:
        replacements = [
            ('_'+''.join(aliases_by_os.keys()), ''),
            *[(os, os[:1]) for os in aliases_by_os.keys()],
        ]
        def shorten_layer_name(s: str):
            return reduce(lambda a, kv: a.replace(*kv), replacements, s)
        
        translated_layers = [translator.map_layer_names(layer, shorten_layer_name) for layer in translated_layers]
        bases_by_os = {os:shorten_layer_name(base) for os,base in bases_by_os.items()}


    return translated_layers, bases_by_os

