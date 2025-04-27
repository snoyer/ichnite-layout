from __future__ import annotations

import argparse
import gzip
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from itertools import chain
from math import ceil, copysign, pi
from pathlib import Path
from textwrap import dedent
from typing import Callable, Iterable, Iterator, Literal, Sequence

import cairocffi
import networkx
import pangocairocffi
import pangocffi
import svgelements

from codegen.source import Key, base_keymap_from_md, split_mods

NUMROW = r"""1! 2@ 3# 4$ 5% 6^ 7& 8* 9( 0) -_ =+ [{ ]} ;: '" ,< .> /? \| `~""".split()
SHIFTED = {k: v for k, v in NUMROW}
UNSHIFTED = {v: k for k, v in NUMROW}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("readme", metavar="README.MD", help=".md input filename")
    parser.add_argument("output", metavar="RENDER.SVG", help=".pdf outout filename")
    parser.add_argument(
        "--layers", default=None, help="comma-separated list of layer ids"
    )
    parser.add_argument(
        "--columns", type=int, default=2, help="number of columns for the grid"
    )

    args = parser.parse_args()

    keymap, _titles = base_keymap_from_md(open(args.readme))

    selected_ids = args.layers.split(",") if args.layers else list(keymap.layers.keys())

    g = networkx.DiGraph()
    for layer_name, keys in keymap.layers.items():
        for i, key in enumerate(keys):
            if key.hold in keymap.layers:
                g.add_edge(layer_name, key.hold, key=i)  # type: ignore

    thumb_paths: dict[str, set[tuple[int, ...]]] = defaultdict(set)
    for u in g.nodes():  # type: ignore
        for path in networkx.all_simple_paths(g, "base", u):  # type: ignore
            thumb_paths[u].add(
                tuple(g.edges[u, v]["key"] for u, v in zip(path, path[1:]))  # type: ignore
            )

    def layout_key(rowcol: tuple[int, int], i: int):
        row, col = rowcol
        col = col - 6
        x = col - copysign(0.2, col)
        y = row

        if abs(col) == 1:
            x -= copysign(0.1, col)
            y -= 0.5
        if row == 3:
            x -= copysign(0.5, col)
            y += 0.1

        return x, y, "1u_" if i in [13, 18, 35, 38] else "1u"

    layout = [layout_key(rc, i) for i, rc in enumerate(keymap.table_shape.keys())]
    layout_rect = Rect.Union(Rect(x, y, 1, 1) for x, y, _ in layout).pad(0.5)

    svg_rect = Rect(
        layout_rect.x0,
        layout_rect.y0,
        layout_rect.w * args.columns,
        layout_rect.h * ceil(len(selected_ids) / args.columns),
    )

    layer_positions = {
        layer_name: (
            i % args.columns * layout_rect.w,
            i // args.columns * layout_rect.h,
        )
        for i, layer_name in enumerate(selected_ids)
    }

    def make_svg(width: float = 1280, unit: str = "px"):
        svg = ET.Element(
            "svg",
            width=f"{width}{unit}",
            height=f"{width * (svg_rect.h / svg_rect.w)}{unit}",
            viewBox=f"{svg_rect.x0} {svg_rect.y0} {svg_rect.w} {svg_rect.h}",
            xmlns="http://www.w3.org/2000/svg",
        )

        def make_key(
            id: str, w: float = 1, h: float = 1, r1: float = 0.1, r2: float = 0.1
        ):
            rect = Rect(0, 0, w, h)
            rect1 = rect.pad(-0.025 * h)
            rect2 = rect.pad(-0.1 * h)

            base = cairo_rounded_rectangle(*rect1.xywh, r1)
            shade = chain(
                cairo_rounded_rectangle(*rect1.xywh, r1),
                cairo_rounded_rectangle(*rect2.xywh, r2, reverse=True),
            )

            sym = ET.Element("symbol", id=id)
            ET.SubElement(sym, "path", {"class": "base"}, d=cairo_path_to_svg(base))
            ET.SubElement(sym, "path", {"class": "shade"}, d=cairo_path_to_svg(shade))
            return sym

        defs = ET.SubElement(svg, "defs")
        defs.append(make_key("1u"))
        defs.append(make_key("1u_", r2=0.5))

        style = ET.SubElement(svg, "style")
        style.text = dedent(
            """
            use .base { fill: inherit; }

            .sym { fill: #000000; }
            .key { fill: #eeeeee; }
            .held { fill: #999999; }
            .shade { fill: black; fill-opacity: 0.1; }
            .arrow { fill: none; stroke: black; stroke-width:.02; }
            .arrow.head { fill: black; }
            
            @media (prefers-color-scheme: dark){
                .sym { fill: #cccccc; }
                .key { fill: #222222; }
                .held { fill: #444444; }
                .shade { fill: black; fill-opacity: 0.5; }
                .arrow { stroke: #cccccc; }
                .arrow.head { fill: #cccccc; }
            }
            """
        )

        known_legends: dict[str, tuple[str, Rect]] = {}

        for layer_name in selected_ids:
            keys = keymap.layers[layer_name]
            held = set(chain.from_iterable(thumb_paths.get(layer_name, [])))
            x0, y0 = layer_positions[layer_name]

            g = ET.SubElement(svg, "g", transform=f"translate({x0} {y0})")

            for bi, (x, y, key_type) in enumerate(layout):
                ET.SubElement(
                    g,
                    "use",
                    {"class": "held" if bi in held else "key"},
                    href=f"#{key_type}",
                    x=f"{x:g}",
                    y=f"{y:g}",
                )

            for key, (x, y, _) in zip(keys, layout):
                rect = Rect(x, y, 1, 1)
                for text, legend_rect, align in key_sublegends(key, rect.pad(-0.1)):
                    if legend := label_to_pango(text):
                        if legend not in known_legends:
                            is_mod = any(x in legend for x in "⇧⌘⌥◆☰⌃")
                            legend_path, bbox = render_text(
                                legend,
                                font=["Deja Vu", "Intel One Mono"],
                                size=0.25,
                                align=align,
                                strict_bbox=is_mod,
                            )
                            svg_path = cairo_path_to_svg(legend_path)
                            sym_id = f"x{len(known_legends)}"
                            known_legends[legend] = sym_id, bbox

                            ET.SubElement(
                                defs, "path", {"class": "sym"}, id=sym_id, d=svg_path
                            )

                        sym_id, bbox = known_legends[legend]
                        s = min(legend_rect.w / bbox.w, legend_rect.h / bbox.h, 1)
                        tx = legend_rect.cx - bbox.cx * s
                        ty = legend_rect.cy - bbox.cy * s

                        transform = f"translate({tx:g} {ty:g})"
                        if s != 1:
                            transform += f" scale({s:g})"
                        ET.SubElement(g, "use", href=f"#{sym_id}", transform=transform)

        for layer_name, ppaths in thumb_paths.items():
            try:
                x0, y0 = layer_positions[layer_name]
                for path in ppaths:
                    keys = [layout[i] for i in path]
                    xys = [complex(x0 + x + 0.5, y0 + y + 1.1) for x, y, _ in keys]
                    for a, d in zip(xys, xys[1:]):
                        q = (a + d) / 2 + 1j
                        b = a + (q - a) / 3
                        c = d + (q - d) / 3
                        p: CairoPath = [
                            (cairocffi.PATH_MOVE_TO, (a.real, a.imag)),
                            (
                                cairocffi.PATH_CURVE_TO,
                                (b.real, b.imag, c.real, c.imag, d.real, d.imag),
                            ),
                        ]
                        ET.SubElement(
                            svg, "path", {"class": "arrow"}, d=cairo_path_to_svg(p)
                        )
                        ET.SubElement(
                            svg,
                            "path",
                            {"class": "arrow head"},
                            d=cairo_path_to_svg(arrow_heads(p, 0.1)),
                        )
            except KeyError:
                pass

        return svg

    svg = make_svg()
    ET.indent(svg)
    tree = ET.ElementTree(svg)

    if args.output.endswith(".svgz"):
        buf = BytesIO()
        tree.write(buf)
        Path(args.output).write_bytes(gzip.compress(buf.getvalue()))
    else:
        tree.write(args.output)


