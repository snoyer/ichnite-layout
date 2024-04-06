import re
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Set,
    TypeVar,
    cast,
    overload,
)

BORDERS = {
    "1111": "┼",
    "0111": "┬",
    "1110": "├",
    "1011": "┤",
    "1101": "┴",
    "0011": "┐",
    "1100": "└",
    "0110": "┌",
    "1001": "┘",
    "0.0.": "─",
    ".0.0": "│",
}

BORDER_CHARACTERS = "".join(BORDERS.values())

T = TypeVar("T")
T2 = TypeVar("T2")
T3 = TypeVar("T3")

TableShape = dict[tuple[int, int], tuple[int, int]]


class Table(Generic[T]):
    def __init__(self, contents: dict[tuple[int, int], T], shape: TableShape) -> None:
        if shape.keys() != contents.keys():
            raise ValueError("shape and contents do not match")

        self._contents = contents
        self._spans = shape

    @property
    def row_count(self):
        return max(r + rspan for (r, _c), (rspan, _cspan) in self._spans.items())

    @property
    def col_count(self):
        return max(c + cspan for (_r, c), (_rspan, cspan) in self._spans.items())

    def __getitem__(self, index: tuple[int, int]):
        return self._contents.__getitem__(index)

    @overload
    def get(self, index: tuple[int, int], default: T2) -> T | T2: ...

    @overload
    def get(self, index: tuple[int, int]) -> Optional[T]: ...

    def get(
        self, index: tuple[int, int], default: Optional[T2] = None
    ) -> T | T2 | None:
        return self._contents.get(index, default)

    @property
    def shape(self):
        return self._spans

    @property
    def values(self):
        return list(self._contents.values())

    @property
    def indexed_cells(self):
        return dict(self._contents)

    def map_contents(self, f: Callable[[T], T2]) -> "Table[T2]":
        return Table({k: f(v) for k, v in self._contents.items()}, dict(self._spans))

    def remove_cells(self, predicate: Optional[Callable[[T], bool]]):
        if not callable(predicate):
            predicate = is_none

        empties = set(k for k, v in self._contents.items() if predicate(v))
        return Table(
            {k: v for k, v in self._contents.items() if k not in empties},
            {k: v for k, v in self._spans.items() if k not in empties},
        )

    def reshape(
        self, src: "Table[T2]", dst: "Table[T2]", default: T3
    ) -> "Table[T | T3]":
        lbl_to_index = {v: k for k, v in src.indexed_cells.items()}

        def new_values():
            for k, v in dst.indexed_cells.items():
                if v in lbl_to_index:
                    yield k, self.get(lbl_to_index[v], default)

        return Table.Shape(dst.shape, dict(new_values()), default)

    @classmethod
    def Shape(
        cls,
        shape: TableShape,
        values: Mapping[tuple[int, int], T2] | Iterable[T2],
        default: T3,
    ) -> "Table[T2 | T3]":
        if isinstance(values, Mapping):
            values = cast(Mapping[tuple[int, int], T2], values)
            return Table({k: values.get(k, default) for k in shape}, shape)
        else:
            return Table(dict(zip(shape, values)), shape)

    @classmethod
    def Parse(
        cls,
        lines: str | Iterable[str],
        col_separators: str = "|" + BORDER_CHARACTERS,
        row_separators: str = "+-" + BORDER_CHARACTERS,
        strip: bool = True,
    ) -> "Table[str]":
        if isinstance(lines, str):
            lines = lines.splitlines()
        lines = list(filter(None, (line.rstrip("\n\r ") for line in lines)))

        r_seps: Set[tuple[int, int]] = set()
        c_seps: Set[tuple[int, int]] = set()

        for y, line in enumerate(lines):
            if all(c in row_separators or c == " " for c in line):
                r_seps |= set((y, x) for x, c in enumerate(line) if c in row_separators)
            else:
                c_seps |= set((y, x) for x, c in enumerate(line) if c in col_separators)
        all_seps = r_seps | c_seps

        w = max(x for _, x in all_seps)
        h = max(y for y, _ in all_seps)
        y2r: dict[int, int] = {}
        x2c = {x: c for c, x in enumerate(sorted(set(x for _, x in c_seps)))}

        rects: dict[tuple[int, int, int, int], list[str]] = {}

        q = sorted(c_seps)
        while q:
            y0, x0 = q.pop(0)
            if x0 >= w or any(_rect_contains(r, (y0, x0)) for r in rects):
                continue

            x1 = x0 + 1
            while x1 <= w and (y0, x1) not in all_seps:
                x1 += 1
            if x1 > w:
                continue

            y1 = y0 + 1
            if r_seps:
                while y1 <= h and not any(
                    (y1, x) in all_seps for x in range(x0 + 1, x1)
                ):
                    y1 += 1

            rects[y0, x0, y1, x1] = [line[x0 + 1 : x1] for line in lines[y0:y1]]

            if y0 not in y2r:
                y2r[y0] = len(y2r)

        shape: TableShape = {}
        contents: dict[tuple[int, int], str] = {}
        for (y0, x0, y1, x1), lines in rects.items():
            r0, c0 = _find_next(y2r, y0), _find_next(x2c, x0)
            r1, c1 = _find_next(y2r, y1), _find_next(x2c, x1)
            if strip:
                lines = filter(None, map(str.strip, lines))
            shape[r0, c0] = r1 - r0, c1 - c0
            contents[r0, c0] = "\n".join(lines)

        return Table(contents, shape)


