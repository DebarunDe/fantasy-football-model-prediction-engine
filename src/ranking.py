import pandas as pd

def rank_players(df, points_col='weighted_fantasy_points'):
    df = df.copy()
    df['rank'] = df[points_col].rank(ascending=False, method='min')
    df = df.sort_values('rank')
    return df

def export_to_excel(df, filename='fantasy_big_board.xlsx'):
    """
    Export the unified big board to Excel with comprehensive formatting.
    Shows all players ranked together with individual optimization metrics, trends, Monte Carlo analysis, and efficiency metrics.
    """
    # Select and order columns for the unified big board
    columns = [
        'unified_rank', 'player_id', 'team', 'position', 'raw_fantasy_points',
        'efficiency_adjusted_points', 'efficiency_adjustment_pct', 'total_efficiency_multiplier',
        'unified_big_board_score', 'z_score', 'position_percentile',
        'risk_adjusted_value', 'risk_score', 'sharpe_ratio',
        'bayesian_value', 'projection_uncertainty',
        'consistency_adjusted_value', 'consistency_score',
        'upside_potential', 'trend_adjusted_points', 'trend_slope',
        'recent_momentum', 'momentum_strength', 'trajectory',
        'breakout_potential', 'regression_risk', 'mc_mean', 'mc_median',
        'mc_25th_percentile', 'mc_75th_percentile', 'mc_volatility',
        'mc_probability_above_avg', 'mc_upside_potential', 'mc_downside_risk',
        'mc_adjusted_score', 'mc_rank', 'rank',
        # VBD & Scarcity columns
        'vor', 'scarcity_factor', 'vor_scarcity_adjusted', 'sos_factor', 'vor_final'
    ]

    # Only include columns that exist in the dataframe
    export_columns = [col for col in columns if col in df.columns]

    # Add any missing columns with default values
    for col in columns:
        if col not in df.columns:
            if col == 'unified_rank':
                df[col] = df.get('rank', range(1, len(df) + 1))
            elif col in ['unified_big_board_score', 'z_score', 'position_percentile',
                        'risk_adjusted_value', 'risk_score', 'sharpe_ratio',
                        'bayesian_value', 'projection_uncertainty',
                        'consistency_adjusted_value', 'consistency_score',
                        'upside_potential', 'trend_adjusted_points', 'trend_slope',
                        'recent_momentum', 'momentum_strength', 'breakout_potential',
                        'regression_risk', 'mc_mean', 'mc_median', 'mc_25th_percentile',
                        'mc_75th_percentile', 'mc_volatility', 'mc_probability_above_avg',
                        'mc_upside_potential', 'mc_downside_risk', 'mc_adjusted_score',
                        'efficiency_adjusted_points', 'efficiency_adjustment_pct', 'total_efficiency_multiplier']:
                df[col] = 0.0
            elif col == 'trajectory':
                df[col] = 'Unknown'
            elif col == 'mc_rank':
                df[col] = df.get('rank', range(1, len(df) + 1))

    # Reorder columns for export
    final_columns = [col for col in columns if col in df.columns]
    export_df = df[final_columns].copy()

    # Create Excel writer
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Write main unified big board
        export_df.to_excel(writer, sheet_name='Unified Big Board', index=False)

        # Create additional analysis sheets
        create_unified_analysis_sheets(writer, df)

        # Get the workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Unified Big Board']

        # Auto-adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width

    print(f'[INFO] Unified big board exported to {filename}')
    return filename

