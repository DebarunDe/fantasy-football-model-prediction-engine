import os
import pandas as pd
import traceback
from data_collection import (
    get_nfl_events,
    get_event_player_props,
    download_nflfastr_csv,
    load_nflfastr_data,
    calculate_team_pace
)
from transformation import calculate_fantasy_points, extract_player_availability
from weighting import injury_weight, team_context_weight
from ranking import rank_players, export_to_excel

def parse_sportsbookapi_player_props(events_data, api_key):
    # For each event, fetch player props and parse them
    all_props = []
    for event in events_data.get('events', []):
        event_id = event.get('eventID')
        home_team = event.get('homeTeam', {}).get('name')
        away_team = event.get('awayTeam', {}).get('name')
        try:
            props_data = get_event_player_props(event_id, api_key)
        except Exception as e:
            print(f'[WARN] Could not fetch props for event {event_id}: {e}')
            continue
        for prop in props_data.get('props', []):
            # Only include player props (filter out team/game props)
            if prop.get('type') != 'player':
                continue
            for outcome in prop.get('outcomes', []):
                player = outcome.get('player', {}).get('name')
                team = outcome.get('team', {}).get('name')
                stat_type = prop.get('name', '').lower()
                value = outcome.get('line')
                # Map stat_type to our columns
                stat_map = {
                    'rushing yards': 'rushing_yds',
                    'rushing touchdowns': 'rushing_tds',
                    'receptions': 'receptions',
                    'receiving yards': 'receiving_yds',
                    'receiving touchdowns': 'receiving_tds',
                    'passing yards': 'passing_yds',
                    'passing touchdowns': 'passing_tds',
                }
                mapped_stat = stat_map.get(stat_type)
                if not mapped_stat or player is None:
                    continue
                # Find or create player row
                match = next((p for p in all_props if p['player_id'] == player and p['team'] == team), None)
                if not match:
                    match = {
                        'player_id': player,
                        'team': team,
                        'rushing_yds': 0,
                        'rushing_tds': 0,
                        'receptions': 0,
                        'receiving_yds': 0,
                        'receiving_tds': 0,
                        'passing_yds': 0,
                        'passing_tds': 0,
                        'position': 'RB',  # Default, can be improved
                    }
                    all_props.append(match)
                match[mapped_stat] = value
    return pd.DataFrame(all_props)

def main():
    try:
        api_key = os.getenv('SPORTSBOOKAPI_KEY')
        if not api_key:
            print('[ERROR] SPORTSBOOKAPI_KEY environment variable not set')
            return
        print('[INFO] Fetching NFL events from SportsbookAPI...')
        try:
            events_data = get_nfl_events(api_key)
        except Exception as e:
            print(f'[ERROR] Failed to fetch NFL events: {e}')
            traceback.print_exc()
            return
        print(f'[INFO] Found {len(events_data.get("events", []))} NFL events.')
        print('[INFO] Fetching player props for all events (may take a while)...')
        props_df = parse_sportsbookapi_player_props(events_data, api_key)
        if props_df.empty:
            print('[ERROR] No player props found from SportsbookAPI.')
            return
        print(f'[INFO] Parsed {len(props_df)} player props.')
        print('[INFO] Downloading nflfastR data...')
        try:
            csv_path = download_nflfastr_csv(season=2023)
            nflfastr_df = load_nflfastr_data(csv_path)
        except Exception as e:
            print(f'[ERROR] Failed to download or load nflfastR data: {e}')
            traceback.print_exc()
            return
        try:
            team_pace_df = calculate_team_pace(nflfastr_df)
        except Exception as e:
            print(f'[ERROR] Failed to calculate team pace: {e}')
            traceback.print_exc()
            return
        league_avg_points = 22  # Placeholder, as we don't have implied points from SportsbookAPI
        league_avg_wins = 9
        league_avg_plays = team_pace_df['plays_per_game'].mean()
        print(f'[INFO] League averages - Points: {league_avg_points:.2f}, Wins: {league_avg_wins}, Plays: {league_avg_plays:.2f}')
        print('[INFO] Calculating fantasy points and applying weights...')
        results = []
        for idx, row in props_df.iterrows():
            player_id = row['player_id']
            team = row['team']
            position = row.get('position', 'RB')
            try:
                games_played, age, pos = extract_player_availability(nflfastr_df, player_id)
            except Exception as e:
                print(f'[WARN] Could not extract availability for {player_id}: {e}')
                games_played, age, pos = 17, None, position
            implied_points = league_avg_points  # Placeholder
            win_total = league_avg_wins
            pace_row = team_pace_df[team_pace_df['team'] == team]
            pace = float(pace_row['plays_per_game'].iloc[0]) if not pace_row.empty else league_avg_plays
            try:
                raw_points = calculate_fantasy_points(row)
            except Exception as e:
                print(f'[WARN] Could not calculate fantasy points for {player_id}: {e}')
                raw_points = 0
            try:
                inj_weight = injury_weight(games_played, age, pos)
            except Exception as e:
                print(f'[WARN] Could not calculate injury weight for {player_id}: {e}')
                inj_weight = 1.0
            try:
                team_weight = team_context_weight(
                    implied_points, league_avg_points, win_total, league_avg_wins, pace, league_avg_plays, position
                )
            except Exception as e:
                print(f'[WARN] Could not calculate team context weight for {player_id}: {e}')
                team_weight = 1.0
            weighted_points = raw_points * inj_weight * team_weight
            results.append({
                **row,
                'games_played': games_played,
                'age': age,
                'position': pos,
                'raw_fantasy_points': raw_points,
                'injury_weight': inj_weight,
                'team_weight': team_weight,
                'weighted_fantasy_points': weighted_points,
                'implied_points': implied_points,
                'pace': pace,
            })
        results_df = pd.DataFrame(results)
        print(f'[INFO] Ranking {len(results_df)} players and exporting to Excel...')
        try:
            ranked_df = rank_players(results_df)
            export_to_excel(ranked_df)
        except Exception as e:
            print(f'[ERROR] Failed to rank or export: {e}')
            traceback.print_exc()
            return
        print('[SUCCESS] Big board exported to fantasy_big_board.xlsx')
    except Exception as e:
        print(f'[FATAL ERROR] Pipeline failed: {e}')
        traceback.print_exc()

if __name__ == '__main__':
    main() 