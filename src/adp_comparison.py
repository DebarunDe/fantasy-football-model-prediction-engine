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
    Normalize player names for matching between different data sources.
    """
    if pd.isna(name):
        return ""
    
    # Convert to string and lowercase
    name = str(name).lower().strip()
    
    # Remove common suffixes
    suffixes = [' ii', ' iii', ' iv', ' jr.', ' sr.', ' jr', ' sr']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    
    # Remove extra spaces
    name = ' '.join(name.split())
    
    return name

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

def match_players_to_adp(big_board_df, adp_df, league_size=12):
    """
    Match players from big board to ADP data and calculate value differences.
    """
    # Normalize player names in big board
    big_board_df = big_board_df.copy()
    big_board_df['normalized_name'] = big_board_df['player_id'].apply(normalize_player_name)
    
    # Create a mapping from normalized names to ADP data
    adp_dict = dict(zip(adp_df['normalized_name'], adp_df['adp']))
    
    # Match players using fuzzy matching
    matched_players = []
    unmatched_big_board = []
    
    for _, player in big_board_df.iterrows():
        normalized_name = player['normalized_name']
        
        # Try exact match first
        if normalized_name in adp_dict:
            matched_players.append({
                'player_id': player['player_id'],
                'team': player.get('team', ''),
                'position': player['position'],
                'unified_rank': player['unified_rank'],
                'unified_big_board_score': player['unified_big_board_score'],
                'raw_fantasy_points': player.get('raw_fantasy_points', 0),
                'vor_final': player.get('vor_final', 0),
                'adp': adp_dict[normalized_name],
                'rank_difference': player['unified_rank'] - adp_dict[normalized_name],
                'league_size_adjusted_diff': (player['unified_rank'] - adp_dict[normalized_name]) / league_size,
                'matched': True
            })
        else:
            # Try fuzzy matching
            best_match = process.extractOne(normalized_name, adp_dict.keys(), scorer=fuzz.ratio)
            if best_match and best_match[1] >= 85:  # 85% similarity threshold
                matched_adp = adp_dict[best_match[0]]
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

def get_value_color(league_size_adjusted_diff):
    """
    Get color based on league-size-adjusted rank difference.
    """
    if pd.isna(league_size_adjusted_diff):
        return 'purple'  # Missing from ADP
    
    diff = league_size_adjusted_diff
    
    if diff >= 1.0:
        return 'teal'      # +1 league size or better
    elif diff >= 0.5:
        return 'green'     # +0.5 to +1 league size
    elif diff >= 0.0:
        return 'light_green'  # +0 to +0.5 league size
    elif diff >= -0.5:
        return 'yellow'    # -0.5 to 0 league size
    elif diff >= -1.0:
        return 'orange'    # -1 to -0.5 league size
    else:
        return 'red'       # -1 league size or worse

def create_adp_comparison_sheet(big_board_df, league_size=12):
    """
    Create ADP comparison sheet with color coding using Fantasy Football Calculator data.
    """
    # Get ADP data with configurable league size
    adp_df = get_average_adp(league_size)
    
    # Match players
    comparison_df = match_players_to_adp(big_board_df, adp_df, league_size)
    
    # Add color coding
    comparison_df['value_color'] = comparison_df['league_size_adjusted_diff'].apply(get_value_color)
    
    # Add value recommendation
    def get_value_recommendation(color):
        if color == 'purple':
            return 'Not in ADP'
        elif color == 'teal':
            return 'Strong Buy'
        elif color == 'green':
            return 'Buy'
        elif color == 'light_green':
            return 'Slight Buy'
        elif color == 'yellow':
            return 'Slight Avoid'
        elif color == 'orange':
            return 'Avoid'
        elif color == 'red':
            return 'Strong Avoid'
        else:
            return 'Fair Value'
    
    comparison_df['value_recommendation'] = comparison_df['value_color'].apply(get_value_recommendation)
    
    return comparison_df 