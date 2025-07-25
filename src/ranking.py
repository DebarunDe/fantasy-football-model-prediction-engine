import pandas as pd

def rank_players(df, points_col='weighted_fantasy_points'):
    df = df.copy()
    df['rank'] = df[points_col].rank(ascending=False, method='min')
    df = df.sort_values('rank')
    return df

def export_to_excel(df, filename='fantasy_big_board.xlsx'):
    df.to_excel(filename, index=False) 