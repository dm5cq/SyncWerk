"""Farbschemata: Dunkel (Standard, wie FotoRahmen/YT-Lader), Hell und Hoher Kontrast."""
import sys

IS_WIN = sys.platform.startswith("win")
FAMILY = "Segoe UI" if IS_WIN else "DejaVu Sans"
MONO = "Consolas" if IS_WIN else "DejaVu Sans Mono"

_COMMON_STATUS = ("green", "blue", "yellow", "red")

THEMES = {
    "dunkel": {
        "menubar": "#202024", "menu_bg": "#2b2b30", "menu_text": "#f0f0f2", "menu_hover": "#3a3a41", "footer": "#2f2f34",
        "bg": "#1c1c1f", "panel": "#26262a", "field": "#202024", "text": "#ececef", "muted": "#a3a3ab",
        "head": "#141416", "head_text": "#d6d6da", "head_btn": "#141416", "head_btn_hover": "#2c2c31",
        "pane_head": "#35353b", "pane_head_text": "#ffffff",
        "ctrl": "#3a3a41", "ctrl_text": "#ececef", "ctrl_hover": "#4a4a53",
        "border": "#38383f", "field_border": "#4a4a52", "trough": "#35353b",
        "accent": "#f28c28", "accent_d": "#d9711a", "accent_text": "#ffffff", "focus": "#ffb26b",
        "green": "#4cc274", "blue": "#5aa5f0", "yellow": "#f2c94c", "red": "#f06262", "on_red": "#ffffff",
        "t_green": "#1c3324", "t_blue": "#1a2b40", "t_yellow": "#36301a", "t_red": "#402124",
        "ghost": "#6c6c74", "sel_bg": "#f28c28", "sel_text": "#ffffff",
        "dis_bg": "#2e2e33", "dis_text": "#66666e",
    },
    "hell": {
        "menubar": "#3c3c40", "menu_bg": "#3c3c40", "menu_text": "#ffffff", "menu_hover": "#505055", "footer": "#e4e4e7",
        "bg": "#f1f1f2", "panel": "#ffffff", "field": "#ffffff", "text": "#2b2b2e", "muted": "#6e6e73",
        "head": "#2b2b2e", "head_text": "#d0d0d4", "head_btn": "#2b2b2e", "head_btn_hover": "#3c3c40",
        "pane_head": "#3c3c40", "pane_head_text": "#ffffff",
        "ctrl": "#e4e4e7", "ctrl_text": "#2b2b2e", "ctrl_hover": "#d3d3d7",
        "border": "#d6d6da", "field_border": "#cfcfd4", "trough": "#e4e4e7",
        "accent": "#f28c28", "accent_d": "#d9711a", "accent_text": "#ffffff", "focus": "#d9711a",
        "green": "#2e9e55", "blue": "#2f7fd1", "yellow": "#b98a00", "red": "#d64040", "on_red": "#ffffff",
        "t_green": "#e4f5e9", "t_blue": "#e3eefb", "t_yellow": "#fff4cc", "t_red": "#fbe2e2",
        "ghost": "#a8a8ad", "sel_bg": "#f28c28", "sel_text": "#ffffff",
        "dis_bg": "#d9d9dc", "dis_text": "#9a9a9f",
    },
    "kontrast": {
        "menubar": "#000000", "menu_bg": "#000000", "menu_text": "#ffffff", "menu_hover": "#333333", "footer": "#000000",
        "bg": "#000000", "panel": "#000000", "field": "#000000", "text": "#ffffff", "muted": "#ffffff",
        "head": "#000000", "head_text": "#ffff00", "head_btn": "#000000", "head_btn_hover": "#333333",
        "pane_head": "#000000", "pane_head_text": "#ffff00",
        "ctrl": "#000000", "ctrl_text": "#ffffff", "ctrl_hover": "#333333",
        "border": "#ffffff", "field_border": "#ffffff", "trough": "#333333",
        "accent": "#ffff00", "accent_d": "#ffd000", "accent_text": "#000000", "focus": "#00ffff",
        "green": "#00ff66", "blue": "#33ccff", "yellow": "#ffff00", "red": "#ff5050", "on_red": "#000000",
        "t_green": "#003314", "t_blue": "#002640", "t_yellow": "#333300", "t_red": "#400000",
        "ghost": "#c0c0c0", "sel_bg": "#00ffff", "sel_text": "#000000",
        "dis_bg": "#000000", "dis_text": "#8c8c8c",
    },
}
NAMES = {"dunkel": "Dunkel", "hell": "Hell", "kontrast": "Hoher Kontrast"}
TINT = {"green": "t_green", "blue": "t_blue", "yellow": "t_yellow", "red": "t_red"}

C = dict(THEMES["dunkel"])
_state = {"name": "dunkel", "scale": 1.0}


def apply(name: str, scale: float = 1.0):
    if name not in THEMES:
        name = "dunkel"
    C.clear()
    C.update(THEMES[name])
    _state["name"] = name
    _state["scale"] = max(0.8, min(2.0, scale))


def name():
    return _state["name"]


def scale():
    return _state["scale"]


def is_hc():
    return _state["name"] == "kontrast"


def F(size=10, weight="normal", mono=False, italic=False):
    """Schrift in aktueller Skalierung; im Hohen Kontrast immer fett."""
    w = "bold" if (weight == "bold" or is_hc()) else "normal"
    s = max(7, round(size * _state["scale"]))
    font = (MONO if mono else FAMILY, s, w)
    return font + ("italic",) if italic and not is_hc() else font