def material_icon(*codepoints: Sequence[str]) -> str:
    escaped = "".join(f"&#x{c};" for c in codepoints)
    return f'<big><span font="Material Symbols Outlined">{escaped}</span></big>'


def material_icon_with_label(codepoint: str, lbl: str) -> str:
    return (
        material_icon(codepoint)
        + "\n<small><small><small>("
        + lbl
        + ")</small></small></small>"
    )


def text_label(*labels: str):
    joined = "\n".join(labels)
    return f"<small>{joined}</small>"


def lock_label(name: str, sub: str = ""):
    if sub:
        return text_label(name, material_icon("e897"), f"<small>{sub}</small>")
    else:
        return text_label(name, material_icon("e897"))


SYMBOLS = {
    "CMD": "⌘",
    "CTRL": "<big><big><sub>⌃</sub></big></big>",
    "SHIFT": "<b>⇧</b>",
    "ALT": "⌥",
    "SUPER": "◆",
    "rCMD": "⌘",
    "rCTRL": "<big><big><sub>⌃</sub></big></big>",
    "rSHIFT": "⇧",
    "rALT": "⌥",
    "rSUPER": "◆",
    "SPACE": "⎵",
    # "ENTER": "↵",
    "ENTER": material_icon("e31b"),
    "TAB": "⇥",
    "PIPE": "|",
    "BSPC": "<small>⌫</small>",
    "DEL": "<small>⌦</small>",
    "ESC": "<small>esc</small>",
    "APP": "☰",
    # "CAPS": lock_label("caps", "(word)"),
    "CAPS": material_icon("e318"),
    "CLOCK": lock_label("caps"),
    "SLOCK": lock_label("scroll"),
    "NLOCK": lock_label("num"),
    "INS": text_label("insert"),
    "BREAK": text_label("break"),
    "PSCR": text_label("print", "screen"),
    "PAUSE": text_label("pause", "break"),
    "LEFT": "←",
    "RIGHT": "→",
    "UP": "↑",
    "DOWN": "↓",
    "PG_UP": "⇞",
    "PG_DN": "⇟",
    "HOME": "⇱",
    "END": "⇲",
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "PLAY": material_icon("e037"),
    "STOP": material_icon("e047"),
    "PREV": material_icon("e045"),
    "NEXT": material_icon("e044"),
    "FFW": material_icon("e01f"),
    "RWD": material_icon("e020"),
    "MUTE": material_icon("e04f"),
    "VOL+": material_icon("e050"),
    "VOL-": material_icon("e04d"),
    "BRI+": material_icon("e1ac"),
    "BRI-": material_icon("e1ad"),
    "COPY": material_icon("e14d"),
    "CUT": material_icon("e14e"),
    "PASTE": material_icon("e14f"),
    "UNDO": material_icon("e166"),
    "REDO": material_icon("e15a"),
    "COMMENT": material_icon("e4f3"),
    "CALC": material_icon("ea5f"),
    "MYCOMP": material_icon("e88a"),
    "WWW": material_icon("e894"),
    "USB": material_icon("e1e0"),
    "BTCLR": material_icon("e1a7", "e92b"),
    "BOOTL": material_icon("e8d7"),
    "RESET": material_icon("f053"),
    "FIND-": material_icon("e880") + "<small>↑</small>",
    "FIND+": material_icon("e880") + "<small>↓</small>",
    "WH_L": "<small>wh</small>←",
    "WH_R": "<small>wh</small>→",
    "WH_U": "<small>wh</small>↑",
    "WH_D": "<small>wh</small>↓",
    "MM_L": material_icon("e323") + "←",
    "MM_R": material_icon("e323") + "→",
    "MM_U": material_icon("e323") + "↑",
    "MM_D": material_icon("e323") + "↓",
    "MB_1": material_icon("e323") + "1",
    "MB_2": material_icon("e323") + "2",
    "MB_3": material_icon("e323") + "3",
    **{
        f"KP{c}": f"{c}\n<small><small><sup>(KP)</sup></small></small>"
        for c in "+-*/=.,()1234567890"
    },
    **{f"BT{i}": material_icon("e1a7") + f"<small>{i}</small>" for i in range(10)},
    **{
        f"@{os}": material_icon("e30a") + f"\n<small>{os}</small>"
        for os in ("linux", "mac", "win")
    },
    "XXX": "",
}


