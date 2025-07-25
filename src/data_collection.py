import os
import requests
import pandas as pd
from datetime import datetime

SPORTSBOOKAPI_BASE = "https://sportsbook-api2.p.rapidapi.com"

# Helper to call SportsbookAPI

def sportsbookapi_request(endpoint, params=None, api_key=None):
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "sportsbook-api2.p.rapidapi.com"
    }
    url = f"{SPORTSBOOKAPI_BASE}{endpoint}"
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def get_nfl_season_key(api_key):
    data = sportsbookapi_request("/v0/competitions/", params={"includeInstances": "true"}, api_key=api_key)
    competitions = data.get("competitions", [])
    today = datetime.utcnow().date()
    nfl_instances = []
    for comp in competitions:
        if comp.get("slug") == "national-football-league":
            for instance in comp.get("competitionInstances", []):
                start_str = instance.get("startAt")
                if start_str:
                    start_date = datetime.fromisoformat(start_str.replace("Z", "")).date()
                    if start_date >= today:
                        nfl_instances.append((start_date, instance["key"]))
    if not nfl_instances:
        raise ValueError("No upcoming NFL season found in /v0/competitions/")
    # Return the soonest upcoming season
    nfl_instances.sort()
    return nfl_instances[0][1]

def get_nfl_events_v0(competition_key, api_key):
    return sportsbookapi_request(f"/v0/competitions/{competition_key}/events", api_key=api_key)

def get_event_markets_v0(event_key, api_key):
    return sportsbookapi_request(f"/v0/events/{event_key}/markets", api_key=api_key)

def get_market_outcomes_v0(market_key, api_key):
    return sportsbookapi_request(f"/v0/markets/{market_key}/outcomes", api_key=api_key)

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