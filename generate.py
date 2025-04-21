import re
import sys
from argparse import ArgumentParser, Namespace
from typing import Callable, Iterable, TextIO, TypeVar

from codegen.qmk import CustomShift, QmkBinding, QmkKey, generate_qmk_layout_code
from codegen.source import ALT_LAYOUTS, keymap_from_md
from codegen.zmk import (
    Binding,
    bootloader_binding,
    bt_binding,
    generate_zmk_keymap_code,
    shiftmorph_binding,
    utf8_linux_macro_binding,
    utf8_mac_macro_binding,
    utf8_win_macro_binding,
)


def argument_parser():
    parser = ArgumentParser(
        description="generate ZMK/QMK keymap code from markdown tables"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser.add_argument("readme", metavar="README.MD", help="readme markdown filename")
    parser.add_argument("output", metavar="OUTPUT", help="output keymap filename")
    parser.add_argument(
        "--reshape",
        dest="reshape",
        help="alternative layout to reshape to",
        choices=ALT_LAYOUTS.keys(),
    )
    zmk = subparsers.add_parser("ZMK", help="create a ZMK keymap")
    zmk.add_argument(
        "--transform",
        default="default_transform",
        metavar="NAME",
        help="matrix transform name",
    )

    qmk = subparsers.add_parser("QMK", help="create a QMK layout")
    qmk.add_argument(
        "--layout", default="LAYOUT", metavar="NAME", help="layout macro name"
    )

    return parser


T = TypeVar("T")


def main(args: Namespace):
    keymap, titles, multi_os_layers = keymap_from_md(
        open(args.readme), reshape=args.reshape
    )
    if args.command == "ZMK":
        code = generate_zmk_keymap_code(
            keymap,
            titles,
            multi_os_layers,
            transform_name=args.transform,
            aliases_for_os=zmk_aliases_for_os,
            extra_includes=(
                "behaviors/capslock.dtsi",
                "behaviors/base_layer.dtsi",
            ),
        )
    elif args.command == "QMK":
        code = [
            generate_qmk_layout_code(
                keymap,
                titles,
                multi_os_layers,
                layout_name=args.layout,
                aliases_for_os=qmk_aliases_for_os,
            )
        ]
    else:
        raise ValueError(f"invalid command: {args.command}")

    if args.output == "-":
        print_line(code)
    else:
        with open(args.output, "w") as f:
            print_line(code, f)


def zmk_aliases_for_os(
    os: str,
) -> dict[str, str | Binding | Callable[[re.Match[str]], str | Binding]]:
    return {
        "'\"": "SQT",
        # "'\"": shiftmorph_binding("'", '"'),
        ",;": shiftmorph_binding(",", ";"),
        ".?": shiftmorph_binding(".", "?"),
        "/\\": shiftmorph_binding("/", "\\"),
        "XXX": Binding("none"),
        "___": Binding("trans"),
        "RESET": Binding("sys_reset"),
        "BOOTL": bootloader_binding(),
        "USB": Binding("out", "OUT_USB"),
        #
        "NLOCK": "KP_NUM",
        "CLOCK": "CLCK",
        "SLOCK": "SLCK",
        "BREAK": "PAUSE_BREAK",
        "APP": "K_APP",
        "PSCR": "PSCRN",
        "PLAY": "C_PLAY_PAUSE",
        "STOP": "C_STOP",
        "PAUSE": "C_PAUSE",
        "PREV": "C_PREV",
        "NEXT": "C_NEXT",
        "FFW": "C_FF",
        "RWD": "C_RW",
        "MUTE": "C_MUTE",
        "VOL+": "C_VOL_UP",
        "VOL-": "C_VOL_DN",
        "BRI+": "C_BRI_UP",
        "BRI-": "C_BRI_DN",
        "MYCOMP": "C_AL_MY_COMPUTER",
        "WWW": "C_AL_WWW",
        "CALC": "C_AL_CALCULATOR",
        #
        r"BT(\d+)": lambda m: bt_binding(int(m.group(1))),
        r"@(.+)": lambda m: Binding("base", m.group(1)),
        r"([\u0080-\uffff])$": lambda m: {
            "linux": utf8_linux_macro_binding,
            "mac": utf8_mac_macro_binding,
            "win": utf8_win_macro_binding,
        }[os](m.group(1)),
        "CAPS": Binding("capslock_word_mac" if os == "mac" else "capslock_word"),
        #
        "MM_U": Binding("mmv", "MOVE_UP"),
        "MM_D": Binding("mmv", "MOVE_DOWN"),
        "MM_L": Binding("mmv", "MOVE_LEFT"),
        "MM_R": Binding("mmv", "MOVE_RIGHT"),
        "MB_1": Binding("mkp", "MB1"),
        "MB_2": Binding("mkp", "MB2"),
        "MB_3": Binding("mkp", "MB3"),
    }


def qmk_aliases_for_os(
    os: str,
) -> dict[str, str | QmkBinding | Callable[[re.Match[str]], str | QmkBinding]]:
    return {
        "PLAY": "MPLY",
        "STOP": "MSTP",
        "MUTE": "MUTE",
        "PREV": "MPRV",
        "NEXT": "MNXT",
        "FFW": "MFFD",
        "RWD": "MRWD",
        "VOL+": "VOLU",
        "VOL-": "VOLD",
        "BRI+": "BRIU",
        "BRI-": "BRID",
        "PG_UP": "PGUP",
        "PG_DN": "PGDOWN",
        "SLOCK": "KC_SCRL",
        "NLOCK": "KC_NUM_LOCK",
        "MYCOMP": "MYCM",
        "CALC": "CALC",
        "WWW": "WHOM",
        "RESET": "QK_BOOT",
        "BOOTL": "QK_REBOOT",
        "DEBUG": "DB_TOGG",
        "XXXXX": "XXX",
        r"([\u0080-\uffff])$": lambda m: QmkKey("UC", "0x%04x" % ord(m.group(1))),
        "'\"": CustomShift("KC_QUOT", "KC_DQUO"),
        ",;": CustomShift("KC_COMM", "KC_SCLN"),
        ".?": CustomShift("KC_DOT", "KC_QUES"),
        "/\\": CustomShift("KC_SLSH", "KC_BSLS"),
    }


def print_line(lines: Iterable[str], f: TextIO = sys.stdout):
    for line in lines:
        f.write(line)
        f.write("\n")
    f.flush()


if __name__ == "__main__":
    exit(main(argument_parser().parse_args()))
