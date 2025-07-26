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
from trend_analyzer import calculate_performance_trends, apply_trend_analysis_to_big_board, analyze_trend_insights
from monte_carlo_analyzer import calculate_monte_carlo_distributions, calculate_monte_carlo_rankings, analyze_monte_carlo_insights
from advanced_efficiency_analyzer import calculate_advanced_efficiency_metrics, apply_efficiency_weights_to_projections, analyze_efficiency_insights
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
        for _, row in props_df.iterrows():
            player_id = row['player_id']
            team = row['team']
            position = row.get('position', 'RB')
            expected_games = 17
            try:
                raw_points = calculate_fantasy_points(row)
            except Exception as e:
                print(f'[WARN] Could not calculate fantasy points for {player_id}: {e}')
                raw_points = 0
            inj_weight = 1.0 # Baseline: no injury weighting
            team_weight = 1.0 # Baseline: no team context weighting
            weighted_points = raw_points # No weighting
            results.append({
                **row,
                'expected_games': expected_games,
                'position': position,
                'raw_fantasy_points': raw_points,
                'injury_weight': inj_weight, # This will be used in individual_optimizer for minor adjustment
                'team_weight': team_weight,
                'weighted_fantasy_points': weighted_points,
                'implied_points': 0,
                'pace': 0,
            })
        results_df = pd.DataFrame(results)

        print('[INFO] Calculating advanced efficiency metrics from nflfastR data...')
        try:
            # Calculate advanced efficiency metrics
            efficiency_df = calculate_advanced_efficiency_metrics(nflfastr_df, results_df)
            
            # Apply efficiency weights to projections
            results_df_with_efficiency = apply_efficiency_weights_to_projections(results_df, efficiency_df)
            
            # Generate efficiency insights
            analyze_efficiency_insights(results_df_with_efficiency)
            
        except Exception as e:
            print(f'[ERROR] Failed to calculate efficiency metrics: {e}')
            traceback.print_exc()
            # Continue without efficiency analysis
            results_df_with_efficiency = results_df

        print('[INFO] Analyzing performance trends and momentum...')
        try:
            # Calculate performance trends for each player
            player_trends = calculate_performance_trends(nflfastr_df, results_df)
            
            # Apply trend analysis to the big board
            results_df_with_trends = apply_trend_analysis_to_big_board(results_df_with_efficiency, player_trends)
            
            # Generate trend insights
            analyze_trend_insights(results_df_with_trends)
            
        except Exception as e:
            print(f'[ERROR] Failed to analyze trends: {e}')
            traceback.print_exc()
            # Continue without trend analysis
            results_df_with_trends = results_df_with_efficiency
        
        print('[INFO] Generating Monte Carlo distributions...')
        try:
            # Generate Monte Carlo distributions
            results_df_with_mc = calculate_monte_carlo_distributions(results_df_with_trends)
            
            # Calculate Monte Carlo rankings
            results_df_with_mc = calculate_monte_carlo_rankings(results_df_with_mc)
            
            # Generate Monte Carlo insights
            analyze_monte_carlo_insights(results_df_with_mc)
            
        except Exception as e:
            print(f'[ERROR] Failed to generate Monte Carlo distributions: {e}')
            traceback.print_exc()
            # Continue without Monte Carlo analysis
            results_df_with_mc = results_df_with_trends
        
        # === VBD & Scarcity Integration ===
        print('[INFO] Calculating Value Over Replacement (VOR) and applying position scarcity adjustments...')
        try:
            baselines = calculate_replacement_baselines(results_df_with_mc)
            results_df_with_vor = calculate_vor(results_df_with_mc, baselines)
            # Position scarcity adjustment
            scarcity_factors = {'QB': 1.00, 'RB': 1.05, 'WR': 1.02, 'TE': 1.08}
            results_df_with_vor['scarcity_factor'] = results_df_with_vor['position'].map(scarcity_factors).fillna(1.0)
            results_df_with_vor['vor_scarcity_adjusted'] = results_df_with_vor['vor'] * results_df_with_vor['scarcity_factor']
            # Placeholder for SOS adjustment (set to 1.0 for now)
            results_df_with_vor['sos_factor'] = 1.0
            results_df_with_vor['vor_final'] = results_df_with_vor['vor_scarcity_adjusted'] * results_df_with_vor['sos_factor']
        except Exception as e:
            print(f'[ERROR] Failed to calculate VOR/scarcity: {e}')
            traceback.print_exc()
            results_df_with_vor = results_df_with_mc
        
        print('[INFO] Creating unified big board with individual optimizations, trends, Monte Carlo analysis, and VBD/scarcity...')
        try:
            # Apply unified big board optimization (now includes trend, Monte Carlo, VBD, and scarcity data)
            unified_df = calculate_unified_big_board_score(results_df_with_vor)
            # Generate unified big board insights
            analyze_unified_big_board_insights(unified_df)
            # Export unified big board with trends and Monte Carlo
            export_to_excel(unified_df, filename='fantasy_big_board_unified_with_trends_and_mc.xlsx')
        except Exception as e:
            print(f'[ERROR] Failed to create unified big board: {e}')
            traceback.print_exc()
            # Fallback to regular ranking
            print('[INFO] Falling back to regular ranking...')
            ranked_df = rank_players(results_df)
            export_to_excel(ranked_df)
            return
        print('[SUCCESS] Unified big board with trends, Monte Carlo, and VBD/scarcity exported to fantasy_big_board_unified_with_trends_and_mc.xlsx')
    except Exception as e:
        print(f'[FATAL ERROR] Pipeline failed: {e}')
        traceback.print_exc()

if __name__ == '__main__':
    main() 