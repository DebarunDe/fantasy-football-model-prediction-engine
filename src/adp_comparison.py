import pandas as pd
import requests
from rapidfuzz import fuzz, process
import numpy as np
import time
import re
import json
import os

def normalize_player_name(name):
    """
    Normalize player names for consistent matching.
    """
    if pd.isna(name):
        return ''
    
    # Convert to lowercase and remove extra whitespace
    normalized = str(name).lower().strip()
    
    # Remove special characters
    normalized = normalized.replace('.', '').replace(',', '').replace('-', ' ')
    
    # Handle common name variations
    name_variations = {
        'jimmy': 'james',
        'jameison': 'jameson',
        'patrick mahomes ii': 'patrick mahomes',
        'patrick mahomes 2': 'patrick mahomes',
        'patrick mahomes 2nd': 'patrick mahomes',
        'patrick mahomes': 'patrick mahomes',
        'mahomes': 'patrick mahomes',
        'aaron jones sr': 'aaron jones',
        'aaron jones sr.': 'aaron jones',
        'aaron jones senior': 'aaron jones',
    }
    
    for variation, standard in name_variations.items():
        if variation in normalized:
            normalized = normalized.replace(variation, standard)
    
    return normalized

def get_fantasy_football_calculator_adp(league_size=12):
    """
    Get ADP data from Fantasy Football Calculator REST API.
    Based on their official API documentation: https://help.fantasyfootballcalculator.com/article/42-adp-rest-api
    """
    try:
        # Fantasy Football Calculator REST API endpoint
        base_url = "https://fantasyfootballcalculator.com/api/v1/adp"
        
        # Use the configurable league size from our pipeline
        # Fantasy Football Calculator supports common league sizes
        supported_league_sizes = [8, 10, 12, 14, 16]
        
        # Find the closest supported league size
        closest_league_size = min(supported_league_sizes, key=lambda x: abs(x - league_size))
        if closest_league_size != league_size:
            print(f"[INFO] League size {league_size} not supported by Fantasy Football Calculator. Using closest supported size: {closest_league_size}")
        
        # Try different scoring formats with our league size
        scoring_formats = ['standard', 'ppr', 'half-ppr']
        years = [2025, 2024]  # Try current and previous year
        
        # Try different API endpoints and parameters for more comprehensive data
        api_variations = [
            # Standard ADP endpoint
            f"{base_url}/{{scoring}}?teams={{teams}}&year={{year}}",
            # Try without year parameter
            f"{base_url}/{{scoring}}?teams={{teams}}",
            # Try with different parameter orders
            f"{base_url}/{{scoring}}?year={{year}}&teams={{teams}}",
            # Try rankings endpoint as fallback
            f"{base_url.replace('/adp', '/rankings')}/{{scoring}}?teams={{teams}}&year={{year}}",
            # Try without scoring format
            f"{base_url}?teams={{teams}}&year={{year}}",
            # Try with format parameter
            f"{base_url}/{{scoring}}?teams={{teams}}&year={{year}}&format=json"
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        best_result = None
        max_players = 0
        
        for api_template in api_variations:
            for scoring in scoring_formats:
                for year in years:
                    try:
                        url = api_template.format(scoring=scoring, teams=closest_league_size, year=year)
                        print(f"[INFO] Trying Fantasy Football Calculator API: {url}")
                        
                        response = requests.get(url, headers=headers, timeout=15)
                        response.raise_for_status()
                        
                        # Parse JSON response
                        data = response.json()
                        players = parse_fantasy_calculator_api_data(data)
                        
                        if players and len(players) > max_players:
                            max_players = len(players)
                            best_result = players
                            print(f"[SUCCESS] Found {len(players)} players from Fantasy Football Calculator API ({scoring}, {closest_league_size} teams, {year})")
                        
                    except Exception as e:
                        print(f"[WARNING] Failed with template {api_template}, {scoring}, {closest_league_size} teams, {year}: {e}")
                        continue
        
        if best_result:
            print(f"[SUCCESS] Using best result with {len(best_result)} players")
            return pd.DataFrame(best_result, columns=['player_name', 'adp'])
        
        print("[ERROR] Could not get data from Fantasy Football Calculator API")
        return pd.DataFrame(columns=['player_name', 'adp'])
        
    except Exception as e:
        print(f"[ERROR] Fantasy Football Calculator API error: {e}")
        return pd.DataFrame(columns=['player_name', 'adp'])

def parse_fantasy_calculator_api_data(data):
    """
    Parse JSON data from Fantasy Football Calculator REST API.
    Based on their API response format.
    """
    players = []
    
    try:
        # The API should return a JSON object with a players array
        if isinstance(data, dict):
            # Look for players array in the response - try multiple possible keys
            players_array = data.get('players') or data.get('data') or data.get('rankings') or data.get('adp') or data.get('results')
            
            if players_array and isinstance(players_array, list):
                for player in players_array:
                    if isinstance(player, dict):
                        # Extract player name and ADP from the API response - try multiple possible keys
                        name = player.get('name') or player.get('player') or player.get('player_name') or player.get('full_name')
                        adp = player.get('adp') or player.get('rank') or player.get('position') or player.get('overall_rank')
                        
                        if name and adp is not None:
                            try:
                                adp_value = float(adp)
                                players.append((name, adp_value))
                            except (ValueError, TypeError):
                                continue
            
            # If no players array found, check if data is directly a list
            elif isinstance(data.get('data'), list):
                for player in data['data']:
                    if isinstance(player, dict):
                        name = player.get('name') or player.get('player')
                        adp = player.get('adp') or player.get('rank')
                        
                        if name and adp is not None:
                            try:
                                adp_value = float(adp)
                                players.append((name, adp_value))
                            except (ValueError, TypeError):
                                continue
        
        # If data is directly a list
        elif isinstance(data, list):
            for player in data:
                if isinstance(player, dict):
                    name = player.get('name') or player.get('player')
                    adp = player.get('adp') or player.get('rank')
                    
                    if name and adp is not None:
                        try:
                            adp_value = float(adp)
                            players.append((name, adp_value))
                        except (ValueError, TypeError):
                            continue
        
        # Sort by ADP
        players.sort(key=lambda x: x[1])
        
        # Remove duplicates based on player name
        seen_names = set()
        unique_players = []
        for name, adp in players:
            normalized_name = normalize_player_name(name)
            if normalized_name not in seen_names:
                seen_names.add(normalized_name)
                unique_players.append((name, adp))
        
        print(f"[INFO] Parsed {len(unique_players)} unique players from API response")
        
    except Exception as e:
        print(f"[WARNING] Error parsing Fantasy Football Calculator API data: {e}")
    
    return unique_players

def load_adp_from_csv():
    """
    Load ADP data from CSV files in the data folder.
    Expected files: Fantasy_Football_Calculator_ADP_2025.csv
    """
    adp_df = pd.DataFrame()
    
    # Try to load Fantasy Football Calculator ADP
    try:
        adp_path = 'data/Fantasy_Football_Calculator_ADP_2025.csv'
        if os.path.exists(adp_path):
            adp_df = pd.read_csv(adp_path)
            print(f"[SUCCESS] Loaded Fantasy Football Calculator ADP from {adp_path}: {len(adp_df)} players")
        else:
            print(f"[INFO] Fantasy Football Calculator ADP file not found at {adp_path}")
    except Exception as e:
        print(f"[WARNING] Could not load Fantasy Football Calculator ADP: {e}")
    
    return adp_df

def collect_fantasy_football_calculator_adp(league_size=12):
    """
    Collect ADP data from Fantasy Football Calculator - try CSV first, then API.
    """
    # Try loading from CSV first
    adp_df = load_adp_from_csv()
    if not adp_df.empty:
        return adp_df
    
    # Fall back to Fantasy Football Calculator API with configurable league size
    print(f"[INFO] Trying Fantasy Football Calculator REST API for ADP data (league size: {league_size})")
    ffc_df = get_fantasy_football_calculator_adp(league_size)
    if not ffc_df.empty:
        return ffc_df
    
    print("[ERROR] Could not get Fantasy Football Calculator ADP data")
    return pd.DataFrame(columns=['player_name', 'adp'])

def get_average_adp(league_size=12):
    """
    Get ADP data from Fantasy Football Calculator with configurable league size.
    """
    adp_df = collect_fantasy_football_calculator_adp(league_size)
    
    if adp_df.empty:
        print("[ERROR] No ADP data available from Fantasy Football Calculator")
        return pd.DataFrame(columns=['player_name', 'normalized_name', 'adp'])
    
    # Normalize player names
    adp_df['normalized_name'] = adp_df['player_name'].apply(normalize_player_name)
    
    # Sort by ADP
    adp_df = adp_df.sort_values('adp')
    
    print(f"[SUCCESS] Loaded Fantasy Football Calculator ADP data: {len(adp_df)} players (league size: {league_size})")
    return adp_df[['player_name', 'normalized_name', 'adp']]

def validate_adp_data(adp_df):
    """
    Validate ADP data and filter out suspicious values.
    """
    print("[INFO] Validating ADP data quality...")
    
    # Filter out known incorrect ADP entries
    incorrect_adp_entries = [
        'Tom Kennedy',  # ADP 40.0 is clearly wrong - should be Jameson Williams but we have both players
        'Ben VanSumeren',  # ADP 88.0 is clearly wrong for this player
        'Nate Adkins',  # ADP 91.3 is clearly wrong for this player
    ]
    
    # Remove incorrect ADP entries
    for incorrect_name in incorrect_adp_entries:
        if incorrect_name in adp_df['player_name'].values:
            print(f"[INFO] Removing incorrect ADP entry: '{incorrect_name}' (ADP data error)")
            adp_df = adp_df[adp_df['player_name'] != incorrect_name]
    
    # Handle duplicate ADP values by adding small offsets
    print("[INFO] Checking for duplicate ADP values...")
    duplicate_adp = adp_df[adp_df.duplicated(subset=['adp'], keep=False)]
    if not duplicate_adp.empty:
        print(f"[WARNING] Found {len(duplicate_adp)} players with duplicate ADP values")
        
        # Group by ADP value and add small offsets to break ties
        for adp_val in duplicate_adp['adp'].unique():
            duplicate_players = adp_df[adp_df['adp'] == adp_val]
            if len(duplicate_players) > 1:
                print(f"[INFO] Resolving duplicate ADP {adp_val}: {', '.join(duplicate_players['player_name'].tolist())}")
                
                # Add small offsets (0.1, 0.2, etc.) to break ties
                for i, (idx, _) in enumerate(duplicate_players.iterrows()):
                    if i > 0:  # Keep the first one unchanged
                        adp_df.loc[idx, 'adp'] = adp_val + (i * 0.1)
    
    # Filter out suspicious ADP values
    suspicious_adp = adp_df[
        (adp_df['adp'] < 1) |  # ADP below 1 is suspicious
        (adp_df['adp'] > 200) |  # ADP above 200 is suspicious
        (adp_df['adp'].isna())  # Missing ADP values
    ]
    
    if not suspicious_adp.empty:
        print(f"[WARNING] Found {len(suspicious_adp)} suspicious ADP values:")
        for _, row in suspicious_adp.iterrows():
            print(f"  {row['player_name']}: ADP {row['adp']}")
    
    # Filter out suspicious values
    clean_adp = adp_df[
        (adp_df['adp'] >= 1) & 
        (adp_df['adp'] <= 200) & 
        (adp_df['adp'].notna())
    ]
    
    print(f"[INFO] Cleaned ADP data: {len(clean_adp)} players (removed {len(adp_df) - len(clean_adp)} suspicious values)")
    return clean_adp

def get_value_color(league_size_adjusted_diff):
    """
    Get color based on league-size-adjusted rank difference.
    Updated with more intuitive thresholds for fantasy football value recommendations.
    """
    if pd.isna(league_size_adjusted_diff):
        return 'purple'  # Missing from ADP
    
    diff = league_size_adjusted_diff
    
    # More intuitive thresholds for fantasy football value recommendations
    # Much less aggressive thresholds for better balance
    if diff <= -1.0:
        return 'teal'      # Our rank is significantly better than ADP = Strong Buy
    elif diff <= -0.4:
        return 'green'     # Our rank is better than ADP = Buy
    elif diff <= -0.15:
        return 'light_green'  # Our rank is slightly better than ADP = Slight Buy
    elif diff <= 0.8:
        return 'white'     # Neutral - no strong recommendation (increased from 0.5)
    elif diff <= 1.8:
        return 'yellow'    # Our rank is slightly worse than ADP = Slight Avoid (increased from 1.2)
    else:
        return 'red'       # Our rank is much worse than ADP = Strong Avoid (increased threshold)

def get_value_recommendation(league_size_adjusted_diff):
    """
    Get recommendation based on league-size-adjusted rank difference.
    Uses the same logic as get_value_color for perfect alignment.
    """
    if pd.isna(league_size_adjusted_diff):
        return 'Not in ADP'
    
    diff = league_size_adjusted_diff
    
    # Same thresholds as get_value_color
    if diff <= -1.0:
        return 'Strong Buy'
    elif diff <= -0.4:
        return 'Buy'
    elif diff <= -0.15:
        return 'Slight Buy'
    elif diff <= 0.8:
        return 'Neutral'
    elif diff <= 1.8:
        return 'Slight Avoid'
    else:
        return 'Strong Avoid'

def match_players_to_adp(big_board_df, adp_df, league_size=12):
    """
    Match players from big board to ADP data and calculate value differences.
    Enhanced with better name matching and validation.
    """
    # Validate and clean ADP data
    clean_adp_df = validate_adp_data(adp_df)
    
    # Normalize player names in big board
    big_board_df = big_board_df.copy()
    big_board_df['normalized_name'] = big_board_df['player_id'].apply(normalize_player_name)
    
    # Create a mapping from normalized names to ADP data
    adp_dict = dict(zip(clean_adp_df['normalized_name'], clean_adp_df['adp']))
    
    # Match players using fuzzy matching with higher threshold
    matched_players = []
    unmatched_big_board = []
    
    for _, player in big_board_df.iterrows():
        normalized_name = player['normalized_name']
        player_position = player['position']
        
        # Try exact match first
        if normalized_name in adp_dict:
            matched_adp = adp_dict[normalized_name]
            
            # Additional validation for exact matches
            rank_diff = abs(player['unified_rank'] - matched_adp)
            if rank_diff > 100:  # Very large difference for exact match
                print(f"[WARNING] Large rank difference for exact match: {player['player_id']} (our rank {player['unified_rank']} vs ADP {matched_adp})")
            
            matched_players.append({
                'player_id': player['player_id'],
                'team': player.get('team', ''),
                'position': player['position'],
                'unified_rank': player['unified_rank'],
                'unified_big_board_score': player['unified_big_board_score'],
                'raw_fantasy_points': player.get('raw_fantasy_points', 0),
                'vor_final': player.get('vor_final', 0),
                'adp': matched_adp,
                'rank_difference': player['unified_rank'] - matched_adp,
                'league_size_adjusted_diff': (player['unified_rank'] - matched_adp) / league_size,
                'matched': True
            })
        else:
            # Try fuzzy matching with higher threshold and position validation
            best_match = process.extractOne(normalized_name, adp_dict.keys(), scorer=fuzz.ratio)
            if best_match and best_match[1] >= 95:  # Very high threshold for accuracy
                matched_adp = adp_dict[best_match[0]]
                
                # Additional validation: check if the match makes sense
                # If there's a huge discrepancy between our rank and ADP, be suspicious
                rank_diff = abs(player['unified_rank'] - matched_adp)
                if rank_diff > 50:  # Lowered threshold for fuzzy matches
                    print(f"[WARNING] Large rank difference for {player['player_id']}: our rank {player['unified_rank']} vs ADP {matched_adp} (diff: {rank_diff})")
                    print(f"[WARNING] Matched '{player['player_id']}' to '{best_match[0]}' with {best_match[1]}% similarity")
                    
                    # For very large discrepancies, don't match unless similarity is extremely high
                    if best_match[1] < 98:
                        print(f"[WARNING] Rejecting match due to large rank difference and low similarity")
                        unmatched_big_board.append({
                            'player_id': player['player_id'],
                            'team': player.get('team', ''),
                            'position': player['position'],
                            'unified_rank': player['unified_rank'],
                            'unified_big_board_score': player['unified_big_board_score'],
                            'raw_fantasy_points': player.get('raw_fantasy_points', 0),
                            'vor_final': player.get('vor_final', 0),
                            'adp': np.nan,
                            'rank_difference': np.nan,
                            'league_size_adjusted_diff': np.nan,
                            'matched': False
                        })
                        continue
                
                matched_players.append({
                    'player_id': player['player_id'],
                    'team': player.get('team', ''),
                    'position': player['position'],
                    'unified_rank': player['unified_rank'],
                    'unified_big_board_score': player['unified_big_board_score'],
                    'raw_fantasy_points': player.get('raw_fantasy_points', 0),
                    'vor_final': player.get('vor_final', 0),
                    'adp': matched_adp,
                    'rank_difference': player['unified_rank'] - matched_adp,
                    'league_size_adjusted_diff': (player['unified_rank'] - matched_adp) / league_size,
                    'matched': True
                })
            else:
                # No match found - mark as purple (missing from ADP)
                unmatched_big_board.append({
                    'player_id': player['player_id'],
                    'team': player.get('team', ''),
                    'position': player['position'],
                    'unified_rank': player['unified_rank'],
                    'unified_big_board_score': player['unified_big_board_score'],
                    'raw_fantasy_points': player.get('raw_fantasy_points', 0),
                    'vor_final': player.get('vor_final', 0),
                    'adp': np.nan,
                    'rank_difference': np.nan,
                    'league_size_adjusted_diff': np.nan,
                    'matched': False
                })
    
    # Combine matched and unmatched players
    all_players = matched_players + unmatched_big_board
    
    # Create DataFrame and sort by ADP (unmatched players go to the end)
    result_df = pd.DataFrame(all_players)
    result_df = result_df.sort_values('adp', na_position='last')
    
    return result_df

def create_adp_comparison_sheet(big_board_df, league_size=12):
    """
    Create ADP comparison sheet with value recommendations.
    """
    print(f"[INFO] Creating ADP comparison sheet (league size: {league_size})")
    
    # Get ADP data
    adp_df = get_average_adp(league_size)
    
    # Match players to ADP
    comparison_df = match_players_to_adp(big_board_df, adp_df, league_size)
    
    # Add value color and recommendation
    comparison_df['value_color'] = comparison_df['league_size_adjusted_diff'].apply(get_value_color)
    
    # Add value recommendation text
    comparison_df['value_recommendation'] = comparison_df['league_size_adjusted_diff'].apply(get_value_recommendation)
    
    print(f"[SUCCESS] Created ADP comparison with {len(comparison_df)} players")
    print(f"[INFO] Value recommendations: {comparison_df['value_recommendation'].value_counts().to_dict()}")
    
    return comparison_df 