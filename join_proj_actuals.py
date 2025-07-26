import pandas as pd
import re
from rapidfuzz import process, fuzz

def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', name)
    name = re.sub(r'[^a-z ]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def fuzzy_merge(proj_file, actual_file, out_file):
    df_proj = pd.read_csv(proj_file)
    df_proj['norm_name'] = df_proj['player_id'].apply(normalize_name)
    df_actual = pd.read_csv(actual_file)
    df_actual['norm_name'] = df_actual['player_name'].apply(normalize_name)
    proj_names = df_proj['norm_name'].tolist()
    matches = []
    for idx, row in df_actual.iterrows():
        match, score, match_idx = process.extractOne(row['norm_name'], proj_names, scorer=fuzz.ratio)
        if score >= 85:
            matches.append((row['norm_name'], match))
        else:
            matches.append((row['norm_name'], None))
    df_actual['matched_norm_name'] = [m[1] for m in matches]
    merged = df_proj.merge(df_actual, left_on='norm_name', right_on='matched_norm_name')
    merged.to_csv(out_file, index=False)
    print(f"Merged {proj_file} with {actual_file} -> {out_file}")
    print(merged[['player_id','player_name','raw_fantasy_points','fantasy_points']].head(20))

def main():
    fuzzy_merge('feature_projections_2023.csv', 'actual_fantasy_points_2023.csv', 'merged_proj_actuals_2023.csv')
    fuzzy_merge('feature_projections_2024.csv', 'actual_fantasy_points_2024.csv', 'merged_proj_actuals_2024.csv')

if __name__ == '__main__':
    main() 