import re
from dataclasses import dataclass
from typing import (Any, Callable, Dict, Generic, Iterable, Iterator, List,
                    Sequence, Tuple, TypeVar, Union)


class Span:
    def __repr__(self):
        return 'Span'

    def __bool__(self):
        return False

@dataclass(frozen=True)
class Index:
    row: int 
    col: int 
    colspan: int = 1
    rowspan: int = 1 


T = TypeVar('T')
T2 = TypeVar('T2')
T3 = TypeVar('T3')


class Table(Generic[T]):
    def __init__(self, rows: List[List[Union[T,None,Span]]]):
        self.rows = rows
    

    def map(self, f: Callable[[T], T2]) -> 'Table[T2]':
        def g(c: Union[T, None ,Span]) -> Union[T2, None,Span]:
            return f(c) if not (c is None or isinstance(c, Span)) else c
        new_rows = [[g(cell) for cell in row]  for row in self.rows]
        return Table(new_rows)


    def map2(self, f: Callable[[T,T2], T3], other: 'Table[T2]') -> 'Table[T3]':
        def g(c1: Union[T, None, Span], c2: Union[T2, None, Span]) -> Union[T3, None, Span]:
            return f(c1,c2) if not (c1 is None or isinstance(c1, Span)) else c1
        new_rows = [[g(c1,c2) for c1,c2 in zip(r1,r2)]  for r1,r2 in zip(self.rows, other.rows)]
        return Table(new_rows)


    @property
    def row_count(self):
        return len(self.rows)

    @property
    def col_count(self):
        return len(self.rows[0])
    
    
    def indices(self, predicate_or_value: Union[T, Callable[[T],bool]]) -> Iterable[Tuple[int,int]]:
        def predicate(c:T):
            if callable(predicate_or_value):
                return predicate_or_value(c)
            else:
                return predicate_or_value == c
        
        for i,row in enumerate(self.rows):
            for j,cell in enumerate(row):
                if not isinstance(cell,Span) and cell != None and predicate(cell):
                    yield i,j

    
    def cells(self) -> Iterator[T]:
        for _,cell in self.indexed_cells():
            yield cell
    

    def indexed_cells(self) -> Iterator[Tuple[Index, T]]:
        for i,row in enumerate(self.rows):
            for j,cell in enumerate(row):
                if not isinstance(cell, Span) and not cell is None:
                    colspan = table_cell_colspan(row,j)
                    yield Index(i,j,1,colspan), cell


    def __str__(self) -> str:
        return format_table(self)

    @classmethod
    def Parse(cls, lines: Union[str, Sequence[str]], separator: str='|', strip: bool=True) -> 'Table[str]':
        if isinstance(lines, str):
            lines = lines.splitlines()
        
        lines = [line.rstrip('\n\r') for line in lines]

        limits = sorted(set(i for line in lines for i,c in enumerate(line) if c==separator))

        def parse_cells(line: str) -> Iterator[Union[str, None, Span]]:
            i = 0
            while i < len(limits)-1:
                j = i+1
                while limits[j]<len(line)-1 and line[limits[j]] != separator:
                    j += 1
                span = j-i
                cell = line[limits[i]+1:limits[j]]
                c = cell.strip() if strip else cell
                yield c
                for _ in range(span-1):
                    yield Span()
                i = j

        x = list(list(parse_cells(line)) for line in lines)
        return Table(x)



def cjust(s: str, w:int) -> str:
    l = len(s)
    h = (w-l) // 2
    return ' '*h + s + ' '*(w-l-h)




def format_table(table:Table[Any], sep: str='|', pad: str=' ', just: Callable[[str,int], str] = cjust) -> str:
    lines = ['' for _ in table.rows]
    for i,j,txt,w in _render(table, sep_width=len(sep), pad_width=len(pad)):
        lines[i] = _edit_str(lines[i], j, sep + just(txt, w) + sep)

    return '\n'.join(lines)



