import pandas as pd

def calculate_fantasy_points(row):
    """
    Calculate full PPR fantasy points from player prop row.
    Expects columns: rushing_yds, rushing_tds, receptions, receiving_yds, receiving_tds, passing_yds, passing_tds
    """
    return (
        row.get('rushing_yds', 0) * 0.1 +
        row.get('rushing_tds', 0) * 6 +
        row.get('receptions', 0) * 1 +
        row.get('receiving_yds', 0) * 0.1 +
        row.get('receiving_tds', 0) * 6 +
        row.get('passing_yds', 0) * 0.04 +
        row.get('passing_tds', 0) * 4
    )

def extract_player_availability(nflfastr_df, player_id):
    """
    Returns games played, age, and position for a given player_id from nflfastR data.
    """
    player_data = nflfastr_df[nflfastr_df['player_id'] == player_id]
    games_played = player_data['game_id'].nunique()
    age = player_data['age'].iloc[0] if not player_data.empty else None
    position = player_data['position'].iloc[0] if not player_data.empty else None
    return games_played, age, position 