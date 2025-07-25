import pandas as pd
import requests
from io import BytesIO

FANTASYPROS_URLS = {
    'QB': 'https://www.fantasypros.com/nfl/projections/qb.php?export=xls',
    'RB': 'https://www.fantasypros.com/nfl/projections/rb.php?export=xls',
    'WR': 'https://www.fantasypros.com/nfl/projections/wr.php?export=xls',
    'TE': 'https://www.fantasypros.com/nfl/projections/te.php?export=xls',
}

POSITION_MAP = {
    'QB': 'QB',
    'RB': 'RB',
    'WR': 'WR',
    'TE': 'TE',
}

def download_fantasypros_excel(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return pd.read_excel(BytesIO(resp.content), engine='xlrd')

def download_fantasypros_projections():
    dfs = []
    for pos, url in FANTASYPROS_URLS.items():
        print(f"[INFO] Downloading FantasyPros projections for {pos}...")
        try:
            df = download_fantasypros_excel(url)
            df['position'] = POSITION_MAP[pos]
            dfs.append(df)
        except Exception as e:
            print(f"[WARN] Could not download or parse {pos} projections: {e}")
    if not dfs:
        print("[ERROR] No projections downloaded from FantasyPros.")
        return pd.DataFrame()
    all_proj = pd.concat(dfs, ignore_index=True)
    return all_proj 