def format_boxed_table(table: Table[Any], pad: str=' ', just: Callable[[str,int],str]=cjust, header: bool=False) -> str:
    bars: Dict[Tuple[int,int], int] = {}
    cells: Dict[Tuple[int,int], str] = {}

    bar1 = 1
    bar2 = 3
    for y,x0,txt,w in _render(table, sep_width=1, pad_width=len(pad)):
        y = 2*y + 1
        x1 = x0 + w
        cells[x0+1,y] = pad + just(txt, w-len(pad)*2) + pad
        bars[x0, y] = bar1
        bars[x1+1, y] = bar1
        for x in range(x0, x1+2):
            bars[x, y-1] = bar2 if header and y-1==2 else bar1
            bars[x, y+1] = bar2 if header and y+1==2 else bar1

    w = max(x for x,_ in bars) + 1
    h = max(y for _,y in bars) + 1
    final = [[' ']*w for _ in range(h)]

    for x,y in bars:
        if 0<=x<w and 0<=y<h:
            final[y][x] = _find_border((
                bars.get((x,y-1), 0),
                bars.get((x+1,y), 0),
                bars.get((x,y+1), 0),
                bars.get((x-1,y), 0),
            ))

    for (x,y),txt in cells.items():
        final[y][x:x+len(txt)] = txt

    return '\n'.join(''.join(line) for line in final)


def _find_border(nesw: Tuple[int,int,int,int]) -> str:
    k = ''.join(map(str,nesw))
    b = BORDERS.get(k)
    if b:
        return b
    else:
        for k2,v in BORDERS.items():
            if re.match(k2,k):
                return v
    return '+'



def _colspans_width(table:Table[Any], sep_width: int=1, pad_width: int=1):

    total_pad = pad_width*2 + sep_width
   
    ncol = table.row_count

    widths = {(i,i+1): 1 for i in range(ncol)}

    for i,row in enumerate(table.rows):
        for j,cell in enumerate(row):
            if not isinstance(cell, Span):
               k = j + table_cell_colspan(table.rows[i], j)
               w = len(str(cell)) if cell else 0
               widths[j,k] = max(w + total_pad, widths.get((j,k),0))

    return widths


def _limits_from_colspan_widths(colspan_widths: Dict[Tuple[int,int],int]) -> List[int]:
    ncol = max(b for _,b in colspan_widths)

    limits = [0] * (ncol+1)
    for (a,b),l in sorted(colspan_widths.items()):
        limits[b] = max(limits[b], limits[a] + l)

    return limits



def _render(table:Table[Any], sep_width: int=1, pad_width: int=1) -> Iterator[Tuple[int,int,str,int]]:

    widths = _colspans_width(table, sep_width=sep_width, pad_width=pad_width)
    #TODO relax/balance loose columns
    limits = _limits_from_colspan_widths(widths)

    for i,row in enumerate(table.rows):
        for j,cell in enumerate(row):
            if not isinstance(cell, Span) and not cell == None:
               k = j + table_cell_colspan(table.rows[i], j)
               w = limits[k] - limits[j] - 1
               yield i, limits[j], str(cell), w



def table_cell_colspan(row:Sequence[Any], i:int) -> int:
    j = i + 1
    n = len(row)
    while j < n and isinstance(row[j], Span):
        j += 1
    return j - i


def _edit_str(s:str, i:int, v:str) -> str:
    if len(s) < i:
        return s + ' '*(i-len(s)) + v
    else:
        return s[:i] + v + s[i+len(v):]




BORDERS_PATTERNS = '''
─0.0. ━0202 ═0303
│.0.0 ┃2020 ║3030
┐0011 ┑0012 ┒0021 ┓0022 ╕0013 ╖0031 ╗0033
└1100 ┕1200 ┖2100 ┗2200 ╘1300 ╙3100 ╚3300
┌0110 ┍0210 ┎0120 ┏0220 ╒0310 ╓0130 ╔0330
┘1001 ┙1002 ┚2001 ┛2002 ╛1003 ╜3001 ╝3003
┬0111 ┭0112 ┮0211 ┯0212 ┰0121 ┱0122 ┲0221 ┳0222 ╤0313 ╥0131 ╦0333
├1110 ┝1210 ┞2110 ┟1120 ┠2120 ┡2210 ┢1220 ┣2220 ╞1310 ╟3130 ╠3330
┤1011 ┥1012 ┦2011 ┧1021 ┨2021 ┩2012 ┪1022 ┫2022 ╡1013 ╢3031 ╣3033
┴1101 ┵1102 ┶1201 ┷1202 ┸2101 ┹2102 ┺2201 ┻2202 ╧1303 ╨3101 ╩3303
┼1111 ┽1112 ┾1211 ┿1212 ╀2111 ╁1121 ╂2121 ╃2112 ╄2211 ╅1122 
╆1221 ╇2212 ╈1222 ╉2122 ╊2221 ╋2222 ╪1313 ╫3131 ╬3333
'''.strip()

BORDERS = dict(sorted(
    ((token[1:], token[0]) for line in BORDERS_PATTERNS.splitlines()
                           for token in line.split()),
    key=lambda kv:len([c for c in kv[0] if c=='.'])
))


