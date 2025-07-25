import os
import pandas as pd
import traceback
from projections_collection import download_fantasypros_projections
from data_collection import (
    download_nflfastr_csv,
    load_nflfastr_data,
    calculate_team_pace
)
from transformation import calculate_fantasy_points, extract_player_availability
from weighting import injury_weight, team_context_weight
from ranking import rank_players, export_to_excel

def map_fantasypros_to_pipeline(df):
    # Map FantasyPros columns to pipeline stat fields
    col_map = {
        'Player': 'player_id',
        'Team': 'team',
        'Rush Yds': 'rushing_yds',
        'Rush TD': 'rushing_tds',
        'Rec': 'receptions',
        'Rec Yds': 'receiving_yds',
        'Rec TD': 'receiving_tds',
        'Pass Yds': 'passing_yds',
        'Pass TD': 'passing_tds',
        'position': 'position',
    }
    # Only keep columns that exist in the DataFrame
    mapped = {}
    for k, v in col_map.items():
        if k in df.columns:
            mapped[v] = df[k]
        else:
            mapped[v] = 0  # Fill missing columns with 0
    mapped_df = pd.DataFrame(mapped)
    # Fill missing stat columns with 0
    for stat in ['rushing_yds','rushing_tds','receptions','receiving_yds','receiving_tds','passing_yds','passing_tds']:
        if stat not in mapped_df.columns:
            mapped_df[stat] = 0
    # Fill missing team/position with empty string
    for stat in ['team','position']:
        if stat not in mapped_df.columns:
            mapped_df[stat] = ''
    return mapped_df

def main():
    try:
        print('[INFO] Downloading FantasyPros projections...')
        props_df_raw = download_fantasypros_projections()
        if props_df_raw.empty:
            print('[ERROR] No player projections found from FantasyPros.')
            return
        print(f'[INFO] Downloaded {len(props_df_raw)} player projections.')
        props_df = map_fantasypros_to_pipeline(props_df_raw)
        print(f'[INFO] Mapped projections to pipeline format: {len(props_df)} players.')
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
        league_avg_points = 22  # Placeholder, as we don't have implied points from FantasyPros
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