def label_to_pango(txt: str):
    xs, y = split_mods(txt)
    return "".join(SYMBOLS.get(x, x) for x in (*xs, y))


def key_sublegends(
    key: Key, rect: Rect, default_shifts: bool = False
) -> Iterable[tuple[str, Rect, Literal["c", "l", "r"]]]:
    if key.hold and re.match(r"[rl]?(CMD|ALT|CTR?L|SH?I?FT)", key.hold):
        if key.tap:
            yield key.tap, rect, "c"
        yield key.hold, rect.sub_rect(w=0.3, h=0.3, x=1, y=1), "r"
    elif key.tap:
        val = key.tap
        if len(val) == 2 and all(x in set((*SHIFTED, *UNSHIFTED)) for x in val):
            yield val[1], rect.sub_rect(h=0.5, y=0), "c"
            yield val[0], rect.sub_rect(h=0.5, y=1), "c"
        elif default_shifts and val in SHIFTED:
            yield SHIFTED[val], rect.sub_rect(h=0.5, y=0), "c"
            yield val, rect.sub_rect(h=0.5, y=1), "c"
        else:
            yield val, rect.sub_rect(), "c"


@dataclass
class Rect:
    x0: float
    y0: float
    w: float
    h: float

    @property
    def x1(self):
        return self.x0 + self.h

    @property
    def y1(self):
        return self.y0 + self.h

    def pad(self, padding: float):
        return Rect(
            self.x0 - padding,
            self.y0 - padding,
            self.w + 2 * padding,
            self.h + 2 * padding,
        )

    def sub_rect(self, w: float = 1, h: float = 1, x: float = 0.5, y: float = 0.5):
        w1, h1 = self.w * w, self.h * h
        return Rect(self.x0 + (self.w - w1) * x, self.y0 + (self.h - h1) * y, w1, h1)

    @property
    def xywh(self):
        return self.x0, self.y0, self.w, self.h

    @property
    def cx(self):
        return self.x0 + self.w / 2

    @property
    def cy(self):
        return self.y0 + self.h / 2

    @classmethod
    def Union(cls, rects: Iterable["Rect"]):
        rects = list(rects)
        x0 = min(r.x0 for r in rects)
        y0 = min(r.y0 for r in rects)
        x1 = max(r.x1 for r in rects)
        y1 = max(r.y1 for r in rects)
        return cls(x0, y0, x1 - x0, y1 - y0)


