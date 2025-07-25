import os
import pandas as pd
import traceback
from data_collection import (
    get_nfl_season_key,
    get_nfl_events_v0,
    get_event_markets_v0,
    get_market_outcomes_v0,
    download_nflfastr_csv,
    load_nflfastr_data,
    calculate_team_pace
)
from transformation import calculate_fantasy_points, extract_player_availability
from weighting import injury_weight, team_context_weight
from ranking import rank_players, export_to_excel

def parse_sportsbookapi_v0_player_props(events_data, api_key):
    # For each event, fetch markets and outcomes, parse player props
    all_props = []
    for event in events_data:
        event_key = event.get('key')
        home_team = event.get('homeParticipant', {}).get('name')
        away_team = event.get('awayParticipant', {}).get('name')
        try:
            markets = get_event_markets_v0(event_key, api_key)
        except Exception as e:
            print(f'[WARN] Could not fetch markets for event {event_key}: {e}')
            continue
        for market in markets:
            market_name = market.get('name', '').lower()
            # Only include player prop markets
            if not any(x in market_name for x in ['passing yards', 'rushing yards', 'receiving yards', 'receptions', 'touchdowns']):
                continue
            try:
                outcomes = get_market_outcomes_v0(market['key'], api_key)
            except Exception as e:
                print(f'[WARN] Could not fetch outcomes for market {market["key"]}: {e}')
                continue
            for outcome in outcomes:
                player = outcome.get('participant', {}).get('name')
                team = outcome.get('participant', {}).get('team', {}).get('name')
                stat_type = market.get('name', '').lower()
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
                mapped_stat = None
                for k, v in stat_map.items():
                    if k in stat_type:
                        mapped_stat = v
                        break
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
        print('[INFO] Fetching NFL season key from SportsbookAPI...')
        try:
            competition_key = get_nfl_season_key(api_key)
        except Exception as e:
            print(f'[ERROR] Failed to fetch NFL season key: {e}')
            traceback.print_exc()
            return
        print(f'[INFO] NFL season key: {competition_key}')
        print('[INFO] Fetching NFL events from SportsbookAPI...')
        try:
            events_data = get_nfl_events_v0(competition_key, api_key)
        except Exception as e:
            print(f'[ERROR] Failed to fetch NFL events: {e}')
            traceback.print_exc()
            return
        print(f'[INFO] Found {len(events_data)} NFL events.')
        print('[INFO] Fetching player props for all events (may take a while)...')
        props_df = parse_sportsbookapi_v0_player_props(events_data, api_key)
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