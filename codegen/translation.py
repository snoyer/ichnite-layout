



import re
from collections import defaultdict
from dataclasses import dataclass, replace
from functools import reduce
from typing import (Any, Callable, Dict, Generic, Iterable, List, Mapping, Optional,
                    Sequence, Set, Tuple, TypeVar, Union)

from source import (SourceBinding, Layer, LayerTap, ModTap, ToLayer,
                    split_common_prefix)
from tables import Table

T = TypeVar('T')


@dataclass(frozen=True)
class TranslatedLayer(Generic[T]):
    name : str
    new_table : Table[T]
    src_table : Table[SourceBinding]
    title : str


class Translator(Generic[T]):
    def __init__(self):
        self.aliases: Dict[str, str] = dict()
        self.aliases_callables: Dict[str, Callable[[str], Union[str,SourceBinding,T]]] = dict()

    def _register_aliases(self, aliases: Dict[str,Any]):
        for k,v in aliases.items():
            if callable(v):
                self.aliases_callables[k] = v
            else:
                self.aliases[k] = v


    def _alias_lookup(self, y: str) -> Union[str, SourceBinding, T]:
        def lookup1(x: str) -> Union[str, SourceBinding, T]:
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

    def _base_translate(self, k: SourceBinding) -> T:
        raise NotImplementedError()

    def replace_layer_ids(self, binding: T, f: Callable[[str], str]) -> T:
        raise NotImplementedError()

    def make_layertap(self, layer: str, tap: Optional[T]) -> T:
        raise NotImplementedError()

    def make_modtap(self, mod: T, tap: T) -> T:
        raise NotImplementedError()

    def make_tolayer(self, layer: str) -> T:
        raise NotImplementedError()


    def translate(self, x:SourceBinding) -> T:
        k: Union[str, SourceBinding, T] = x
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


    def translate_layer(self, layer:Layer[SourceBinding]):
        new_table = layer.table.copy(map(self.translate, layer.table.cells))
        return TranslatedLayer(
            name = layer.name,
            new_table = new_table,
            src_table = layer.table,
            title = layer.title,
        )


    def map_layer_names(self,
        layer: TranslatedLayer[T],
        f: Callable[[str], str],
        exclude: Optional[Sequence[str]]=None
    ) -> TranslatedLayer[T]:
        exclude2: Set[str] = set(exclude) if exclude else set()
        def g(name: str):
            return name if name in exclude2 else f(name)

        new_layer = replace(layer,
            name = g(layer.name),
            new_table = layer.new_table.copy(map(lambda c: self.replace_layer_ids(c, g), layer.new_table.cells)),
        )
        return new_layer




Q = TypeVar('Q')
def make_os_specific_layers(
    layers: Sequence[Layer[SourceBinding]],
    translators_by_os: Mapping[str, Translator[Q]],
    optimize: bool = True,
    shorten_names: bool = True,
) -> Tuple[
    List[TranslatedLayer[Q]],
    Dict[str, str]
]:
    translators_by_os = dict(translators_by_os)
    os_ids = translators_by_os.keys()

    def f(l: str, os: str):
        return f'{l.upper()}_{os}'
    
    base = layers[0].name
    os_layers_codes = {
        f'@{os}': ToLayer(f(base,os)) for os in os_ids
    }

    bases_by_os = {os:f(base,os) for os in os_ids}
    base_ids = list(bases_by_os.values())

    def translate_layers():
        def fix_os_bindings(k: SourceBinding):
            return os_layers_codes.get(k, k) if isinstance(k, str) else k
        
        for layer in layers:
            layer2 = layer.map_table(fix_os_bindings)
            for os, translator in translators_by_os.items():
                translated_layer = translator.translate_layer(layer2)
                translated_layer = replace(translated_layer,
                                           src_table=layer.table)
                yield translator.map_layer_names(translated_layer, lambda l: f(l, os), exclude=base_ids), translator
    translated_layers = list(translate_layers())

    if optimize:
        translated_layers = optimize_translated_layers(translated_layers, dont_merge=base_ids)

    if shorten_names:
        replacements = [
            ('_' + ''.join(os_ids), ''),
            *[(os, os[:1]) for os in os_ids],
        ]
        def shorten_layer_name(s: str):
            return reduce(lambda a, kv: a.replace(*kv), replacements, s)

        translated_layers = [(translator.map_layer_names(layer, shorten_layer_name), translator)
                             for layer, translator in translated_layers]
        bases_by_os = {os:shorten_layer_name(base) for os,base in bases_by_os.items()}


    return [layer for layer,_ in translated_layers], bases_by_os


TranslatedAndTranslator = Tuple[TranslatedLayer[T], Translator[T]]


def optimize_translated_layers(
    layers: Iterable[TranslatedAndTranslator[T]],
    dont_merge: Optional[Sequence[str]] = None
) -> List[TranslatedAndTranslator[T]]:
    layers_by_id = {layer.name: (i, layer, translator)
                    for i, (layer, translator) in enumerate(layers)}

    def combine_names(names: Sequence[str]) -> str:
        prefix, suffixes = split_common_prefix(names)
        return prefix + ''.join(suffixes)

    while True:
        new_ids: Dict[str, str] = {}

        duplicates: Dict[Tuple[str, ...],
                         List[Tuple[int, str, Translator[T]]]] = defaultdict(list)
        for layer_id, (i, layer, translator) in layers_by_id.items():
            hashable = tuple(map(str, layer.new_table.cells))
            duplicates[hashable].append((i, layer_id, translator))
        duplicates2 = [xs for xs in duplicates.values() if len(xs) > 1]

        for indexed_names in duplicates2:
            names = [name for _, name, _ in indexed_names]
            if not dont_merge or not any(name in dont_merge for name in names):
                new_name = combine_names(names)

                layers_by_id[new_name] = layers_by_id[names[0]]
                for name in names:
                    new_ids[name] = new_name
                    del layers_by_id[name]

        if new_ids:
            for name, (i, layer, translator) in layers_by_id.items():
                newlayer = translator.map_layer_names(layer,
                                                      lambda l: new_ids.get(l, l))
                layers_by_id[name] = i, newlayer, translator
        else:
            break

    return [(layer, translator) for _, layer, translator in sorted(layers_by_id.values())]
