import pandas as pd

FANTASYPROS_LOCAL_FILES = {
    'QB': 'data/FantasyPros_Fantasy_Football_Projections_QB.csv',
    'RB': 'data/FantasyPros_Fantasy_Football_Projections_RB.csv',
    'WR': 'data/FantasyPros_Fantasy_Football_Projections_WR.csv',
    'TE': 'data/FantasyPros_Fantasy_Football_Projections_TE.csv',
}

POSITION_MAP = {
    'QB': 'QB',
    'RB': 'RB',
    'WR': 'WR',
    'TE': 'TE',
}

def download_fantasypros_projections():
    dfs = []
    for pos, path in FANTASYPROS_LOCAL_FILES.items():
        print(f"[INFO] Reading FantasyPros projections for {pos} from {path}...")
        try:
            # Read CSV with header, then filter out blank rows
            df = pd.read_csv(path, header=0)
            # Remove rows where Player column is empty or just whitespace
            df = df[df['Player'].notnull() & (df['Player'].str.strip() != '')]
            df['position'] = POSITION_MAP[pos]
            dfs.append(df)
        except Exception as e:
            print(f"[WARN] Could not read {pos} projections: {e}")
    if not dfs:
        print("[ERROR] No projections loaded from FantasyPros.")
        return pd.DataFrame()
    all_proj = pd.concat(dfs, ignore_index=True)
    return all_proj 