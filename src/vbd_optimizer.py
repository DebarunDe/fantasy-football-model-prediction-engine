import pandas as pd
import numpy as np

def calculate_replacement_baselines(df, league_size=12):
    """
    Calculate replacement-level players for each position.
    Based on league_size (number of teams).
    """
    baselines = {}
    # For standard leagues:
    # QB: 1 per team
    # RB: 2 per team
    # WR: 2 per team
    # TE: 1 per team
    qb_idx = league_size - 1
    rb_idx = 2 * league_size - 1
    wr_idx = 2 * league_size - 1
    te_idx = league_size - 1
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df[df['position'] == position].sort_values('raw_fantasy_points', ascending=False)
        if position == 'QB':
            baseline_idx = qb_idx
        elif position == 'RB':
            baseline_idx = rb_idx
        elif position == 'WR':
            baseline_idx = wr_idx
        elif position == 'TE':
            baseline_idx = te_idx
        if len(pos_df) > baseline_idx:
            baselines[position] = pos_df.iloc[baseline_idx]['raw_fantasy_points']
        else:
            # Fallback: use median if not enough players
            baselines[position] = pos_df['raw_fantasy_points'].median()
    return baselines

def calculate_vor(df, baselines):
    """
    Calculate Value Over Replacement (VOR) for each player.
    """
    df_vor = df.copy()
    df_vor['vor'] = 0.0
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_mask = df_vor['position'] == position
        baseline = baselines.get(position, 0)
        df_vor.loc[pos_mask, 'vor'] = df_vor.loc[pos_mask, 'raw_fantasy_points'] - baseline
    
    return df_vor

def calculate_opportunity_cost(df_vor):
    """
    Calculate opportunity cost based on positional scarcity.
    """
    df_oc = df_vor.copy()
    df_oc['opportunity_cost'] = 0.0
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df_oc[df_oc['position'] == position].sort_values('vor', ascending=False)
        
        if len(pos_df) > 1:
            # Calculate drop-off to next best player at same position
            for i in range(len(pos_df) - 1):
                current_vor = pos_df.iloc[i]['vor']
                next_vor = pos_df.iloc[i + 1]['vor']
                drop_off = current_vor - next_vor
                
                # Set opportunity cost for current player
                player_idx = pos_df.index[i]
                df_oc.loc[player_idx, 'opportunity_cost'] = drop_off
    
    return df_oc

def calculate_optimal_value(df_oc, vor_weight=0.7, oc_weight=0.3):
    """
    Calculate optimal value score combining VOR and opportunity cost.
    """
    df_optimal = df_oc.copy()
    
    # Normalize VOR and opportunity cost to 0-1 scale
    df_optimal['vor_normalized'] = (df_optimal['vor'] - df_optimal['vor'].min()) / (df_optimal['vor'].max() - df_optimal['vor'].min())
    df_optimal['oc_normalized'] = (df_optimal['opportunity_cost'] - df_optimal['opportunity_cost'].min()) / (df_optimal['opportunity_cost'].max() - df_optimal['opportunity_cost'].min())
    
    # Calculate optimal value score
    df_optimal['optimal_value'] = (
        df_optimal['vor_normalized'] * vor_weight + 
        df_optimal['oc_normalized'] * oc_weight
    )
    
    return df_optimal

def optimize_big_board(df):
    """
    Optimize big board using Value-Based Drafting principles.
    """
    print("[INFO] Calculating replacement baselines...")
    baselines = calculate_replacement_baselines(df)
    print(f"Replacement Baselines: {baselines}")
    
    print("[INFO] Calculating Value Over Replacement (VOR)...")
    df_vor = calculate_vor(df, baselines)
    
    print("[INFO] Calculating opportunity cost...")
    df_oc = calculate_opportunity_cost(df_vor)
    
    print("[INFO] Calculating optimal value scores...")
    df_optimal = calculate_optimal_value(df_oc)
    
    # Rank by optimal value
    df_optimal['vbd_rank'] = df_optimal['optimal_value'].rank(ascending=False, method='min')
    df_optimal = df_optimal.sort_values('vbd_rank')
    
    return df_optimal

def analyze_positional_scarcity(df_optimal):
    """
    Analyze positional scarcity and provide drafting insights.
    """
    print("\n=== POSITIONAL SCARCITY ANALYSIS ===")
    
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df_optimal[df_optimal['position'] == position].head(10)
        if not pos_df.empty:
            print(f"\n{position} Top 10:")
            for _, row in pos_df.iterrows():
                print(f"  {row['player_id']}: {row['raw_fantasy_points']:.1f} pts, VOR: {row['vor']:.1f}, OC: {row['opportunity_cost']:.1f}")

def generate_draft_strategy(df_optimal):
    """
    Generate draft strategy recommendations based on VBD analysis.
    """
    print("\n=== DRAFT STRATEGY RECOMMENDATIONS ===")
    
    # Find highest VOR players by position
    top_vor_by_pos = {}
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df_optimal[df_optimal['position'] == position]
        if not pos_df.empty:
            top_player = pos_df.loc[pos_df['vor'].idxmax()]
            top_vor_by_pos[position] = top_player
    
    # Find highest opportunity cost players
    top_oc_players = df_optimal.nlargest(5, 'opportunity_cost')[['player_id', 'position', 'opportunity_cost', 'vor']]
    
    print("Highest VOR Players by Position:")
    for pos, player in top_vor_by_pos.items():
        print(f"  {pos}: {player['player_id']} (VOR: {player['vor']:.1f})")
    
    print("\nHighest Opportunity Cost Players:")
    for _, player in top_oc_players.iterrows():
        print(f"  {player['player_id']} ({player['position']}): OC {player['opportunity_cost']:.1f}, VOR {player['vor']:.1f}")

if __name__ == "__main__":
    # This would be called from main.py after loading the data
    pass 