from datetime import datetime, timedelta
import json
import sys
import zoneinfo
import requests

SHARKS_TEAM_ID = 28

def main():
    pacific_tz = zoneinfo.ZoneInfo("America/Los_Angeles")
    yesterday = (datetime.now(pacific_tz) - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"[INFO] Running Sharks workout check for Pacific Date: {yesterday}", flush=True)
    url = f"https://api-web.nhle.com/v1/score/{yesterday}"

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Failed to fetch schedule from NHL API: {e}", flush=True)
        sys.exit(1)

    games = res.json().get("games", [])
    sharks_game = next(
        (g for g in games if g.get("homeTeam", {}).get("id") == SHARKS_TEAM_ID or g.get("awayTeam", {}).get("id") == SHARKS_TEAM_ID),
        None
    )

    if sharks_game:
        is_home = sharks_game["homeTeam"]["id"] == SHARKS_TEAM_ID
        team_data = sharks_game["homeTeam"] if is_home else sharks_game["awayTeam"]
        opp_data = sharks_game["awayTeam"] if is_home else sharks_game["homeTeam"]

        goals = team_data.get("score", 0)
        opp_score = opp_data.get("score", 0)
        opp_name = opp_data.get("abbrev", opp_data.get("commonName", {}).get("default", "OPP"))
        game_id = sharks_game["id"]

        try:
            pbp_res = requests.get(f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play", timeout=10).json()
        except:
            pbp_res = {}

        pp_goals = 0
        player_goals = {}

        for play in pbp_res.get("plays", []):
            if play.get("typeDescKey") == "goal" and play.get("details", {}).get("eventOwnerTeamId") == SHARKS_TEAM_ID:
                
                # Corrected Power Play Logic
                # situationCode format: [AwayGoalie][AwaySkaters][HomeSkaters][HomeGoalie]
                sit = play.get("situationCode", "1551")
                if len(sit) == 4:
                    try:
                        away_skaters = int(sit[1])
                        home_skaters = int(sit[2])
                        
                        # Check if Sharks had a man advantage
                        if is_home and home_skaters > away_skaters:
                            pp_goals += 1
                        elif not is_home and away_skaters > home_skaters:
                            pp_goals += 1
                    except ValueError:
                        pass

                scorer = play.get("details", {}).get("scoringPlayerId")
                if scorer:
                    player_goals[scorer] = player_goals.get(scorer, 0) + 1

        hat_tricks = sum(1 for c in player_goals.values() if c >= 3)
        total_miles = (goals * 1.0) + (pp_goals * 0.25) + (hat_tricks * 2.0)
        played = True

    else:
        goals = pp_goals = hat_tricks = total_miles = opp_score = 0
        opp_name = ""
        played = False

    workout_data = {
        "date": yesterday,
        "played": played,
        "sharks_score": goals,
        "opp_score": opp_score,
        "opp_name": opp_name,
        "goals": goals,
        "pp_goals": pp_goals,
        "hat_tricks": hat_tricks,
        "total_miles": round(total_miles, 2),
    }

    print("[INFO] Saving output to data.json...", flush=True)
    with open("data.json", "w") as f:
        json.dump(workout_data, f, indent=2)

if __name__ == "__main__":
    main()