def is_none(x: Any):
    return x is None


def _find_next(xxx: dict[int, int], i: int):
    for k, v in sorted(xxx.items()):
        if k >= i:
            return v
    return max(xxx.values()) + 1


def _rect_contains(r: tuple[int, int, int, int], p: tuple[int, int]):
    x0, y0, x1, y1 = r
    x, y = p
    return x0 <= x < x1 and y0 <= y < y1


def cjust(s: str, w: int) -> str:
    size = len(s)
    h = (w - size) // 2
    return " " * h + s + " " * (w - size - h)


def format_table(
    table: Table[Any],
    sep: str = "|",
    pad: str = " ",
    just: Callable[[str, int], str] = cjust,
) -> str:
    lines = ["" for _ in range(table.row_count)]
    for (r0, c0, _, c1), content, _size in _render(
        table, h_sep_width=len(sep), h_pad_width=len(pad), v_sep_width=0
    ):
        if len(content) > 1:
            raise ValueError(f"cannot format table with multiline cells: {content!r}")
        lines[r0] = _edit_str(
            lines[r0], c0, sep + just("\n".join(content), c1 - c0 - 1) + sep
        )

    return "\n".join(lines)


def format_boxed_table(
    table: Table[Any], pad: str = " ", just: Callable[[str, int], str] = cjust
) -> str:
    bars: dict[tuple[int, int], int] = {}
    cells: dict[tuple[int, int], str] = {}

    h_pad_width = len(pad)
    sep_width = 1
    v_sep_width = 1
    total_sep_width = h_pad_width + sep_width

    for (r0, c0, r1, c1), content, content_size in _render(
        table, h_sep_width=sep_width, h_pad_width=h_pad_width, v_sep_width=v_sep_width
    ):
        for r in range(r0, r1 + 1):
            bars[r, c0] = 1
            bars[r, c1] = 1
        for c in range(c0, c1 + 1):
            bars[r0, c] = 1
            bars[r1, c] = 1

        h, _w = content_size
        for r, line in enumerate(content, (r1 - r0 - 1 - h) // 2):
            cells[v_sep_width + r0 + r, c0 + total_sep_width] = cjust(
                line, c1 - c0 - sep_width - sep_width
            )

    final_w = max(c for _, c in bars) + 1
    final_h = max(r for r, _ in bars) + 1
    final = [[" "] * final_w for _ in range(final_h)]

    for r, c in bars:
        final[r][c] = _find_border(
            bars.get((r - 1, c), 0),
            bars.get((r, c + 1), 0),
            bars.get((r + 1, c), 0),
            bars.get((r, c - 1), 0),
        )

    for (r, c), txt in cells.items():
        final[r][c : c + len(txt)] = txt

    return "\n".join("".join(line) for line in final)


def _render(
    table: Table[T],
    h_sep_width: int = 1,
    h_pad_width: int = 1,
    v_sep_width: int = 1,
    str_f: Callable[[T], str] = str,
):
    total_pad = h_pad_width * 2 + h_sep_width

    ncol = table.col_count
    nrow = table.row_count

    content_lines: dict[tuple[int, int], list[str]] = {}
    for ij, content in table.indexed_cells.items():
        content_str = str_f(content)
        lines = [line.rstrip("\n\r") for line in content_str.splitlines()]
        content_lines[ij] = lines

    content_sizes: dict[tuple[int, int], tuple[int, int]] = {}
    for ij, lines in content_lines.items():
        content_sizes[ij] = (
            len(lines),
            max(len(line.rstrip("\n\r")) for line in lines) if lines else 0,
        )

    widths = {(i, i + 1): 1 + h_sep_width for i in range(ncol)}
    heights = {(i, i + 1): 1 + v_sep_width for i in range(nrow)}
    for (row, col), (rspan, cspan) in table.shape.items():
        next_col = col + cspan
        next_row = row + rspan
        h, w = content_sizes.get((row, col), (0, 0))
        heights[row, next_row] = max(h + v_sep_width, heights.get((row, next_row), 0))
        widths[col, next_col] = max(w + total_pad, widths.get((col, next_col), 0))

    # TODO relax/balance loose columns
    c_limits = _limits_from_span_widths(widths)
    r_limits = _limits_from_span_widths(heights)

    for (row, col), (rspan, cspan) in table.shape.items():
        r0 = r_limits[row]
        c0 = c_limits[col]
        r1 = r_limits[row + rspan]
        c1 = c_limits[col + cspan]
        if (row, col) in content_lines:
            yield (r0, c0, r1, c1), content_lines[row, col], content_sizes[row, col]


def _limits_from_span_widths(colspan_widths: dict[tuple[int, int], int]) -> list[int]:
    ncol = max(b for _, b in colspan_widths)
    limits = [0] * (ncol + 1)
    for (a, b), w in sorted(colspan_widths.items()):
        limits[b] = max(limits[b], limits[a] + w)

    return limits


def _find_border(n: int, e: int, s: int, w: int) -> str:
    k = "".join(map(str, [n, e, s, w]))
    b = BORDERS.get(k)
    if b:
        return b
    else:
        for k2, v in BORDERS.items():
            if re.match(k2, k):
                return v
    return "+"


def _edit_str(s: str, i: int, v: str) -> str:
    if len(s) < i:
        return s + " " * (i - len(s)) + v
    else:
        return s[:i] + v + s[i + len(v) :]
