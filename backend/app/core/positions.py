"""Position parsing and fit helpers (mirrors data/lib/positions.py)."""

from __future__ import annotations

import hashlib
import re
import unicodedata

POSITIONS = [
    "GK", "LB", "RB", "CB", "LWB", "RWB", "DM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST"
]

# FBref uses coarse DF/MF/FW codes — map combos to realistic game roles.
FBREF_TO_GAME = {
    "GK": ("GK", []),
    "DF": ("CB", ["LB", "RB"]),
    "MF": ("CM", ["CAM", "DM"]),
    "FW": ("ST", ["LW", "RW"]),
    "DF,FW": ("LW", ["RW", "LB", "RB", "ST"]),
    "FW,DF": ("LW", ["RW", "ST", "LB", "RB"]),
    "DF,MF": ("LB", ["RB", "CM", "CB"]),
    "MF,DF": ("CM", ["LB", "RB", "DM"]),
    "MF,FW": ("CAM", ["LW", "RW", "ST", "CM"]),
    "FW,MF": ("ST", ["CAM", "LW", "RW"]),
}

KNOWN_RB_SLUGS = {
    "gary_neville",
    "lee_dixon",
    "kyle_walker",
    "nathaniel_clyne",
    "trent_alexander_arnold",
    "aaron_wan_bissaka",
    "micah_richards",
    "pablo_zabaleta",
    "kieran_trippier",
    "glen_johnson",
    "branislav_ivanovic",
    "bacary_sagna",
    "jose_bosingwa",
    "justin_hoyte",
}

KNOWN_LB_SLUGS = {
    "andrew_robertson",
    "luke_shaw",
    "ashley_cole",
    "patrice_evra",
    "gael_clichy",
    "leighton_baines",
    "jose_enrique",
    "fabio_aurelio",
    "wayne_bridge",
    "sylvinho",
    "cesar_azpilicueta",
    "ashley_young",
    "james_milner",
}


def slugify(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name.strip("_")[:64]


MIN_ERA_MINUTES = 450


def is_valid_player_name(name: str, *, minutes: int = 0) -> bool:
    if len(name.strip().split()) >= 2:
        return True
    return minutes >= MIN_ERA_MINUTES


def _side_fullback(player: str, *, extra: list[str] | None = None) -> tuple[str, list[str]]:
    slug = slugify(player)
    secondaries = list(extra or ["RWB", "LWB"])
    if slug in KNOWN_RB_SLUGS:
        return "RB", ["LB", *secondaries]
    if slug in KNOWN_LB_SLUGS:
        return "LB", ["RB", *secondaries]
    h = int(hashlib.md5(slug.encode()).hexdigest(), 16)
    if h % 2:
        return "RB", ["LB", *secondaries]
    return "LB", ["RB", *secondaries]


def format_position_label(primary: str, secondary: list[str] | None = None, *, max_parts: int = 3) -> str:
    parts: list[str] = []
    for pos in [primary, *(secondary or [])]:
        if pos and pos not in parts:
            parts.append(pos)
        if len(parts) >= max_parts:
            break
    return " · ".join(parts)


def parse_fbref_positions(pos: str) -> tuple[str, list[str]]:
    if not pos or not isinstance(pos, str):
        return "CM", []
    pos = pos.strip().upper()
    if pos in FBREF_TO_GAME:
        primary, secondaries = FBREF_TO_GAME[pos]
        return primary, list(secondaries)
    token = pos.split(",")[0].strip()
    if token in FBREF_TO_GAME:
        primary, secondaries = FBREF_TO_GAME[token]
        return primary, list(secondaries)
    return "CM", []


def resolve_era_position(
    fbref_pos: str,
    *,
    player: str = "",
    gls_per90: float = 0.0,
    ast_per90: float = 0.0,
    ga_per90: float = 0.0,
    minutes: int = 0,
) -> tuple[str, list[str]]:
    pos = (fbref_pos or "").strip().upper()
    primary, secondaries = parse_fbref_positions(pos)

    if pos == "DF":
        if ast_per90 >= 0.06:
            return _side_fullback(player)
        if ga_per90 == 0 and gls_per90 == 0 and ast_per90 == 0 and minutes >= 900:
            return "CB", ["LB", "RB"]
        if gls_per90 <= 0.03 and 0.02 <= ga_per90 < 0.15:
            return "CB", ["LB", "RB"]
        if (
            ast_per90 < 0.05
            and gls_per90 <= 0.22
            and ga_per90 < 0.25
            and (ga_per90 >= 0.02 or minutes >= 2000)
        ):
            return "CB", ["LB", "RB"]
        return _side_fullback(player, extra=["CB"])

    if pos == "FW":
        if gls_per90 >= 0.55:
            return "ST", ["LW", "RW", "CAM"]
        if (
            gls_per90 >= 0.15
            and ast_per90 >= 0.20
            and ast_per90 >= gls_per90
            and ga_per90 >= 0.40
        ):
            return "ST", ["LW", "RW"]
        if gls_per90 >= 0.45 and (ast_per90 == 0 or ast_per90 / gls_per90 < 0.40):
            return "ST", ["LW", "RW"]
        if gls_per90 >= 0.50 and ast_per90 >= 0.15:
            return "LW", ["RW", "ST", "CAM"]
        if ga_per90 >= 0.55 and gls_per90 >= 0.30:
            return "ST", ["LW", "RW"]
        if ga_per90 >= 0.35:
            return "LW", ["RW", "ST", "CAM"]
        return "ST", ["LW", "RW"]

    if pos == "MF":
        if ast_per90 >= 0.12 and ga_per90 >= 0.30:
            return "LW", ["RW", "CAM", "CM"]

    if pos == "DF,MF":
        if ast_per90 >= 0.08:
            return _side_fullback(player, extra=["CM", "CB"])
        return _side_fullback(player, extra=["CM", "CB"])

    if pos == "MF,DF":
        if ast_per90 >= 0.10 and ga_per90 >= 0.25:
            return "LW", ["RW", "CAM", "CM"]
        if ast_per90 >= 0.06:
            return _side_fullback(player, extra=["CM", "DM"])

    if pos in {"FW,MF", "MF,FW"}:
        if ast_per90 >= 0.18 or ga_per90 >= 0.32:
            return "LW", ["RW", "CAM", "ST"]
        return primary, secondaries

    return primary, secondaries


def default_fits(primary: str, secondary: list[str]) -> dict[str, int]:
    fits = {p: 20 for p in POSITIONS}
    fits[primary] = 97
    for s in secondary:
        if s in fits:
            fits[s] = max(fits[s], 82)
    if primary == "GK":
        fits["GK"] = 98
    for p in POSITIONS:
        if p == primary or p in secondary:
            continue
        if primary in {"CB", "LB", "RB"} and p in {"CB", "LB", "RB", "LWB", "RWB"}:
            fits[p] = max(fits[p], 65)
        if primary in {"CM", "DM", "CAM"} and p in {"CM", "DM", "CAM", "LM", "RM"}:
            fits[p] = max(fits[p], 60)
        if primary in {"ST", "LW", "RW"} and p in {"ST", "LW", "RW", "CAM"}:
            fits[p] = max(fits[p], 55)
        if primary in {"LM", "RM"} and p in {"LW", "RW", "LB", "RB", "CM"}:
            fits[p] = max(fits[p], 60)
    return fits
