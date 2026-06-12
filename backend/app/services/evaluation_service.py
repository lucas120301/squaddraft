from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class SlotAssignment:
    slot_id: str
    position: str
    player_id: str
    draft_value: float
    fit: int


ATTACK_WEIGHTS = {
    "ST": 1.00,
    "LW": 0.95,
    "RW": 0.95,
    "CAM": 0.85,
    "CM": 0.30,
    "LB": 0.20,
    "RB": 0.20,
    "LWB": 0.20,
    "RWB": 0.20,
    "CB": 0.05,
    "GK": 0.00,
    "DM": 0.15,
    "LM": 0.25,
    "RM": 0.25,
}

MIDFIELD_WEIGHTS = {
    "CM": 1.00,
    "DM": 1.00,
    "CAM": 0.85,
    "LM": 0.70,
    "RM": 0.70,
    "LW": 0.35,
    "RW": 0.35,
    "LB": 0.35,
    "RB": 0.35,
    "LWB": 0.35,
    "RWB": 0.35,
    "ST": 0.20,
    "CB": 0.20,
    "GK": 0.00,
}

DEFENCE_WEIGHTS = {
    "CB": 1.00,
    "LB": 0.85,
    "RB": 0.85,
    "LWB": 0.75,
    "RWB": 0.75,
    "DM": 0.80,
    "CM": 0.35,
    "LM": 0.25,
    "RM": 0.25,
    "ST": 0.10,
    "LW": 0.10,
    "RW": 0.10,
    "CAM": 0.10,
    "GK": 0.00,
}

FORMATION_BONUSES = {
    "4-3-3": ("attack", lambda a: a.get("lw") and a.get("st") and a.get("rw")),
    "4-2-3-1": ("midfield", lambda a: a.get("dm1") and a.get("dm2") and a.get("cam")),
    "4-4-2": ("attack", lambda a: a.get("st1") and a.get("st2")),
    "3-5-2": ("midfield", lambda a: a.get("lwb") and a.get("rwb")),
    "5-3-2": ("defence", lambda a: a.get("cb1") and a.get("cb2") and a.get("cb3")),
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def draft_value(base_rating: int, rating_modifier: int) -> int:
    return int(clamp(base_rating + rating_modifier, 1, 99))


def effective_value(dv: int, fit: int) -> float:
    return dv * (fit / 100)


def weighted_area_score(assignments: list[SlotAssignment], weights: dict[str, float], attr_getter) -> float:
    total_w = 0.0
    total_v = 0.0
    for a in assignments:
        w = weights.get(a.position, 0.1)
        if w <= 0:
            continue
        attr = attr_getter(a)
        total_w += w
        total_v += attr * w
    return total_v / total_w if total_w else 0.0


def compute_balance(assignments: list[SlotAssignment], formation_id: str) -> float:
    score = 100.0
    labels = {a.slot_id: a for a in assignments}

    for a in assignments:
        if 50 <= a.fit < 70:
            score -= 5
        elif 1 <= a.fit < 50:
            score -= 12
        elif a.fit == 0:
            score -= 25

    gk = next((a for a in assignments if a.position == "GK"), None)
    if not gk or gk.fit < 85:
        score -= 25

    def count_fit(min_fit: int, positions: set[str]) -> int:
        return sum(1 for a in assignments if a.position in positions and a.fit >= min_fit)

    if count_fit(70, {"CB", "LB", "RB", "LWB", "RWB", "DM"}) < 3:
        score -= 15
    if count_fit(70, {"CM", "DM", "CAM", "LM", "RM"}) < 2:
        score -= 10

    forwards = sum(1 for a in assignments if a.position in {"ST", "LW", "RW", "CAM"})
    if forwards > 4:
        score -= 10

    weak = sum(1 for a in assignments if a.draft_value * (a.fit / 100) < 50)
    if weak > 2:
        score -= 8

    return clamp(score, 20, 100)


def evaluate_team(
    formation_id: str,
    assignments: list[SlotAssignment],
    player_attrs: dict[str, dict],
) -> dict[str, float]:
    for a in assignments:
        attrs = player_attrs[a.player_id]
        a.draft_value = float(draft_value(attrs["base_rating"], attrs.get("rating_modifier", 0)))

    def attack_getter(a: SlotAssignment) -> float:
        attrs = player_attrs[a.player_id]
        ev = effective_value(int(a.draft_value), a.fit)
        return (attrs.get("attack") or ev) * (ev / 100)

    def mid_getter(a: SlotAssignment) -> float:
        attrs = player_attrs[a.player_id]
        ev = effective_value(int(a.draft_value), a.fit)
        return (attrs.get("midfield") or ev) * (ev / 100)

    def def_getter(a: SlotAssignment) -> float:
        attrs = player_attrs[a.player_id]
        ev = effective_value(int(a.draft_value), a.fit)
        return (attrs.get("defence") or ev) * (ev / 100)

    attack_score = weighted_area_score(assignments, ATTACK_WEIGHTS, attack_getter)
    midfield_score = weighted_area_score(assignments, MIDFIELD_WEIGHTS, mid_getter)
    defence_score = weighted_area_score(assignments, DEFENCE_WEIGHTS, def_getter)

    gk = next((a for a in assignments if a.position == "GK"), None)
    gk_score = effective_value(int(gk.draft_value), gk.fit) if gk else 25.0

    balance_score = compute_balance(assignments, formation_id)

    team_strength = (
        attack_score * 0.30
        + midfield_score * 0.25
        + defence_score * 0.25
        + gk_score * 0.10
        + balance_score * 0.10
    )

    slot_map = {a.slot_id: a for a in assignments}
    bonus = FORMATION_BONUSES.get(formation_id)
    if bonus:
        area, check = bonus
        if check(slot_map):
            if area == "attack":
                attack_score += 2
            elif area == "midfield":
                midfield_score += 2
            elif area == "defence":
                defence_score += 2
            team_strength = (
                attack_score * 0.30
                + midfield_score * 0.25
                + defence_score * 0.25
                + gk_score * 0.10
                + balance_score * 0.10
            )

    return {
        "attack_score": round(attack_score, 2),
        "midfield_score": round(midfield_score, 2),
        "defence_score": round(defence_score, 2),
        "gk_score": round(gk_score, 2),
        "balance_score": round(balance_score, 2),
        "team_strength": round(clamp(team_strength, 1, 100), 2),
    }
