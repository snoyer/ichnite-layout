import re
from collections import defaultdict
from typing import Callable, Generic, Sequence, TypeVar

from .source import Key, split_common_prefix

T = TypeVar('T')

ValueOrCallable = T | Callable[[re.Match[str]], T]


class Translator(Generic[T]):
    def __init__(self):
        self.exact_aliases: dict[str, str] = {}
        self.match_aliases: list[tuple[str, Callable[[re.Match[str]], str]]] = []
        
        self.exact_translations: dict[str, T] = {}
        self.match_translations: list[tuple[str, Callable[[re.Match[str]], T]]] = []

    def register_aliases(self, aliases: dict[str, str | Callable[[re.Match[str]], str]]):
        for k,v in aliases.items():
            if callable(v):
                self.match_aliases.append((k, v))
            else:
                self.exact_aliases[k] = v

    def register_translations(self, translations: dict[str, T | Callable[[re.Match[str]], T]]):
        for k,v in translations.items():
            if callable(v):
                self.match_translations.append((k, v))
            else:
                self.exact_translations[k] = v

    def _translation_lookup(self, x: str) -> T:
        try:
            return self.exact_translations[x]
        except KeyError:
            for pattern,func in self.match_translations:
                if m := re.match(pattern, x):
                    return func(m)
        raise KeyError(x)

    def _alias_lookup(self, y: str) -> str:
        def lookup1(x: str):
            try:
                return self.exact_aliases[x]
            except KeyError:
                for pattern,func in self.match_aliases:
                    if m := re.match(pattern, x):
                        return func(m)
            raise KeyError(x)

        seen: set[str] = set()
        x = y
        try:
            while x not in seen:
                seen.add(x)
                x = lookup1(x)
        except KeyError:
            pass
        return x

    def translate_all(self, keys: Sequence[Key], is_layer_name: Callable[[str], bool]) -> list[T]:
        return [self.translate(key, is_layer_name=is_layer_name) for key in keys]
        
    def translate(self, key: Key, is_layer_name: Callable[[str], bool]) -> T:
        raise NotImplementedError()
    
    @classmethod
    def map_layer_names(cls, f: Callable[[str], str], binding: T) -> T:
        raise NotImplementedError()



def translate_multi_os_layers(
    layers: dict[str, list[Key]],
    translator_for_os: Callable[[str], Translator[T]],
    os_from_layer_name: Callable[[str], str]
) -> dict[str, list[T]]:
    layer_to_os = {layer:os_from_layer_name(layer) for layer in layers}
    translator_by_os = {os: translator_for_os(os) for os in set(layer_to_os.values())}
    return {name: translator_by_os[layer_to_os[name]].translate_all(keys, is_layer_name=layers.__contains__)
            for name,keys in layers.items()}


def shorten_layers_names(
    layers: dict[str, list[T]],
    update_layer_names:Callable[[Callable[[str], str], T], T],
    shorten_layer_name: Callable[[str], str]
):
    return {shorten_layer_name(k):[update_layer_names(shorten_layer_name, b) for b in bindings] for k,bindings in layers.items()}


def dedup_keymaps_layers(
    layers: dict[str, list[T]],
    update_layer_names:Callable[[Callable[[str], str], T], T],
    ignore: Callable[[str], bool] | None = None,
):

    def combine_names(names: Sequence[str]) -> str:
        prefix, suffixes = split_common_prefix(names)
        return prefix + ','.join(sorted(suffixes))

    tmp_bindings: dict[tuple[int, str], list[T]] = {(i,name):bindings for i,(name,bindings) in enumerate(layers.items())}

    while True:
        new_ids: dict[str, str] = {}

        grouped: dict[tuple[str, ...], list[tuple[int,str]]] = defaultdict(list)
        for (i,name),bindings in tmp_bindings.items():
            if not callable(ignore) or not ignore(name):
                hashable = tuple(map(repr, bindings))
            else:
                hashable = tuple(str(id(bindings)),)
            grouped[hashable].append((i,name))
        duplicates = [xs for xs in grouped.values() if len(xs) > 1]
        
        for indexed_names in duplicates:
            new_name = combine_names([name for _i,name in indexed_names])
            tmp_bindings[(indexed_names[0][0], new_name)] = tmp_bindings[indexed_names[0]]
            for name in indexed_names:
                new_ids[name[1]] = new_name
                del tmp_bindings[name]

        if new_ids:
            tmp_bindings = {k:[update_layer_names(lambda l: new_ids.get(l, l), b) for b in bindings] for k,bindings in tmp_bindings.items()}
        else:
            break
    
    return {name:bindings for (_i,name),bindings in sorted(tmp_bindings.items())}
