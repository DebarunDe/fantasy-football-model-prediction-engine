import os
import requests
import pandas as pd

SPORTSBOOKAPI_BASE = "https://sportsbook-odds.p.rapidapi.com/v2"

# Helper to call SportsbookAPI

def sportsbookapi_request(endpoint, params=None, api_key=None):
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "sportsbook-odds.p.rapidapi.com"
    }
    url = f"{SPORTSBOOKAPI_BASE}{endpoint}"
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def get_nfl_events(api_key):
    # Get all NFL events with odds available
    return sportsbookapi_request("/events", {"leagueID": "NFL", "oddsAvailable": "true"}, api_key)

def get_event_player_props(event_id, api_key):
    # Correct: eventID as query param, not path param
    return sportsbookapi_request("/props", {"eventID": event_id}, api_key)

def download_nflfastr_csv(season=2023, out_path=None):
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
    reg = nflfastr_df[nflfastr_df['season_type'] == 'REG']
    team_plays = reg.groupby(['posteam', 'game_id']).size().reset_index(name='plays')
    team_pace = team_plays.groupby('posteam')['plays'].mean().reset_index()
    team_pace.columns = ['team', 'plays_per_game']
    return team_pace 