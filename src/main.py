import os
import pandas as pd
import traceback
from data_collection import (
    get_odds_api_props,
    get_odds_api_team_totals,
    download_nflfastr_csv,
    load_nflfastr_data,
    calculate_team_pace
)
from transformation import calculate_fantasy_points, extract_player_availability
from weighting import injury_weight, team_context_weight
from ranking import rank_players, export_to_excel

def parse_team_totals(odds_team_data):
    """
    Parse The Odds API response to get team implied points and win totals.
    Returns a DataFrame: team, implied_points, win_total
    """
    teams = {}
    for game in odds_team_data:
        home = game.get('home_team')
        away = [t for t in game.get('teams', []) if t != home][0] if game.get('teams') else None
        # Over/under (totals)
        total = None
        for market in game.get('bookmakers', [{}])[0].get('markets', []):
            if market.get('key') == 'totals':
                total = market.get('outcomes', [{}])[0].get('point')
        # Spread
        home_spread = None
        for market in game.get('bookmakers', [{}])[0].get('markets', []):
            if market.get('key') == 'spreads':
                for outcome in market.get('outcomes', []):
                    if outcome.get('name') == home:
                        home_spread = outcome.get('point')
        if home and away and total and home_spread is not None:
            home_points = (total / 2) - (home_spread / 2)
            away_points = (total / 2) + (home_spread / 2)
            teams[home] = teams.get(home, {'implied_points': 0, 'games': 0})
            teams[away] = teams.get(away, {'implied_points': 0, 'games': 0})
            teams[home]['implied_points'] += home_points
            teams[home]['games'] += 1
            teams[away]['implied_points'] += away_points
            teams[away]['games'] += 1
    # Average implied points per team
    team_rows = []
    for team, d in teams.items():
        team_rows.append({'team': team, 'implied_points': d['implied_points'] / d['games'] if d['games'] else 0})
    return pd.DataFrame(team_rows)

def parse_player_props(props_data):
    """
    Parse The Odds API player prop data into a DataFrame with columns:
    player_id, team, position, rushing_yds, rushing_tds, receptions, receiving_yds, receiving_tds, passing_yds, passing_tds
    """
    # Mapping from Odds API market key to our stat columns
    stat_map = {
        'rushing_yards': 'rushing_yds',
        'rushing_touchdowns': 'rushing_tds',
        'receptions': 'receptions',
        'receiving_yards': 'receiving_yds',
        'receiving_touchdowns': 'receiving_tds',
        'passing_yards': 'passing_yds',
        'passing_touchdowns': 'passing_tds',
    }
    # Build a dict: {(player, team): {stat: value, ...}}
    player_stats = {}
    for game in props_data:
        for bookmaker in game.get('bookmakers', []):
            for market in bookmaker.get('markets', []):
                stat_key = stat_map.get(market.get('key'))
                if not stat_key:
                    continue
                for outcome in market.get('outcomes', []):
                    player = outcome.get('description') or outcome.get('name')
                    team = outcome.get('team') or outcome.get('participant') or game.get('home_team')
                    if not player:
                        continue
                    key = (player, team)
                    if key not in player_stats:
                        player_stats[key] = {
                            'player_id': player,
                            'team': team,
                            'rushing_yds': 0,
                            'rushing_tds': 0,
                            'receptions': 0,
                            'receiving_yds': 0,
                            'receiving_tds': 0,
                            'passing_yds': 0,
                            'passing_tds': 0,
                        }
                    # Use the over/under line as the projection
                    player_stats[key][stat_key] = outcome.get('point', 0)
    # Convert to DataFrame
    df = pd.DataFrame(list(player_stats.values()))
    # Optionally, add position info (could be improved with a mapping or from nflfastR)
    df['position'] = 'RB'  # Default; can be improved
    return df

def main():
    try:
        api_key = os.getenv('ODDS_API_KEY')
        if not api_key:
            print('[ERROR] ODDS_API_KEY environment variable not set')
            return

        print('[INFO] Fetching player props from The Odds API...')
        try:
            props_data = get_odds_api_props(api_key)
        except Exception as e:
            print(f'[ERROR] Failed to fetch player props: {e}')
            traceback.print_exc()
            return
        props_df = parse_player_props(props_data)
        if props_df.empty:
            print('[ERROR] No player props found from The Odds API.')
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

        print('[INFO] Fetching team totals from The Odds API...')
        try:
            team_totals_data = get_odds_api_team_totals(api_key)
            team_totals_df = parse_team_totals(team_totals_data)
        except Exception as e:
            print(f'[ERROR] Failed to fetch or parse team totals: {e}')
            traceback.print_exc()
            return

        league_avg_points = team_totals_df['implied_points'].mean()
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
            team_row = team_totals_df[team_totals_df['team'] == team]
            implied_points = float(team_row['implied_points'].iloc[0]) if not team_row.empty else league_avg_points
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