def tmp_context():
    surface = cairocffi.RecordingSurface(cairocffi.CONTENT_COLOR_ALPHA, None)
    return cairocffi.Context(surface)


def transform_cairo_path(
    f: Callable[[complex], complex], path: CairoPathLike
) -> CairoPath:
    def coords_to_points(coords: tuple[float, ...]):
        return (complex(*coords[i : i + 2]) for i in range(0, len(coords), 2))

    def points_to_coords(points: Iterable[complex]):
        return chain.from_iterable((p.real, p.imag) for p in points)

    return [
        (cmd, tuple(points_to_coords(map(f, coords_to_points(coords)))))
        for cmd, coords in path
    ]


CairoPath = list[tuple[int, tuple[float, ...]]]
CairoPathLike = Iterable[tuple[int, tuple[float, ...]]]


def cairo_path_to_svg(path: CairoPathLike):
    def parts() -> Iterator[float | str]:
        for cmd, cs in path:
            if cmd == cairocffi.PATH_MOVE_TO:
                yield "M"
            elif cmd == cairocffi.PATH_LINE_TO:
                yield "L"
            elif cmd == cairocffi.PATH_CURVE_TO:
                yield "C"
            elif cmd == cairocffi.PATH_CLOSE_PATH:
                yield "Z"
            yield from cs

    d = " ".join(map(str, parts()))
    return simplify_svg_path(d)


