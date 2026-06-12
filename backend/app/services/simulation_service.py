from __future__ import annotations

import hashlib
import random


def record_from_points(points: int) -> tuple[int, int, int]:
    points = max(15, min(114, points))
    best = None
    for wins in range(39):
        for draws in range(39 - wins):
            losses = 38 - wins - draws
            if wins * 3 + draws != points:
                continue
            draw_penalty = abs(draws - 6)
            loss_penalty = max(0, losses - 15)
            too_many_draws_penalty = max(0, draws - 12) * 2
            score = draw_penalty + loss_penalty + too_many_draws_penalty
            candidate = (score, wins, draws, losses)
            if best is None or candidate < best:
                best = candidate
    if best:
        _, wins, draws, losses = best
        return wins, draws, losses
    return record_from_points(points - 1)


def make_seed(room_id: str, completed_at: str, version: str) -> int:
    raw = f"{room_id}:{completed_at}:{version}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:16], 16)


def simulate_record(team_strength: float, seed: int, team_index: int) -> dict:
    rng = random.Random(seed + team_index * 9973)
    season_strength = team_strength + rng.gauss(0, 2.5)
    season_strength = max(1, min(100, season_strength))

    expected_points = 25 + (season_strength - 60) * 2.1
    expected_points = max(20, min(112, expected_points))
    internal_points = round(expected_points + rng.gauss(0, 4))
    internal_points = max(15, min(114, internal_points))

    if season_strength >= 97 and rng.random() < 0.02:
        wins, draws, losses = 38, 0, 0
    else:
        wins, draws, losses = record_from_points(internal_points)

    if season_strength >= 90 and wins < 30:
        wins, draws, losses = record_from_points(internal_points + 6)
    if season_strength < 55 and wins > 22:
        wins, draws, losses = record_from_points(internal_points - 8)

    return {
        "internal_team_strength": round(team_strength, 2),
        "internal_season_strength": round(season_strength, 2),
        "internal_expected_points": int(round(expected_points)),
        "internal_points": internal_points,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "record": f"{wins}-{draws}-{losses}",
    }
