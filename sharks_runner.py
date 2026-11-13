"""
San Jose Sharks Running Challenge - Automated Tracker
Fetches the Sharks schedule and game data from the NHL API, calculates
the mileage to run based on Sharks game results, and outputs data.json.

Math Rules:
- 1.0 mile per Sharks goal scored
- 0.25 miles when the opponent has a power play but does NOT score (killed penalty)
- 2.0 miles for each hat trick by a Sharks player
"""

from datetime import datetime, timedelta
import json
import os
import sys
import zoneinfo
import requests

SHARKS_TEAM_ID = 28
PACIFIC_TZ = zoneinfo.ZoneInfo("America/Los_Angeles")
BASE_URL = "https://api-web.nhle.com/v1"

def fetch_json(url, timeout=12):
    try:
        res = requests.get(url, timeout=timeout)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"[WARN] Failed to fetch {url}: {e}", flush=True)
        return None

def calculate_game_miles(game, cached_games_map):
    game_id = game["id"]
    game_state = game.get("gameState")
    is_final = game_state in ("FINAL", "OFF")

    is_home = game.get("homeTeam", {}).get("id") == SHARKS_TEAM_ID
    sjs_data = game["homeTeam"] if is_home else game["awayTeam"]
    opp_data = game["awayTeam"] if is_home else game["homeTeam"]

    opp_abbrev = opp_data.get("abbrev", "")
    opp_name = opp_data.get("commonName", {}).get("default") or opp_data.get("placeName", {}).get("default") or opp_abbrev
    opp_logo = opp_data.get("logo", "")
    sharks_logo = sjs_data.get("logo", "")

    game_obj = {
        "id": game_id,
        "date": game.get("gameDate"),
        "startTimeUTC": game.get("startTimeUTC"),
        "isHome": is_home,
        "oppAbbrev": opp_abbrev,
        "oppName": opp_name,
        "oppLogo": opp_logo,
        "sharksLogo": sharks_logo,
        "gameState": game_state,
        "gameScheduleState": game.get("gameScheduleState", "OK"),
    }

    if not is_final:
        return game_obj

    # If this game was already calculated and cached, we can reuse its detailed breakdown
    if game_id in cached_games_map and cached_games_map[game_id].get("totalMiles") is not None:
        cached = cached_games_map[game_id]
        # Preserve updated metadata while keeping calculation
        cached.update(game_obj)
        return cached

    sharks_score = int(sjs_data.get("score", 0))
    opp_score = int(opp_data.get("score", 0))
    game_obj["sharksScore"] = sharks_score
    game_obj["oppScore"] = opp_score
    game_obj["result"] = "W" if sharks_score > opp_score else "L"

    outcome_desc = game.get("gameOutcome", {}).get("lastPeriodType", "REG")
    game_obj["gameOutcome"] = outcome_desc

    # Fetch right-rail for team game stats (power play opportunities & goals)
    opp_empty_pp = 0
    opp_pp_goals = 0
    opp_pp_opps = 0

    rr_data = fetch_json(f"{BASE_URL}/gamecenter/{game_id}/right-rail")
    if rr_data and "teamGameStats" in rr_data:
        for stat in rr_data["teamGameStats"]:
            if stat.get("category") == "powerPlay":
                opp_pp_val = stat.get("awayValue") if is_home else stat.get("homeValue")
                if opp_pp_val and "/" in str(opp_pp_val):
                    try:
                        g_str, o_str = str(opp_pp_val).split("/")
                        opp_pp_goals = int(g_str)
                        opp_pp_opps = int(o_str)
                        opp_empty_pp = max(0, opp_pp_opps - opp_pp_goals)
                    except ValueError:
                        pass
                break

    # Fetch landing for goal scorers and hat tricks
    hat_tricks = 0
    hat_trick_players = []
    goal_scorers = []

    landing_data = fetch_json(f"{BASE_URL}/gamecenter/{game_id}/landing")
    if landing_data and "summary" in landing_data and "scoring" in landing_data["summary"]:
        player_counts = {}
        player_names = {}
        for period in landing_data["summary"]["scoring"]:
            p_num = period.get("periodDescriptor", {}).get("number", 1)
            for goal in period.get("goals", []):
                if goal.get("teamAbbrev", {}).get("default") == "SJS":
                    pid = str(goal.get("playerId", ""))
                    pname = goal.get("name", {}).get("default", "Unknown")
                    goal_scorers.append({
                        "name": pname,
                        "period": p_num,
                        "time": goal.get("timeInPeriod", ""),
                        "strength": goal.get("strength", "ev")
                    })
                    if pid:
                        player_counts[pid] = player_counts.get(pid, 0) + 1
                        player_names[pid] = pname

        for pid, count in player_counts.items():
            if count >= 3:
                hat_tricks += 1
                hat_trick_players.append(f"{player_names.get(pid, 'Player')} ({count})")

    # Math Calculation
    goals_miles = round(sharks_score * 1.0, 2)
    pp_miles = round(opp_empty_pp * 0.25, 2)
    hat_trick_miles = round(hat_tricks * 2.0, 2)
    total_miles = round(goals_miles + pp_miles + hat_trick_miles, 2)

    game_obj["goals"] = sharks_score
    game_obj["oppPPGoals"] = opp_pp_goals
    game_obj["oppPPOpps"] = opp_pp_opps
    game_obj["oppEmptyPP"] = opp_empty_pp
    game_obj["oppPPSummary"] = f"{opp_pp_goals}/{opp_pp_opps}"
    game_obj["hatTricks"] = hat_tricks
    game_obj["hatTrickPlayers"] = hat_trick_players
    game_obj["goalScorers"] = goal_scorers
    game_obj["milesBreakdown"] = {
        "goalsMiles": goals_miles,
        "ppMiles": pp_miles,
        "hatTrickMiles": hat_trick_miles,
        "totalMiles": total_miles
    }
    game_obj["totalMiles"] = total_miles

    return game_obj