def simplify_svg_path(d: str):
    def f(float_str: str):
        s = f"{float(float_str):.4f}".rstrip("0").rstrip(".")
        return re.sub(r"^([-+]?)0+\.", r"\1.", s)

    d = svgelements.Path(d).d(relative=True)  # type: ignore
    d = re.sub(r"(\d+)[.](\d+)", lambda m: f(m.group(0)), d)
    d = re.sub(r"([mlc])\s+", r"\1", d)
    return d


def cairo_rounded_rectangle(
    x: float,
    y: float,
    w: float,
    h: float,
    r: float,
    reverse: bool = False,
) -> CairoPath:
    r = min(r, min(w, h) / 2)
    x0 = x + r
    y0 = y + r
    x1 = x + w - r
    y1 = y + h - r
    ctx = tmp_context()
    ctx.new_path()
    if reverse:
        ctx.arc_negative(x0, y1, r, pi, pi / 2)
        ctx.arc_negative(x1, y1, r, pi / 2, 0)
        ctx.arc_negative(x1, y0, r, pi * 2, pi * 3 / 2)
        ctx.arc_negative(x0, y0, r, pi * 3 / 2, pi)
    else:
        ctx.arc(x0, y0, r, pi, pi * 3 / 2)
        ctx.arc(x1, y0, r, pi * 3 / 2, pi * 2)
        ctx.arc(x1, y1, r, 0, pi / 2)
        ctx.arc(x0, y1, r, pi / 2, pi)
    return ctx.copy_path()


def render_text(
    text: str,
    font: str | Iterable[str] = "Deja Vu",
    size: float = 12,
    align: str = "c",
    strict_bbox: bool = False,
) -> tuple[CairoPath, Rect]:
    if "w" in align:
        pango_align = pangocffi.Alignment.LEFT
    elif "e" in align:
        pango_align = pangocffi.Alignment.RIGHT
    else:
        pango_align = pangocffi.Alignment.CENTER

    scale = 1000
    ctx = tmp_context()
    layout = pangocairocffi.create_layout(ctx)
    layout.alignment = pango_align

    def make_markup():
        fonts = [font] if isinstance(font, str) else list(font)
        for single_font in fonts:
            yield f'<span font="{single_font} {size * scale}">'
        yield text
        for single_font in fonts:
            yield "</span>"

    layout.apply_markup("".join(make_markup()))

    drawn_extent, logical_extent = layout.get_extents()

    def f(u: int):
        return pangocffi.units_to_double(u) / scale

    r = drawn_extent if strict_bbox else logical_extent
    with ctx:
        ctx.new_path()
        pangocairocffi.layout_path(ctx, layout)
        return (
            transform_cairo_path(lambda p: p / scale, ctx.copy_path()),
            Rect(*map(f, (r.x, r.y, r.width, r.height))),
        )


def arrow_heads(path: CairoPathLike, s: float) -> CairoPathLike:
    for sub in split_path(path):
        while sub[-1][0] == cairocffi.PATH_CLOSE_PATH:
            sub.pop()

        if sub[-1][0] == cairocffi.PATH_CURVE_TO:
            a = sub[-1][1]
            yield from arrow_head(complex(a[2], a[3]), complex(a[4], a[5]), s)
        elif sub[-1][0] == cairocffi.PATH_LINE_TO:
            yield from arrow_head(
                complex(*sub[-2][1][-2:]), complex(*sub[-1][1][-2:]), s
            )
        else:
            raise ValueError()


def arrow_head(a: complex, b: complex, s: float) -> CairoPath:
    u = (b - a) / abs(b - a)
    v = complex(-u.imag, u.real)
    c = b - u * s + v * s / 2
    d = b - u * s - v * s / 2
    return [
        (cairocffi.PATH_MOVE_TO, (b.real, b.imag)),
        (cairocffi.PATH_LINE_TO, (c.real, c.imag)),
        (cairocffi.PATH_LINE_TO, (d.real, d.imag)),
        (cairocffi.PATH_CLOSE_PATH, ()),
    ]


def split_path(path: CairoPathLike) -> Iterator[CairoPath]:
    sub: CairoPath = []
    for c, ps in path:
        if c == cairocffi.PATH_MOVE_TO and sub:
            yield sub[:]
            sub = []
        sub.append((c, ps))
    if sub:
        yield sub[:]


if __name__ == "__main__":
    main()
