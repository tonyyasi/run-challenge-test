from datetime import datetime, timedelta
import json
import sys
import zoneinfo
import requests

SHARKS_TEAM_ID = 28


def main():
    # 1. Force date calculation to Pacific Time (San Jose local time)
    pacific_tz = zoneinfo.ZoneInfo("America/Los_Angeles")
    yesterday = (datetime.now(pacific_tz) - timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )

    print(
        f"[INFO] Running Sharks workout check for Pacific Date: {yesterday}",
        flush=True,
    )

    url = f"https://api-web.nhle.com/v1/score/{yesterday}"
    print(f"[INFO] Fetching schedule from API: {url}", flush=True)

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Failed to fetch schedule from NHL API: {e}", flush=True)
        sys.exit(1)

    games = res.json().get("games", [])
    print(
        f"[INFO] Retrieved {len(games)} game(s) from API for {yesterday}.",
        flush=True,
    )

    sharks_game = next(
        (
            g
            for g in games
            if g.get("homeTeam", {}).get("id") == SHARKS_TEAM_ID
            or g.get("awayTeam", {}).get("id") == SHARKS_TEAM_ID
        ),
        None,
    )

    if sharks_game:
        is_home = sharks_game["homeTeam"]["id"] == SHARKS_TEAM_ID
        team_data = (
            sharks_game["homeTeam"] if is_home else sharks_game["awayTeam"]
        )
        opp_data = (
            sharks_game["awayTeam"] if is_home else sharks_game["homeTeam"]
        )

        goals = team_data.get("score", 0)
        game_id = sharks_game["id"]

        print(
            f"[INFO] Sharks game found! ID: {game_id} | Sharks {goals} - {opp_data.get('score', 0)} {opp_data.get('commonName', {}).get('default', 'Opponent')}",
            flush=True,
        )

        # Fetch Play-by-Play details
        pbp_url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
        print(
            f"[INFO] Fetching play-by-play details from: {pbp_url}", flush=True
        )

        try:
            pbp_res = requests.get(pbp_url, timeout=10).json()
        except Exception as e:
            print(
                f"[WARNING] Could not fetch play-by-play stats: {e}", flush=True
            )
            pbp_res = {}

        pp_goals = 0
        player_goals = {}

        for play in pbp_res.get("plays", []):
            if (
                play.get("typeDescKey") == "goal"
                and play.get("details", {}).get("eventOwnerTeamId")
                == SHARKS_TEAM_ID
            ):
                sit = play.get("situationCode", "1000")
                if len(sit) >= 2 and sit[0] != sit[1]:
                    pp_goals += 1

                scorer = play.get("details", {}).get("scoringPlayerId")
                if scorer:
                    player_goals[scorer] = player_goals.get(scorer, 0) + 1

        hat_tricks = sum(1 for c in player_goals.values() if c >= 3)
        total_miles = (goals * 1.0) + (pp_goals * 0.25) + (hat_tricks * 2.0)
        played = True

        print(
            f"[INFO] Breakdown -> Goals: {goals}, PP Goals: {pp_goals}, Hat Tricks: {hat_tricks}",
            flush=True,
        )
        print(f"[INFO] Total target miles: {total_miles:.2f}", flush=True)

    else:
        print(
            f"[INFO] No Sharks game played on {yesterday}. Rest day!",
            flush=True,
        )
        goals = pp_goals = hat_tricks = total_miles = 0
        played = False

    workout_data = {
        "date": yesterday,
        "played": played,
        "goals": goals,
        "pp_goals": pp_goals,
        "hat_tricks": hat_tricks,
        "total_miles": round(total_miles, 2),
    }

    print("[INFO] Saving output to data.json...", flush=True)
    with open("data.json", "w") as f:
        json.dump(workout_data, f, indent=2)

    print("[SUCCESS] Process completed successfully.", flush=True)


if __name__ == "__main__":
    main()
