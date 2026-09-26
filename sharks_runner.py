from datetime import date, timedelta
import json
import requests

SHARKS_TEAM_ID = 28


def main():
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://api-web.nhle.com/v1/score/{yesterday}"

    res = requests.get(url)
    if res.status_code != 200:
        return

    games = res.json().get("games", [])
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
        goals = team_data.get("score", 0)

        game_id = sharks_game["id"]
        pbp_res = requests.get(
            f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
        ).json()

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
    else:
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

    # Save data for web page usage
    with open("data.json", "w") as f:
        json.dump(workout_data, f, indent=2)


if __name__ == "__main__":
    main()
