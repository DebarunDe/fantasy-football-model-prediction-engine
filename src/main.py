import os
import pandas as pd
import traceback
from projections_collection import download_fantasypros_projections
from data_collection import (
    load_nflfastr_multi_years,
    calculate_team_pace
)
from transformation import calculate_fantasy_points
from weighting import injury_weight, team_context_weight
from ranking import rank_players, export_to_excel
from individual_optimizer import calculate_unified_big_board_score, analyze_unified_big_board_insights
from rapidfuzz import process, fuzz
import re
from vbd_optimizer import calculate_replacement_baselines, calculate_vor

def map_fantasypros_to_pipeline(df):
    # Data is already cleaned in projections_collection.py
    mapped_rows = []
    for _, row in df.iterrows():
        # Use the position column that was already set in projections_collection.py
        pos = row.get('position', '').strip().upper()
        # Map columns by position
        if pos == 'QB':
            mapped = {
                'player_id': row['Player'],
                'team': row['Team'],
                'passing_yds': row['YDS'],  # Passing YDS
                'passing_tds': row['TDS'],  # Passing TDS
                'rushing_yds': row['YDS.1'], # Rushing YDS
                'rushing_tds': row['TDS.1'],# Rushing TDS
                'receptions': 0,
                'receiving_yds': 0,
                'receiving_tds': 0,
                'position': 'QB',
                'team': row['Team'],
            }
        elif pos == 'RB':
            mapped = {
                'player_id': row['Player'],
                'team': row['Team'],
                'rushing_yds': row['YDS'],  # Rushing YDS
                'rushing_tds': row['TDS'],  # Rushing TDS
                'receptions': row['REC'],   # Receiving REC
                'receiving_yds': row['YDS.1'], # Receiving YDS
                'receiving_tds': row['TDS.1'],# Receiving TDS
                'passing_yds': 0,
                'passing_tds': 0,
                'position': 'RB',
                'team': row['Team'],
            }
        elif pos == 'WR':
            mapped = {
                'player_id': row['Player'],
                'team': row['Team'],
                'receptions': row['REC'],   # Receiving REC
                'receiving_yds': row['YDS'], # Receiving YDS
                'receiving_tds': row['TDS'], # Receiving TDS
                'rushing_yds': row['YDS.1'], # Rushing YDS
                'rushing_tds': row['TDS.1'],# Rushing TDS
                'passing_yds': 0,
                'passing_tds': 0,
                'position': 'WR',
                'team': row['Team'],
            }
        elif pos == 'TE':
            mapped = {
                'player_id': row['Player'],
                'team': row['Team'],
                'receptions': row['REC'],   # Receiving REC
                'receiving_yds': row['YDS'], # Receiving YDS
                'receiving_tds': row['TDS'], # Receiving TDS
                'rushing_yds': 0,
                'rushing_tds': 0,
                'passing_yds': 0,
                'passing_tds': 0,
                'position': 'TE',
                'team': row['Team'],
            }
        else:
            mapped = {
                'player_id': row['Player'],
                'team': row['Team'],
                'receptions': 0,
                'receiving_yds': 0,
                'receiving_tds': 0,
                'rushing_yds': 0,
                'rushing_tds': 0,
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
    # Ensure all stat columns are numeric
    for stat in ['rushing_yds','rushing_tds','receptions','receiving_yds','receiving_tds','passing_yds','passing_tds']:
        mapped_df[stat] = pd.to_numeric(mapped_df[stat].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
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

if __name__ == '__main__':
    import sys
    import pandas as pd
    import datetime
    # Default to next NFL season if no year is provided
    current_year = datetime.datetime.now().year
    league_size = 12  # Default league size
    # Parse command-line arguments
    year = None
    for arg in sys.argv[1:]:
        if arg.isdigit() and int(arg) > 2000:
            year = arg
        elif arg.isdigit():
            league_size = int(arg)
    if not year:
        year = str(current_year + 1)
        print(f'[INFO] No year provided. Defaulting to {year}.')
    print(f'[INFO] Using league size: {league_size} teams')
    # Load projections for the given year
    props_df_raw = download_fantasypros_projections()
    props_df = map_fantasypros_to_pipeline(props_df_raw)
    # Determine if year is in the future (no nflfastR data available)
    if int(year) > current_year:
        print(f"[INFO] {year} is in the future. Skipping nflfastR data and running projections only.")
        results = []
        for _, row in props_df.iterrows():
            player_id = row['player_id']
            team = row['team']
            position = row.get('position', 'RB')
            expected_games = 17
            try:
                raw_points = calculate_fantasy_points(row)
            except Exception as e:
                raw_points = 0
            inj_weight = 1.0
            team_weight = 1.0
            weighted_points = raw_points
            results.append({
                **row,
                'expected_games': expected_games,
                'position': position,
                'raw_fantasy_points': raw_points,
                'injury_weight': inj_weight,
                'team_weight': team_weight,
                'weighted_fantasy_points': weighted_points,
                'implied_points': 0,
                'pace': 0,
            })
        results_df = pd.DataFrame(results)
        from individual_optimizer import calculate_advanced_statistical_metrics, calculate_risk_adjusted_value, calculate_bayesian_adjustments, calculate_consistency_metrics, calculate_unified_big_board_score
        from vbd_optimizer import calculate_replacement_baselines, calculate_vor, calculate_opportunity_cost, calculate_optimal_value
        from ranking import export_to_excel
        # --- VOR/Scarcity Integration ---
        baselines = calculate_replacement_baselines(results_df, league_size=league_size)
        df_vor = calculate_vor(results_df, baselines)
        df_oc = calculate_opportunity_cost(df_vor)
        df_optimal = calculate_optimal_value(df_oc)
        # Add VOR/scarcity columns to results_df for unified big board
        results_df = results_df.merge(df_optimal[['player_id','vor','optimal_value']], on='player_id', how='left')
        results_df['vor_final'] = results_df['vor']
        # --- End VOR/Scarcity Integration ---
        df = calculate_advanced_statistical_metrics(results_df)
        df = calculate_risk_adjusted_value(df)
        df = calculate_bayesian_adjustments(df)
        df = calculate_consistency_metrics(df)
        unified_df = calculate_unified_big_board_score(df)
        export_to_excel(unified_df, filename='fantasy_big_board.xlsx', league_size=league_size)
        print('\nTop 20 Players for', year)
        print(unified_df[['player_id','position','unified_big_board_score']].head(20))
        sys.exit(0)
    else:
        try:
            print('[INFO] Downloading and loading last two years of nflfastR data...')
            nflfastr_df = load_nflfastr_multi_years(n=2)
            if nflfastr_df.empty:
                print('[ERROR] No nflfastR data loaded.')
                sys.exit(1)
            team_pace_df = calculate_team_pace(nflfastr_df)
            league_avg_points = 22
            league_avg_wins = 9
            league_avg_plays = team_pace_df['plays_per_game'].mean()
            print(f'[INFO] League averages - Points: {league_avg_points:.2f}, Wins: {league_avg_wins}, Plays: {league_avg_plays:.2f}')
            avg_games_dict = calculate_expected_games(nflfastr_df, props_df)
            results = []
            for _, row in props_df.iterrows():
                player_id = row['player_id']
                team = row['team']
                position = row.get('position', 'RB')
                expected_games = 17
                try:
                    raw_points = calculate_fantasy_points(row)
                except Exception as e:
                    raw_points = 0
                inj_weight = 1.0
                team_weight = 1.0
                weighted_points = raw_points
                results.append({
                    **row,
                    'expected_games': expected_games,
                    'position': position,
                    'raw_fantasy_points': raw_points,
                    'injury_weight': inj_weight,
                    'team_weight': team_weight,
                    'weighted_fantasy_points': weighted_points,
                    'implied_points': 0,
                    'pace': 0,
                })
            results_df = pd.DataFrame(results)
            from individual_optimizer import calculate_advanced_statistical_metrics, calculate_risk_adjusted_value, calculate_bayesian_adjustments, calculate_consistency_metrics, calculate_unified_big_board_score
            from vbd_optimizer import calculate_replacement_baselines, calculate_vor, calculate_opportunity_cost, calculate_optimal_value
            from ranking import export_to_excel
            # --- VOR/Scarcity Integration ---
            baselines = calculate_replacement_baselines(results_df, league_size=league_size)
            df_vor = calculate_vor(results_df, baselines)
            df_oc = calculate_opportunity_cost(df_vor)
            df_optimal = calculate_optimal_value(df_oc)
            # Add VOR/scarcity columns to results_df for unified big board
            results_df = results_df.merge(df_optimal[['player_id','vor','optimal_value']], on='player_id', how='left')
            results_df['vor_final'] = results_df['vor']
            # --- End VOR/Scarcity Integration ---
            df = calculate_advanced_statistical_metrics(results_df)
            df = calculate_risk_adjusted_value(df)
            df = calculate_bayesian_adjustments(df)
            df = calculate_consistency_metrics(df)
            unified_df = calculate_unified_big_board_score(df)
            export_to_excel(unified_df, filename='fantasy_big_board.xlsx', league_size=league_size)
            print('\nTop 20 Players for', year)
            print(unified_df[['player_id','position','unified_big_board_score']].head(20))
        except Exception as e:
            print(f'[FATAL ERROR] Pipeline failed: {e}')
            import traceback
            traceback.print_exc() 