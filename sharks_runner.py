from datetime import date, timedelta
import requests

# San Jose Sharks NHL Team ID is 28 (SJS)
SHARKS_TEAM_ID = 28


def calculate_miles(game_data):
    goals = 0
    pp_goals = 0
    player_goals = {}

    # Extract goal detail from game play-by-play / score data
    # (NHL API v1 schedule/boxscore or gamecenter endpoints)
    linescore = game_data.get("linescore", {})
    home_team = linescore.get("teams", {}).get("home", {})
    away_team = linescore.get("teams", {}).get("away", {})

    # Determine if Sharks were home or away
    is_home = home_team.get("team", {}).get("id") == SHARKS_TEAM_ID
    sharks_goals_count = (
        home_team.get("goals", 0) if is_home else away_team.get("goals", 0)
    )

    # Simplified API fetch for boxscore play details
    # Parse scoring plays from the NHL Gamecenter API payload
    scoring_plays = game_data.get("scoringPlays", [])

    for play in scoring_plays:
        team_id = play.get("team", {}).get("id")
        if team_id == SHARKS_TEAM_ID:
            goals += 1
            # Check for Power Play goal flag
            if play.get("result", {}).get("strength", {}).get("code") == "PPG":
                pp_goals += 1

            # Count goal scorer for hat trick logic
            scorer_id = play.get("players", [{}])[0].get("player", {}).get("id")
            if scorer_id:
                player_goals[scorer_id] = player_goals.get(scorer_id, 0) + 1

    # Check for any hat tricks (3+ goals by a single player)
    hat_tricks = sum(1 for count in player_goals.values() if count >= 3)

    # Rule calculations
    miles_from_goals = goals * 1.0
    miles_from_pp = pp_goals * 0.25
    miles_from_hat_tricks = hat_tricks * 2.0

    total_miles = miles_from_goals + miles_from_pp + miles_from_hat_tricks

    return {
        "goals": goals,
        "pp_goals": pp_goals,
        "hat_tricks": hat_tricks,
        "total_miles": total_miles,
    }


def main():
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://api-web.nhle.com/v1/score/{yesterday}"

    response = requests.get(url)
    if response.status_code != 200:
        print("Failed to retrieve NHL schedule.")
        return

    data = response.json()
    games = data.get("games", [])

    sharks_game = None
    for game in games:
        if (
            game.get("homeTeam", {}).get("id") == SHARKS_TEAM_ID
            or game.get("awayTeam", {}).get("id") == SHARKS_TEAM_ID
        ):
            sharks_game = game
            break

    if not sharks_game:
        print(f"No Sharks game found for yesterday ({yesterday}). Rest day!")
        return

    # Extract goal counts directly from boxscore summary
    is_home = sharks_game["homeTeam"]["id"] == SHARKS_TEAM_ID
    team_data = sharks_game["homeTeam"] if is_home else sharks_game["awayTeam"]
    goals = team_data.get("score", 0)

    # Note: Detailed play breakdown (PP goals & Hat Tricks) can be retrieved via the game ID
    game_id = sharks_game["id"]
    pbp_url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
    pbp_res = requests.get(pbp_url).json()

    pp_goals = 0
    player_goals = {}

    for play in pbp_res.get("plays", []):
        if (
            play.get("typeDescKey") == "goal"
            and play.get("details", {}).get("eventOwnerTeamId")
            == SHARKS_TEAM_ID
        ):
            # Check PP goal status
            if play.get("situationCode", "1000")[0] != play.get(
                "situationCode", "1000"
            )[1]:  # standard advantage check
                pp_goals += 1

            scorer = play.get("details", {}).get("scoringPlayerId")
            if scorer:
                player_goals[scorer] = player_goals.get(scorer, 0) + 1

    hat_tricks = sum(1 for count in player_goals.values() if count >= 3)

    total_miles = (goals * 1.0) + (pp_goals * 0.25) + (hat_tricks * 2.0)

    msg = f"🦈 Sharks Game Workout for {yesterday}:\n"
    msg += f"- Goals: {goals} ({goals * 1.0} mi)\n"
    msg += f"- Power Play Goals: {pp_goals} ({pp_goals * 0.25} mi)\n"
    msg += f"- Hat Tricks: {hat_tricks} ({hat_tricks * 2.0} mi)\n"
    msg += f"🏃 Total Workout: {total_miles:.2f} Miles"

    print(msg)


if __name__ == "__main__":
    main()
