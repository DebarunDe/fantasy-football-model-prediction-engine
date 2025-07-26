import pandas as pd
import requests
from rapidfuzz import fuzz, process
import numpy as np

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

def collect_espn_adp():
    """
    Collect ESPN ADP data for 2025 season.
    Note: This is a placeholder - in practice, you'd need to scrape ESPN or use their API.
    """
    # For now, we'll create a sample dataset
    # In production, you'd scrape ESPN's ADP data
    espn_adp_data = {
        'player_name': [
            'Josh Allen', 'Lamar Jackson', 'Jalen Hurts', 'Patrick Mahomes', 'Joe Burrow',
            'Christian McCaffrey', 'Bijan Robinson', 'Jahmyr Gibbs', 'Saquon Barkley', 'Derrick Henry',
            'Ja\'Marr Chase', 'Justin Jefferson', 'CeeDee Lamb', 'Tyreek Hill', 'Amon-Ra St. Brown',
            'Travis Kelce', 'Sam LaPorta', 'Mark Andrews', 'T.J. Hockenson', 'George Kittle',
            'De\'Von Achane', 'Josh Jacobs', 'Kyren Williams', 'Breece Hall', 'Jonathan Taylor',
            'Puka Nacua', 'Malik Nabers', 'Garrett Wilson', 'Chris Olave', 'Jaylen Waddle',
            'Jayden Daniels', 'Caleb Williams', 'Drake Maye', 'Anthony Richardson', 'Justin Fields'
        ],
        'espn_adp': [
            15, 18, 22, 25, 28,
            1, 2, 3, 4, 5,
            6, 7, 8, 9, 10,
            11, 12, 13, 14, 16,
            17, 19, 20, 21, 23,
            24, 26, 27, 29, 30,
            31, 32, 33, 34, 35
        ]
    }
    
    return pd.DataFrame(espn_adp_data)

def collect_yahoo_adp():
    """
    Collect Yahoo ADP data for 2025 season.
    Note: This is a placeholder - in practice, you'd need to scrape Yahoo or use their API.
    """
    # For now, we'll create a sample dataset
    # In production, you'd scrape Yahoo's ADP data
    yahoo_adp_data = {
        'player_name': [
            'Josh Allen', 'Lamar Jackson', 'Jalen Hurts', 'Patrick Mahomes', 'Joe Burrow',
            'Christian McCaffrey', 'Bijan Robinson', 'Jahmyr Gibbs', 'Saquon Barkley', 'Derrick Henry',
            'Ja\'Marr Chase', 'Justin Jefferson', 'CeeDee Lamb', 'Tyreek Hill', 'Amon-Ra St. Brown',
            'Travis Kelce', 'Sam LaPorta', 'Mark Andrews', 'T.J. Hockenson', 'George Kittle',
            'De\'Von Achane', 'Josh Jacobs', 'Kyren Williams', 'Breece Hall', 'Jonathan Taylor',
            'Puka Nacua', 'Malik Nabers', 'Garrett Wilson', 'Chris Olave', 'Jaylen Waddle',
            'Jayden Daniels', 'Caleb Williams', 'Drake Maye', 'Anthony Richardson', 'Justin Fields'
        ],
        'yahoo_adp': [
            16, 19, 21, 24, 27,
            1, 2, 3, 4, 5,
            6, 7, 8, 9, 10,
            11, 12, 13, 14, 15,
            17, 18, 20, 22, 23,
            25, 26, 28, 29, 30,
            31, 32, 33, 34, 35
        ]
    }
    
    return pd.DataFrame(yahoo_adp_data)

def get_average_adp(league_size=12):
    """
    Get average ADP from ESPN and Yahoo, with league size consideration.
    """
    espn_df = collect_espn_adp()
    yahoo_df = collect_yahoo_adp()
    
    # Normalize player names for matching
    espn_df['normalized_name'] = espn_df['player_name'].apply(normalize_player_name)
    yahoo_df['normalized_name'] = yahoo_df['player_name'].apply(normalize_player_name)
    
    # Merge ESPN and Yahoo ADP data
    merged_df = pd.merge(espn_df, yahoo_df, on='normalized_name', how='outer', suffixes=('_espn', '_yahoo'))
    
    # Calculate average ADP
    merged_df['avg_adp'] = merged_df[['espn_adp', 'yahoo_adp']].mean(axis=1)
    
    # Sort by average ADP
    merged_df = merged_df.sort_values('avg_adp')
    
    # Add original player name (prefer ESPN name if available)
    merged_df['player_name'] = merged_df['player_name_espn'].fillna(merged_df['player_name_yahoo'])
    
    return merged_df[['player_name', 'normalized_name', 'espn_adp', 'yahoo_adp', 'avg_adp']]

def match_players_to_adp(big_board_df, adp_df, league_size=12):
    """
    Match players from big board to ADP data and calculate value differences.
    """
    # Normalize player names in big board
    big_board_df = big_board_df.copy()
    big_board_df['normalized_name'] = big_board_df['player_id'].apply(normalize_player_name)
    
    # Create a mapping from normalized names to ADP data
    adp_dict = dict(zip(adp_df['normalized_name'], adp_df['avg_adp']))
    
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
                'avg_adp': adp_dict[normalized_name],
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
                    'avg_adp': matched_adp,
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
                    'avg_adp': np.nan,
                    'rank_difference': np.nan,
                    'league_size_adjusted_diff': np.nan,
                    'matched': False
                })
    
    # Combine matched and unmatched players
    all_players = matched_players + unmatched_big_board
    
    # Create DataFrame and sort by ADP (unmatched players go to the end)
    result_df = pd.DataFrame(all_players)
    result_df = result_df.sort_values('avg_adp', na_position='last')
    
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
    Create ADP comparison sheet with color coding.
    """
    # Get average ADP data
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