def create_unified_analysis_sheets(writer, df):
    """
    Create additional analysis sheets for the unified big board approach.
    """
    # Top 50 players
    top_50_df = df.head(50)[['unified_rank', 'player_id', 'position', 'unified_big_board_score', 'raw_fantasy_points']]
    top_50_df.to_excel(writer, sheet_name='Top_50_Players', index=False)

    # Position-specific rankings
    for pos in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df[df['position'] == pos].head(20)[['unified_rank', 'player_id', 'unified_big_board_score', 'raw_fantasy_points']]
        pos_df.to_excel(writer, sheet_name=f'{pos}_Rankings', index=False)

    # Risk analysis
    if 'risk_score' in df.columns:
        risk_df = df.sort_values('risk_score', ascending=False)[['unified_rank', 'player_id', 'position', 'risk_score', 'sharpe_ratio']]
        risk_df.to_excel(writer, sheet_name='Risk_Analysis', index=False)

    # Consistency analysis
    if 'consistency_score' in df.columns:
        consistency_df = df.sort_values('consistency_score', ascending=False)[['unified_rank', 'player_id', 'position', 'consistency_score']]
        consistency_df.to_excel(writer, sheet_name='Consistency_Analysis', index=False)

    # Bayesian analysis
    if 'bayesian_value' in df.columns:
        bayesian_df = df.sort_values('bayesian_value', ascending=False)[['unified_rank', 'player_id', 'position', 'bayesian_value', 'projection_uncertainty']]
        bayesian_df.to_excel(writer, sheet_name='Bayesian_Analysis', index=False)

    # Statistical outliers
    if 'z_score' in df.columns:
        outliers_df = df[abs(df['z_score']) > 2][['unified_rank', 'player_id', 'position', 'z_score', 'position_percentile']]
        outliers_df.to_excel(writer, sheet_name='Statistical_Outliers', index=False)

    # Upside analysis
    if 'upside_potential' in df.columns:
        upside_df = df.sort_values('upside_potential', ascending=False)[['unified_rank', 'player_id', 'position', 'upside_potential']]
        upside_df.to_excel(writer, sheet_name='Upside_Analysis', index=False)

    # Position distribution
    pos_dist = df.groupby('position').agg({
        'player_id': 'count',
        'unified_big_board_score': 'mean',
        'raw_fantasy_points': 'mean'
    }).reset_index()
    pos_dist.columns = ['Position', 'Player_Count', 'Avg_Unified_Score', 'Avg_Raw_Points']
    pos_dist.to_excel(writer, sheet_name='Position_Distribution', index=False)

    # Efficiency analysis sheets
    if 'efficiency_adjustment_pct' in df.columns:
        # Top efficiency boosters
        efficiency_boosters = df.nlargest(20, 'efficiency_adjustment_pct')[['unified_rank', 'player_id', 'position', 'efficiency_adjustment_pct', 'total_efficiency_multiplier']]
        efficiency_boosters.to_excel(writer, sheet_name='Efficiency_Boosters', index=False)

        # Top efficiency penalties
        efficiency_penalties = df.nsmallest(20, 'efficiency_adjustment_pct')[['unified_rank', 'player_id', 'position', 'efficiency_adjustment_pct', 'total_efficiency_multiplier']]
        efficiency_penalties.to_excel(writer, sheet_name='Efficiency_Penalties', index=False)

        # Efficiency by position
        eff_pos_dist = df.groupby('position').agg({
            'efficiency_adjustment_pct': 'mean',
            'total_efficiency_multiplier': 'mean'
        }).reset_index()
        eff_pos_dist.columns = ['Position', 'Avg_Efficiency_Adjustment_Pct', 'Avg_Efficiency_Multiplier']
        eff_pos_dist.to_excel(writer, sheet_name='Efficiency_by_Position', index=False)

    # Trend analysis sheets
    if 'breakout_potential' in df.columns:
        # Breakout candidates
        breakout_df = df.sort_values('breakout_potential', ascending=False)[['unified_rank', 'player_id', 'position', 'breakout_potential', 'recent_momentum', 'trajectory']]
        breakout_df.to_excel(writer, sheet_name='Breakout_Candidates', index=False)

        # Regression risks
        regression_df = df.sort_values('regression_risk', ascending=False)[['unified_rank', 'player_id', 'position', 'regression_risk', 'recent_momentum', 'trajectory']]
        regression_df.to_excel(writer, sheet_name='Regression_Risks', index=False)

        # Momentum analysis
        momentum_df = df.sort_values('recent_momentum', ascending=False)[['unified_rank', 'player_id', 'position', 'recent_momentum', 'momentum_strength', 'trajectory']]
        momentum_df.to_excel(writer, sheet_name='Momentum_Analysis', index=False)

        # Trend trajectories
        trajectory_df = df.groupby('trajectory').agg({
            'player_id': 'count',
            'unified_big_board_score': 'mean',
            'raw_fantasy_points': 'mean'
        }).reset_index()
        trajectory_df.columns = ['Trajectory', 'Player_Count', 'Avg_Unified_Score', 'Avg_Raw_Points']
        trajectory_df.to_excel(writer, sheet_name='Trajectory_Analysis', index=False)

    # Monte Carlo analysis sheets
    if 'mc_mean' in df.columns:
        # Monte Carlo rankings
        if all(col in df.columns for col in ['mc_rank', 'mc_adjusted_score', 'mc_mean', 'mc_volatility']):
            mc_rankings_df = df.sort_values('mc_rank')[['mc_rank', 'player_id', 'position', 'mc_adjusted_score', 'mc_mean', 'mc_volatility']]
            mc_rankings_df.to_excel(writer, sheet_name='Monte_Carlo_Rankings', index=False)
        # Highest upside potential
        if all(col in df.columns for col in ['mc_upside_potential', 'mc_volatility', 'mc_mean']):
            mc_upside_df = df.sort_values('mc_upside_potential', ascending=False)[['unified_rank', 'player_id', 'position', 'mc_upside_potential', 'mc_volatility', 'mc_mean']]
            mc_upside_df.to_excel(writer, sheet_name='MC_Upside_Analysis', index=False)
        # Safest players (lowest downside risk)
        if all(col in df.columns for col in ['mc_downside_risk', 'mc_volatility', 'mc_mean']):
            mc_safe_df = df.sort_values('mc_downside_risk')[['unified_rank', 'player_id', 'position', 'mc_downside_risk', 'mc_volatility', 'mc_mean']]
            mc_safe_df.to_excel(writer, sheet_name='MC_Safety_Analysis', index=False)
        # Highest probability of exceeding average
        if all(col in df.columns for col in ['mc_probability_above_avg', 'mc_mean', 'mc_volatility']):
            mc_prob_df = df.sort_values('mc_probability_above_avg', ascending=False)[['unified_rank', 'player_id', 'position', 'mc_probability_above_avg', 'mc_mean', 'mc_volatility']]
            mc_prob_df.to_excel(writer, sheet_name='MC_Probability_Analysis', index=False)
        # Most volatile players
        if all(col in df.columns for col in ['mc_volatility', 'mc_confidence_interval', 'mc_mean']):
            mc_volatile_df = df.sort_values('mc_volatility', ascending=False)[['unified_rank', 'player_id', 'position', 'mc_volatility', 'mc_confidence_interval', 'mc_mean']]
            mc_volatile_df.to_excel(writer, sheet_name='MC_Volatility_Analysis', index=False) 