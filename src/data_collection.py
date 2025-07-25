import os
import requests
import pandas as pd

def get_odds_api_props(api_key):
    # Example endpoint for player props (update as needed)
    url = f"https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/?apiKey={api_key}&regions=us&markets=player_props&oddsFormat=decimal"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def get_odds_api_team_totals(api_key):
    # Endpoint for game lines (for implied points)
    url = f"https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/?apiKey={api_key}&regions=us&markets=totals,spreads&oddsFormat=decimal"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def download_nflfastr_csv(season=2023, out_path=None):
    """Download nflfastR play-by-play CSV for a given season."""
    base_url = f"https://github.com/nflverse/nflfastR-data/releases/download/play_by_play_{season}/play_by_play_{season}.csv.gz"
    if out_path is None:
        out_path = f"play_by_play_{season}.csv.gz"
    r = requests.get(base_url, stream=True)
    r.raise_for_status()
    with open(out_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return out_path

def load_nflfastr_data(csv_path):
    return pd.read_csv(csv_path, compression='gzip', low_memory=False)

def calculate_team_pace(nflfastr_df):
    """
    Returns a DataFrame with team, plays per game.
    """
    # Only regular season games
    reg = nflfastr_df[nflfastr_df['season_type'] == 'REG']
    # Offensive plays per team per game
    team_plays = reg.groupby(['posteam', 'game_id']).size().reset_index(name='plays')
    team_pace = team_plays.groupby('posteam')['plays'].mean().reset_index()
    team_pace.columns = ['team', 'plays_per_game']
    return team_pace 