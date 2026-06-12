"""Era mapping helpers for 5-year PL spans."""

from __future__ import annotations

ERAS = [
    "1992-1995",
    "1995-2000",
    "2000-2005",
    "2005-2010",
    "2010-2015",
    "2015-2020",
    "2020-2025",
]

# PL season end-year (soccerdata format) -> era label
SEASON_TO_ERA: dict[int, str] = {}
for era in ERAS:
    start, end = era.split("-")
    start_year = int(start)
    end_year = int(end)
    # Era 1992-1995 covers seasons ending 1993, 1994, 1995
    for y in range(start_year + 1, end_year + 1):
        SEASON_TO_ERA[y] = era

# soccerdata `seasons` arg = campaign start year (1992 -> 1992-93 ending 1993)
SCRAPE_SEASONS = list(range(1992, 2025))
PL_SEASONS = SCRAPE_SEASONS


def season_code_to_end_year(code: str) -> int:
    """FBref/soccerdata code like 9293 or 2425 -> PL season end-year."""
    code = str(code).zfill(4)
    y2 = int(code[2:])
    return 2000 + y2 if y2 < 50 else 1900 + y2

MIN_ERA_MINUTES = 450


def season_to_era(season_end_year: int) -> str | None:
    return SEASON_TO_ERA.get(int(season_end_year))
