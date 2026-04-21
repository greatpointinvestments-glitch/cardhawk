"""Game Night Mode — stat thresholds, performance alerts, portfolio impact."""


# --- Stat Thresholds by Sport ---

THRESHOLDS = {
    "NBA": {
        "MONSTER": {"pts": 40, "reb": 20, "ast": 15, "stl": 6, "blk": 6},
        "BIG": {"pts": 30, "reb": 15, "ast": 12, "stl": 5, "blk": 5},
        "SOLID": {"pts": 22, "reb": 10, "ast": 8, "stl": 3, "blk": 3},
    },
    "NFL": {
        "MONSTER": {"pass_yds": 400, "pass_td": 4, "rush_yds": 150, "rush_td": 3, "rec_yds": 150},
        "BIG": {"pass_yds": 300, "pass_td": 3, "rush_yds": 100, "rush_td": 2, "rec_yds": 100},
        "SOLID": {"pass_yds": 250, "pass_td": 2, "rush_yds": 75, "rush_td": 1, "rec_yds": 75},
    },
    "MLB": {
        "MONSTER": {"hr": 3, "rbi": 5, "hits": 4, "k_pitcher": 12},
        "BIG": {"hr": 2, "rbi": 4, "hits": 4, "k_pitcher": 10},
        "SOLID": {"hr": 1, "rbi": 3, "hits": 3, "k_pitcher": 8},
    },
}

# Impact tier → estimated card price change %
IMPACT_ESTIMATES = {
    "MONSTER": 10,
    "BIG": 5,
    "SOLID": 2,
    "QUIET": 0,
}


def evaluate_player_performance(player_name: str, sport: str, game_stats: dict) -> dict | None:
    """Check a player's game stats against thresholds.

    Returns {tier, impact_pct, headline, stats_summary} or None if below thresholds.
    """
    sport_thresholds = THRESHOLDS.get(sport)
    if not sport_thresholds:
        return None

    # Check tiers from highest to lowest
    for tier in ("MONSTER", "BIG", "SOLID"):
        tier_thresholds = sport_thresholds[tier]
        for stat, min_val in tier_thresholds.items():
            actual = game_stats.get(stat, 0)
            if actual >= min_val:
                impact_pct = IMPACT_ESTIMATES[tier]
                headline = _build_headline(player_name, stat, actual, tier, sport)
                return {
                    "tier": tier,
                    "impact_pct": impact_pct,
                    "headline": headline,
                    "stat_key": stat,
                    "stat_value": actual,
                }

    return None


def _build_headline(player_name: str, stat: str, value, tier: str, sport: str) -> str:
    """Generate an exciting headline for a big performance."""
    stat_labels = {
        "pts": "points", "reb": "rebounds", "ast": "assists",
        "stl": "steals", "blk": "blocks",
        "pass_yds": "passing yards", "pass_td": "passing TDs",
        "rush_yds": "rushing yards", "rush_td": "rushing TDs",
        "rec_yds": "receiving yards",
        "hr": "home runs", "rbi": "RBI", "hits": "hits",
        "k_pitcher": "strikeouts",
    }
    label = stat_labels.get(stat, stat)

    if tier == "MONSTER":
        return f"{player_name} just dropped {value} {label} — cards could spike!"
    elif tier == "BIG":
        return f"{player_name} going off with {value} {label} tonight"
    else:
        return f"{player_name} having a solid night — {value} {label}"


def evaluate_game_score(game: dict) -> dict | None:
    """MVP proxy: evaluate game based on score differential.

    Since ESPN free endpoints don't provide individual player stats reliably,
    use the score differential to estimate performance quality.
    """
    if game.get("status") not in ("In Progress", "Final"):
        return None

    home_score = game.get("home_score", 0)
    away_score = game.get("away_score", 0)

    if home_score == 0 and away_score == 0:
        return None

    diff = abs(home_score - away_score)
    total = home_score + away_score
    sport = game.get("sport", "NBA")

    # Determine tier based on point differential
    if sport == "NBA":
        if diff >= 25:
            tier = "MONSTER"
        elif diff >= 15:
            tier = "BIG"
        elif diff >= 8:
            tier = "SOLID"
        else:
            return None
    elif sport == "NFL":
        if diff >= 21:
            tier = "MONSTER"
        elif diff >= 14:
            tier = "BIG"
        elif diff >= 7:
            tier = "SOLID"
        else:
            return None
    elif sport == "MLB":
        if diff >= 6:
            tier = "MONSTER"
        elif diff >= 4:
            tier = "BIG"
        elif diff >= 2:
            tier = "SOLID"
        else:
            return None
    else:
        return None

    winner = game["home_team"] if home_score > away_score else game["away_team"]

    return {
        "tier": tier,
        "impact_pct": IMPACT_ESTIMATES[tier],
        "score_diff": diff,
        "total_score": total,
        "winning_team": winner,
    }


def get_active_game_alerts(portfolio: list[dict], games: list[dict]) -> list[dict]:
    """Generate game night alerts for owned players in active games."""
    from modules.live_games import match_players_to_games

    player_list = []
    for card in portfolio:
        player_list.append({
            "player_name": card["player_name"],
            "sport": card["sport"],
            "card_type": card.get("card_type", ""),
            "source": "Portfolio",
        })

    matched = match_players_to_games(player_list, games)
    alerts = []

    for m in matched:
        if not m["is_playing_today"] or not m.get("game"):
            continue

        game = m["game"]
        evaluation = evaluate_game_score(game)

        if evaluation:
            alerts.append({
                "player_name": m["player_name"],
                "sport": m.get("sport", ""),
                "team": m.get("team", ""),
                "game": game,
                "tier": evaluation["tier"],
                "impact_pct": evaluation["impact_pct"],
                "score_diff": evaluation["score_diff"],
                "winning_team": evaluation["winning_team"],
            })

    # Sort: MONSTER first, then BIG, then SOLID
    tier_order = {"MONSTER": 0, "BIG": 1, "SOLID": 2}
    alerts.sort(key=lambda a: tier_order.get(a["tier"], 3))
    return alerts


def compute_portfolio_impact(alerts: list[dict], market_values: dict) -> dict:
    """Estimate total portfolio impact from game night alerts.

    Args:
        alerts: List of alert dicts from get_active_game_alerts()
        market_values: Dict of card_id -> current market value
    """
    total_impact = 0
    player_impacts = []

    for alert in alerts:
        # Find cards owned for this player
        player_value = 0
        for card_id, value in market_values.items():
            # Simple approach: sum values for matching players
            player_value += value if isinstance(value, (int, float)) else 0

        est_change = round(player_value * (alert["impact_pct"] / 100), 2)
        total_impact += est_change

        player_impacts.append({
            "player_name": alert["player_name"],
            "tier": alert["tier"],
            "impact_pct": alert["impact_pct"],
            "est_value_change": est_change,
        })

    return {
        "total_impact": round(total_impact, 2),
        "player_impacts": player_impacts,
        "alert_count": len(alerts),
    }
