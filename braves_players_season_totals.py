import requests
import csv
from datetime import datetime
from collections import defaultdict

TEAM_ID = 144  # Atlanta Braves MLB ID

def ip_to_float(ip_str):
    # MLB IP string: "6.1" = 6 and 1/3 innings
    try:
        if ip_str and isinstance(ip_str, str) and '.' in ip_str:
            whole, frac = ip_str.split('.')
            return int(whole) + int(frac) / 3
        elif ip_str:
            return float(ip_str)
        else:
            return 0.0
    except Exception:
        return 0.0

def get_braves_game_ids(year=None):
    if year is None:
        year = datetime.now().year
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={TEAM_ID}&season={year}&gameType=R"
    resp = requests.get(url)
    data = resp.json()
    game_ids = []
    for date in data.get("dates", []):
        for game in date.get("games", []):
            if game.get("status", {}).get("detailedState") == "Final":
                game_ids.append(game["gamePk"])
    return game_ids

def fetch_braves_player_stats(game_id):
    boxscore_url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    data = requests.get(boxscore_url).json()
    braves_side = None
    for side in ['home', 'away']:
        if data['teams'][side]['team'].get('abbreviation') == 'ATL':
            braves_side = side
            break
    if not braves_side:
        print(f"Braves not found in game {game_id}!")
        return []
    team_stats = data['teams'][braves_side]
    players = team_stats.get('players', {})
    player_rows = []
    for pid, player in players.items():
        info = player['person']
        raw_order = player.get('battingOrder', '')
        order = int(raw_order) // 100 if raw_order and raw_order.isdigit() else ''
        pos = player.get('position', {}).get('abbreviation', '')
        bat = player.get('stats', {}).get('batting', {})
        pit = player.get('stats', {}).get('pitching', {})
        field = player.get('stats', {}).get('fielding', {})
        row = {
            "player_id": info.get("id", ""),
            "player_name": info.get("fullName", ""),
            "position": pos,
            "batting_order": order,
            "AB": bat.get("atBats", 0) or 0,
            "R": bat.get("runs", 0) or 0,
            "H": bat.get("hits", 0) or 0,
            "RBI": bat.get("rbi", 0) or 0,
            "BB": bat.get("baseOnBalls", 0) or 0,
            "SO": bat.get("strikeOuts", 0) or 0,
            "HR": bat.get("homeRuns", 0) or 0,
            "OPS": bat.get("ops", ""),
            "IP": pit.get("inningsPitched", ""),
            "H_pit": pit.get("hits", 0) or 0,
            "R_pit": pit.get("runs", 0) or 0,
            "ER": pit.get("earnedRuns", 0) or 0,
            "BB_pit": pit.get("baseOnBalls", 0) or 0,
            "SO_pit": pit.get("strikeOuts", 0) or 0,
            "HR_pit": pit.get("homeRuns", 0) or 0,
            "errors": field.get("errors", 0) or 0,
            "assists": field.get("assists", 0) or 0,
            "putOuts": field.get("putOuts", 0) or 0
        }
        player_rows.append(row)
    return player_rows

def aggregate_player_stats(all_player_rows):
    aggregated = defaultdict(lambda: defaultdict(int))
    names = {}
    positions = {}
    orders = {}
    total_ip_str = defaultdict(str)
    for row in all_player_rows:
        pid = row["player_id"]
        names[pid] = row["player_name"]
        positions[pid] = row["position"]
        orders[pid] = row["batting_order"]
        # Batting stats
        for key in ["AB", "R", "H", "RBI", "BB", "SO", "HR"]:
            aggregated[pid][key] += int(row.get(key, 0) or 0)
        # Pitching stats
        for key in ["H_pit", "R_pit", "ER", "BB_pit", "SO_pit", "HR_pit"]:
            aggregated[pid][key] += int(row.get(key, 0) or 0)
        # Save IP as a sum
        ip_val = ip_to_float(row.get("IP", ""))
        if ip_val > 0:
            aggregated[pid]["IP_float"] += ip_val
        # Defensive stats
        for key in ["errors", "assists", "putOuts"]:
            aggregated[pid][key] += int(row.get(key, 0) or 0)

    # Calculate ERA and WHIP
    output_rows = []
    for pid in aggregated:
        ip_float = aggregated[pid].get("IP_float", 0)
        er = aggregated[pid].get("ER", 0)
        bb_pit = aggregated[pid].get("BB_pit", 0)
        h_pit = aggregated[pid].get("H_pit", 0)
        era = ""
        whip = ""
        ip_str = ""
        if ip_float > 0:
            era = round(er / ip_float * 9, 2)
            whip = round((bb_pit + h_pit) / ip_float, 2)
            # Format IP as MLB notation: e.g., 6.2 = 6 2/3
            whole = int(ip_float)
            frac = ip_float - whole
            if frac:
                # Convert fraction to MLB notation (0.333... = .1, 0.666... = .2)
                if abs(frac - 1/3) < 0.01:
                    ip_str = f"{whole}.1"
                elif abs(frac - 2/3) < 0.01:
                    ip_str = f"{whole}.2"
                else:
                    ip_str = f"{ip_float:.2f}"
            else:
                ip_str = str(whole)
        else:
            ip_str = "0"
        output = {
            "player_id": pid,
            "player_name": names[pid],
            "position": positions[pid],
            "batting_order": orders[pid],
            "AB": aggregated[pid]["AB"],
            "R": aggregated[pid]["R"],
            "H": aggregated[pid]["H"],
            "RBI": aggregated[pid]["RBI"],
            "BB": aggregated[pid]["BB"],
            "SO": aggregated[pid]["SO"],
            "HR": aggregated[pid]["HR"],
            "IP": ip_str,
            "H_pit": aggregated[pid]["H_pit"],
            "R_pit": aggregated[pid]["R_pit"],
            "ER": aggregated[pid]["ER"],
            "BB_pit": aggregated[pid]["BB_pit"],
            "SO_pit": aggregated[pid]["SO_pit"],
            "HR_pit": aggregated[pid]["HR_pit"],
            "ERA": era,
            "WHIP": whip,
            "errors": aggregated[pid]["errors"],
            "assists": aggregated[pid]["assists"],
            "putOuts": aggregated[pid]["putOuts"]
        }
        output_rows.append(output)
    return output_rows

def save_aggregated_player_stats(player_rows, filename="braves_player_season_totals.csv"):
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            "player_id", "player_name", "position", "batting_order",
            "AB", "R", "H", "RBI", "BB", "SO", "HR",
            "IP", "H_pit", "R_pit", "ER", "BB_pit", "SO_pit", "HR_pit", "ERA", "WHIP",
            "errors", "assists", "putOuts"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in player_rows:
            writer.writerow(row)

def main(year=None):
    print("Fetching game IDs...")
    game_ids = get_braves_game_ids(year)
    all_player_rows = []
    for idx, game_id in enumerate(game_ids, 1):
        print(f"Processing game {idx}/{len(game_ids)}: {game_id}")
        player_rows = fetch_braves_player_stats(game_id)
        all_player_rows.extend(player_rows)
    print("Aggregating player stats...")
    aggregated = aggregate_player_stats(all_player_rows)
    print(f"Saving aggregated stats for {len(aggregated)} players.")
    save_aggregated_player_stats(aggregated)

if __name__ == "__main__":
    main()