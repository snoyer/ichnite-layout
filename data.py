from functools import partial
from itertools import chain
import re




def layers_from_tables(layer_tables):
    layers_by_id = {k:list(chain(*v)) for k,v in layer_tables}

    def make_shifted(default,shift):
        return dict(default=default, shift=shift) if shift else default

    def make_taphold(tap, hold):
        if hold:
            if isinstance(tap, dict):
                return dict(**tap, hold=hold)
            else:
                return dict(default=tap, hold=hold)
        return tap

    taphold_layer = layers_by_id.pop('tap-hold')
    base_layer    = layers_by_id.pop('base')
    shift_layer   = layers_by_id.pop('shifts')

    shiftedbase_layer = list(map(make_shifted, base_layer, shift_layer))

    layers = dict(
        base = list(map(make_taphold, shiftedbase_layer, taphold_layer)),
        **layers_by_id
    )

    for layer_id,layer in layers.items():
        m = re.match(r'([\w+]+)([+&>,])([\w+]+)', layer_id)
        if m:
            a,f,b = m.groups()
            try:
                ai = taphold_layer.index(a)
                bi = taphold_layer.index(b)
                layers[a][bi] = make_taphold(layers[a][bi], layer_id)
                if f in '+&':
                    layers[b][ai] = make_taphold(layers[b][ai], layer_id)
            except ValueError:
                pass

    return layers



def extract_tables_from_md(f):
    def md_header_depth(line):
        line = line.strip()
        return len(line) - len(line.lstrip('#'))

    def md_find_section(predicate):
        lines = iter(f)
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

    def match_head(line):
        return re.match(r'[#]+ +(.+)`(.+)`', line)

    def match_table(line):
        return re.match(r'[ \t]+([|].*)+', line)

    section = None
    table = []
    for line in md_find_section(partial(re.search, r'layout definition', flags=re.I)):
        m = match_head(line)
        if m:
            if table:
                yield section, list(table)
                table = []
            section = m.group(2)
        elif match_table(line):
            table.append([s.strip() for s in re.split(r'[|]+', line.strip().strip('|'))])
    if table:
        yield section, list(table)



if __name__ == '__main__':
    layers = layers_from_tables(extract_tables_from_md(open('readme.md')))
    for k,vs in layers.items():
        print(k, vs)
