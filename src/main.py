import os
import pandas as pd
import traceback
from projections_collection import download_fantasypros_projections
from data_collection import (
    load_nflfastr_multi_years,
    calculate_team_pace
)
from transformation import calculate_fantasy_points, extract_player_availability
from weighting import injury_weight, team_context_weight
from ranking import rank_players, export_to_excel
from rapidfuzz import process, fuzz
import re

def map_fantasypros_to_pipeline(df):
    # Remove any blank header rows
    df = df[df['Player'].notnull() & (df['Player'].str.strip() != '')]
    # Determine position if not present
    if 'position' not in df.columns:
        if 'ATT' in df.columns and 'CMP' in df.columns:
            pos = 'QB'
        elif 'REC' in df.columns and 'YDS' in df.columns:
            pos = 'WR'  # Could be WR or RB, will check below
        else:
            pos = 'RB'  # Fallback
        df['position'] = pos
    # Map columns by position
    mapped_rows = []
    for _, row in df.iterrows():
        pos = row.get('position', '').strip().upper()
        # QB: Passing (ATT,CMP,YDS,TDS,INTS), Rushing (ATT,YDS,TDS), FL, FPTS
        if pos == 'QB':
            mapped = {
                'player_id': row['Player'],
                'team': row['Team'],
                'passing_yds': row['YDS'],  # 1st YDS (passing)
                'passing_tds': row['TDS'],  # 1st TDS (passing)
                'rushing_yds': row.iloc[8], # 2nd YDS (rushing)
                'rushing_tds': row.iloc[10],# 2nd TDS (rushing)
                'receptions': 0,
                'receiving_yds': 0,
                'receiving_tds': 0,
                'position': 'QB',
                'team': row['Team'],
            }
        # RB: Rushing (ATT,YDS,TDS), Receiving (REC,YDS,TDS), FL, FPTS
        elif pos == 'RB':
            mapped = {
                'player_id': row['Player'],
                'team': row['Team'],
                'rushing_yds': row['YDS'],  # 1st YDS (rushing)
                'rushing_tds': row['TDS'],  # 1st TDS (rushing)
                'receptions': row['REC'],   # 2nd REC (receiving)
                'receiving_yds': row.iloc[8], # 2nd YDS (receiving)
                'receiving_tds': row.iloc[10],# 2nd TDS (receiving)
                'passing_yds': 0,
                'passing_tds': 0,
                'position': 'RB',
                'team': row['Team'],
            }
        # WR/TE: Receiving (REC,YDS,TDS), Rushing (ATT,YDS,TDS), FL, FPTS
        else:  # WR or TE
            mapped = {
                'player_id': row['Player'],
                'team': row['Team'],
                'receptions': row['REC'],   # 1st REC (receiving)
                'receiving_yds': row['YDS'], # 1st YDS (receiving)
                'receiving_tds': row['TDS'], # 1st TDS (receiving)
                'rushing_yds': row.iloc[8], # 2nd YDS (rushing)
                'rushing_tds': row.iloc[10],# 2nd TDS (rushing)
                'passing_yds': 0,
                'passing_tds': 0,
                'position': pos,
                'team': row['Team'],
            }
        mapped_rows.append(mapped)
    mapped_df = pd.DataFrame(mapped_rows)
    # Fill missing stat columns with 0
    for stat in ['rushing_yds','rushing_tds','receptions','receiving_yds','receiving_tds','passing_yds','passing_tds']:
        if stat not in mapped_df.columns:
            mapped_df[stat] = 0
    for stat in ['team','position']:
        if stat not in mapped_df.columns:
            mapped_df[stat] = ''
    return mapped_df

def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', name)
    name = re.sub(r'[^a-z ]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def build_name_map(fantasypros_names, nflfastr_names, threshold=90):
    nflfastr_names_norm = [normalize_name(n) for n in nflfastr_names]
    name_map = {}
    for fp_name in fantasypros_names:
        fp_norm = normalize_name(fp_name)
        match, score, idx = process.extractOne(fp_norm, nflfastr_names_norm, scorer=fuzz.ratio)
        if score >= threshold:
            name_map[fp_name] = nflfastr_names[idx]
        else:
            name_map[fp_name] = None
    return name_map

def calculate_expected_games(nflfastr_df, props_df):
    if nflfastr_df.empty:
        return {}
    reg = nflfastr_df[nflfastr_df['season_type'] == 'REG']
    # Use fantasy_player_name if present, else melt rusher/receiver/passer columns
    if 'fantasy_player_name' in reg.columns:
        player_games = reg.groupby(['fantasy_player_name', 'season'])['game_id'].nunique().reset_index()
        avg_games = player_games.groupby('fantasy_player_name')['game_id'].mean().to_dict()
        nf_names = list(avg_games.keys())
    else:
        # Fallback: stack rusher/receiver/passer columns
        name_cols = [col for col in ['rusher_player_name', 'receiver_player_name', 'passer_player_name'] if col in reg.columns]
        melted = pd.melt(reg, id_vars=['game_id', 'season'], value_vars=name_cols, value_name='player_name')
        melted = melted.dropna(subset=['player_name'])
        player_games = melted.groupby(['player_name', 'season'])['game_id'].nunique().reset_index()
        avg_games = player_games.groupby('player_name')['game_id'].mean().to_dict()
        nf_names = list(avg_games.keys())
    fp_names = props_df['player_id'].unique().tolist()
    name_map = build_name_map(fp_names, nf_names, threshold=90)
    expected_games = {}
    for fp_name in fp_names:
        nf_name = name_map[fp_name]
        if nf_name and nf_name in avg_games:
            expected_games[fp_name] = avg_games[nf_name]
        else:
            expected_games[fp_name] = 17
    return expected_games

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
        print('[INFO] Downloading and loading last two years of nflfastR data...')
        nflfastr_df = load_nflfastr_multi_years(n=2)
        if nflfastr_df.empty:
            print('[ERROR] No nflfastR data loaded.')
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
        print('[INFO] Calculating expected games played for each player (fuzzy matching)...')
        avg_games_dict = calculate_expected_games(nflfastr_df, props_df)
        print('[INFO] Calculating fantasy points and applying weights...')
        results = []
        for idx, row in props_df.iterrows():
            player_id = row['player_id']
            team = row['team']
            position = row.get('position', 'RB')
            expected_games = avg_games_dict.get(player_id, 17)
            try:
                games_played, age, pos = expected_games, None, position
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
                inj_weight = games_played / 17.0
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
                'expected_games': games_played,
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