def main():
    pacific_now = datetime.now(PACIFIC_TZ)
    yesterday = (pacific_now - timedelta(days=1)).strftime("%Y-%m-%d")
    today = pacific_now.strftime("%Y-%m-%d")

    print(f"[INFO] Running Sharks workout check. Pacific Date: Today={today}, Yesterday={yesterday}", flush=True)

    # Load existing cache if present to speed up execution
    cached_games_map = {}
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r") as f:
                old_data = json.load(f)
                for g in old_data.get("games", []):
                    if g.get("id") and g.get("totalMiles") is not None:
                        cached_games_map[g["id"]] = g
            print(f"[INFO] Loaded {len(cached_games_map)} cached game calculations.", flush=True)
        except Exception as e:
            print(f"[WARN] Could not parse existing data.json: {e}", flush=True)

    # Fetch season schedule for Sharks
    schedule_url = f"{BASE_URL}/club-schedule-season/SJS/now"
    schedule_data = fetch_json(schedule_url)
    if not schedule_data or "games" not in schedule_data:
        print("[ERROR] Failed to fetch Sharks schedule from NHL API.", flush=True)
        sys.exit(1)

    raw_games = schedule_data.get("games", [])
    print(f"[INFO] Found {len(raw_games)} games in Sharks schedule.", flush=True)

    processed_games = []
    total_season_miles = 0.0
    total_goals = 0
    total_empty_pp = 0
    total_hat_tricks = 0
    wins = 0
    losses = 0
    ot_losses = 0

    yesterday_game = None
    latest_completed_game = None
    next_game = None

    for raw_g in raw_games:
        game_obj = calculate_game_miles(raw_g, cached_games_map)
        processed_games.append(game_obj)

        if game_obj.get("gameState") in ("FINAL", "OFF") and game_obj.get("totalMiles") is not None:
            miles = float(game_obj["totalMiles"])
            total_season_miles += miles
            total_goals += int(game_obj.get("goals", 0))
            total_empty_pp += int(game_obj.get("oppEmptyPP", 0))
            total_hat_tricks += int(game_obj.get("hatTricks", 0))

            if game_obj.get("result") == "W":
                wins += 1
            else:
                if game_obj.get("gameOutcome") in ("OT", "SO"):
                    ot_losses += 1
                else:
                    losses += 1

            latest_completed_game = game_obj
        else:
            if next_game is None:
                next_game = game_obj

        if game_obj.get("date") == yesterday:
            yesterday_game = game_obj

    total_completed = wins + losses + ot_losses
    avg_miles = round(total_season_miles / total_completed, 2) if total_completed > 0 else 0.0

    # Build backward-compatible top-level keys for yesterday's workout
    if yesterday_game and yesterday_game.get("gameState") in ("FINAL", "OFF"):
        played = True
        sharks_score = yesterday_game.get("sharksScore", 0)
        opp_score = yesterday_game.get("oppScore", 0)
        opp_name = yesterday_game.get("oppAbbrev", "")
        goals = yesterday_game.get("goals", 0)
        opp_empty_pp = yesterday_game.get("oppEmptyPP", 0)
        hat_tricks = yesterday_game.get("hatTricks", 0)
        total_miles = yesterday_game.get("totalMiles", 0.0)
    else:
        played = False
        sharks_score = opp_score = goals = opp_empty_pp = hat_tricks = 0
        opp_name = ""
        total_miles = 0.0

    output_data = {
        # Backward-compatible fields
        "date": yesterday,
        "played": played,
        "sharks_score": sharks_score,
        "opp_score": opp_score,
        "opp_name": opp_name,
        "goals": goals,
        "pp_goals": opp_empty_pp,  # Kept for backward compatibility with older UI
        "opp_empty_pp": opp_empty_pp,
        "hat_tricks": hat_tricks,
        "total_miles": round(total_miles, 2),

        # Enriched fields
        "last_updated": pacific_now.isoformat(),
        "today_date": today,
        "yesterday_game": yesterday_game,
        "latest_completed_game": latest_completed_game,
        "next_game": next_game,
        "season_summary": {
            "total_miles": round(total_season_miles, 2),
            "games_played": total_completed,
            "record": f"{wins}-{losses}-{ot_losses}",
            "wins": wins,
            "losses": losses,
            "ot_losses": ot_losses,
            "total_goals": total_goals,
            "total_empty_pp": total_empty_pp,
            "total_hat_tricks": total_hat_tricks,
            "avg_miles_per_game": avg_miles
        },
        "games": processed_games
    }

    print(f"[INFO] Season total miles: {round(total_season_miles, 2)} across {total_completed} games.", flush=True)
    print(f"[INFO] Writing enriched data to data.json and data.js...", flush=True)
    with open("data.json", "w") as f:
        json.dump(output_data, f, indent=2)

    with open("data.js", "w") as f:
        f.write("window.SHARKS_DATA = ")
        json.dump(output_data, f, indent=2)
        f.write(";\n")

    print("[SUCCESS] data.json and data.js updated successfully.", flush=True)

if __name__ == "__main__":
    main()
