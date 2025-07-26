import pandas as pd
import numpy as np
from scipy import stats

def calculate_advanced_statistical_metrics(df):
    """
    Calculate advanced statistical metrics for individual player evaluation.
    Maintains individual player focus while adding sophisticated analysis.
    """
    df_metrics = df.copy()
    
    # Calculate position-specific statistics
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_mask = df_metrics['position'] == position
        pos_df = df_metrics[pos_mask]
        
        if len(pos_df) > 0:
            # Calculate position averages and standard deviations
            pos_mean = pos_df['raw_fantasy_points'].mean()
            pos_std = pos_df['raw_fantasy_points'].std()
            
            # Z-Score: How many standard deviations above/below position average
            df_metrics.loc[pos_mask, 'z_score'] = (
                (pos_df['raw_fantasy_points'] - pos_mean) / pos_std
            )
            
            # Percentile Rank within position
            df_metrics.loc[pos_mask, 'position_percentile'] = (
                pos_df['raw_fantasy_points'].rank(pct=True) * 100
            )
            
            # Coefficient of Variation (consistency measure)
            # Lower = more consistent, Higher = more volatile
            df_metrics.loc[pos_mask, 'consistency_score'] = 1.0 - (
                pos_df['raw_fantasy_points'] / pos_df['raw_fantasy_points'].max()
            )
    
    return df_metrics

def calculate_risk_adjusted_value(df):
    """
    Calculate risk-adjusted value using individual player characteristics.
    Applies portfolio theory concepts to individual players.
    """
    df_risk = df.copy()
    
    # Risk factors for each individual player
    for idx, row in df_risk.iterrows():
        risk_score = 0.0
        upside_potential = 0.0
        
        # Position-based risk (individual characteristic)
        if row['position'] == 'RB':
            risk_score += 0.3  # High injury risk
            upside_potential += 0.2  # High ceiling
        elif row['position'] == 'QB':
            risk_score += 0.1  # Lower injury risk
            upside_potential += 0.3  # Very high ceiling
        elif row['position'] == 'WR':
            risk_score += 0.2  # Moderate risk
            upside_potential += 0.4  # Highest ceiling
        elif row['position'] == 'TE':
            risk_score += 0.25  # Moderate-high risk
            upside_potential += 0.1  # Lower ceiling
        
        # Individual performance risk (higher points = higher risk)
        if row['raw_fantasy_points'] > 300:
            risk_score += 0.2  # Elite players have higher expectations
            upside_potential += 0.1  # But also higher upside
        
        # Experience risk (rookies vs veterans)
        if any(keyword in row['player_id'] for keyword in ['Jr.', 'III', 'IV', 'V']):
            risk_score += 0.2  # Rookie risk
            upside_potential += 0.3  # Rookie upside
        
        # Team context risk (individual player's situation)
        if row['team'] in ['WAS', 'NE', 'CHI']:  # New systems
            risk_score += 0.15
        elif row['team'] in ['KC', 'BUF', 'CIN']:  # Stable, high-powered
            risk_score -= 0.1
            upside_potential += 0.1
        
        # Calculate Sharpe Ratio (return per unit of risk)
        if risk_score > 0:
            sharpe_ratio = row['raw_fantasy_points'] / (risk_score * 100)
        else:
            sharpe_ratio = row['raw_fantasy_points'] / 10  # Base risk
        
        df_risk.loc[idx, 'risk_score'] = min(risk_score, 1.0)
        df_risk.loc[idx, 'upside_potential'] = min(upside_potential, 1.0)
        df_risk.loc[idx, 'sharpe_ratio'] = sharpe_ratio
        
        # Risk-adjusted value score
        df_risk.loc[idx, 'risk_adjusted_value'] = (
            row['raw_fantasy_points'] * (1 + upside_potential) * (1 - risk_score * 0.5)
        )
    
    return df_risk

def calculate_bayesian_adjustments(df):
    """
    Apply Bayesian adjustments to individual player projections.
    Accounts for uncertainty and regression to mean.
    """
    df_bayes = df.copy()
    
    # Calculate position-specific priors (baseline expectations)
    position_priors = {}
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df_bayes[df_bayes['position'] == position]
        if len(pos_df) > 0:
            position_priors[position] = {
                'mean': pos_df['raw_fantasy_points'].mean(),
                'std': pos_df['raw_fantasy_points'].std(),
                'count': len(pos_df)
            }
    
    # Apply Bayesian adjustments to each player
    for idx, row in df_bayes.iterrows():
        position = row['position']
        prior = position_priors.get(position, {'mean': 200, 'std': 50, 'count': 1})
        
        # Current projection
        current_projection = row['raw_fantasy_points']
        
        # Prior belief (position average)
        prior_belief = prior['mean']
        
        # Uncertainty in current projection (higher for rookies, new teams)
        projection_uncertainty = 0.3  # Base uncertainty
        
        if any(keyword in row['player_id'] for keyword in ['Jr.', 'III', 'IV', 'V']):
            projection_uncertainty += 0.2  # Rookie uncertainty
        
        if row['team'] in ['WAS', 'NE', 'CHI']:
            projection_uncertainty += 0.1  # New system uncertainty
        
        # Bayesian posterior (weighted average of projection and prior)
        # More uncertainty = more weight on prior (regression to mean)
        bayesian_adjustment = (
            current_projection * (1 - projection_uncertainty) +
            prior_belief * projection_uncertainty
        )
        
        # Confidence interval
        confidence_interval = prior['std'] * projection_uncertainty
        
        df_bayes.loc[idx, 'bayesian_projection'] = bayesian_adjustment
        df_bayes.loc[idx, 'projection_uncertainty'] = projection_uncertainty
        df_bayes.loc[idx, 'confidence_interval'] = confidence_interval
        
        # Bayesian value score
        df_bayes.loc[idx, 'bayesian_value'] = (
            bayesian_adjustment * (1 - projection_uncertainty * 0.5)
        )
    
    return df_bayes

def calculate_consistency_metrics(df):
    """
    Calculate individual player consistency metrics.
    Focuses on individual player characteristics.
    """
    df_consistency = df.copy()
    
    for idx, row in df_consistency.iterrows():
        consistency_score = 0.5  # Base consistency
        
        # Position consistency (individual characteristic)
        if row['position'] == 'QB':
            consistency_score += 0.2  # QBs are most consistent
        elif row['position'] == 'WR':
            consistency_score += 0.1  # WRs are moderately consistent
        elif row['position'] == 'RB':
            consistency_score -= 0.1  # RBs can be volatile
        elif row['position'] == 'TE':
            consistency_score -= 0.2  # TEs can be inconsistent
        
        # Individual scoring level consistency
        if 200 <= row['raw_fantasy_points'] <= 350:
            consistency_score += 0.1  # Sweet spot for consistency
        elif row['raw_fantasy_points'] > 400:
            consistency_score -= 0.1  # Very high scorers can be volatile
        
        # Experience consistency
        if any(keyword in row['player_id'] for keyword in ['Jr.', 'III', 'IV', 'V']):
            consistency_score -= 0.2  # Rookies less consistent
        else:
            consistency_score += 0.1  # Veterans more consistent
        
        # Team stability consistency
        if row['team'] in ['KC', 'BUF', 'CIN', 'PHI']:
            consistency_score += 0.1  # Stable, good teams
        elif row['team'] in ['WAS', 'NE', 'CHI']:
            consistency_score -= 0.1  # New systems
        
        df_consistency.loc[idx, 'consistency_score'] = max(0.0, min(1.0, consistency_score))
        
        # Consistency-adjusted value
        df_consistency.loc[idx, 'consistency_adjusted_value'] = (
            row['raw_fantasy_points'] * (1 + consistency_score * 0.2)
        )
    
    return df_consistency

def calculate_unified_big_board_score(df):
    """
    Create a unified big board that blends individual optimizations with cross-positional ranking.
    All players ranked together on one big board, with injury risk applied as a small downward weight to the raw fantasy points projection.
    Enhanced Monte Carlo integration for better probabilistic modeling and tie-breaking.
    Now incorporates efficiency-adjusted points as the primary component.
    """
    df_unified = df.copy()

    # Apply all individual optimizations (but will minimize their effect in the final score)
    df_unified = calculate_advanced_statistical_metrics(df_unified)
    df_unified = calculate_risk_adjusted_value(df_unified)
    df_unified = calculate_bayesian_adjustments(df_unified)
    df_unified = calculate_consistency_metrics(df_unified)

    for idx, row in df_unified.iterrows():
        # Use efficiency-adjusted points as primary component (if available)
        efficiency_adjusted_points = row.get('efficiency_adjusted_points', row.get('raw_fantasy_points', 0))
        raw_points = row.get('raw_fantasy_points', 0)
        injury_weight = row.get('injury_weight', 1.0)
        
        # Apply a small penalty for injury risk (e.g., 20% of the risk is applied)
        injury_penalty = (1.0 - injury_weight) * 0.2
        injury_adjusted_points = efficiency_adjusted_points * (1.0 - injury_penalty)

        # Monte Carlo metrics (if available)
        mc_mean = row.get('mc_mean', injury_adjusted_points)
        mc_median = row.get('mc_median', injury_adjusted_points)
        mc_25th_percentile = row.get('mc_25th_percentile', injury_adjusted_points)
        mc_75th_percentile = row.get('mc_75th_percentile', injury_adjusted_points)
        mc_volatility = row.get('mc_volatility', 0)
        mc_probability_above_avg = row.get('mc_probability_above_avg', 0.5)
        mc_upside_potential = row.get('mc_upside_potential', 0)
        mc_downside_risk = row.get('mc_downside_risk', 0)

        # VOR/scarcity/SOS integration
        vor_final = row.get('vor_final', 0)
        # Normalize vor_final for blending (avoid negative/zero)
        vor_norm = max(vor_final, 0)

        # Position-specific adjustments for VOR and scarcity
        if row['position'] == 'QB':
            vor_weight = 0.40  # Increased from 0.35 to further boost QB value
            scarcity_boost = 1.20  # Increased from 1.15 to boost QB scarcity
            cap = 1.0  # Keep QB cap removed
        elif row['position'] == 'RB':
            vor_weight = 0.40  # Reduced from 0.45 to further reduce RB overvaluation
            scarcity_boost = 1.05  # Reduced from 1.10 to reduce RB boost
            cap = 1.0
        elif row['position'] == 'WR':
            vor_weight = 0.60  # Increased from 0.55 to boost WR value further
            scarcity_boost = 1.25  # Increased from 1.20 to boost WR scarcity
            cap = 1.0
        elif row['position'] == 'TE':
            vor_weight = 0.35  # Increased from 0.25 to boost TE value for PPR scarcity
            scarcity_boost = 1.15  # Increased from 1.05 to boost TE scarcity premium
            cap = 1.0
        else:
            vor_weight = 0.30
            scarcity_boost = 1.0
            cap = 1.0

        position_factor = 1.0
        if row['position'] == 'QB':
            position_factor = 1.10  # Increased from 1.05 to boost QB value
        elif row['position'] == 'RB':
            position_factor = 1.00  # Reduced from 1.05 to reduce RB overvaluation
        elif row['position'] == 'WR':
            position_factor = 1.20  # Increased from 1.15 to boost WR value
        elif row['position'] == 'TE':
            position_factor = 1.12  # Increased from 1.05 to boost TE value for PPR scarcity

        # Position-specific volatility penalty (higher penalty for more volatile positions)
        volatility_penalty = 0
        if row['position'] == 'QB':
            volatility_penalty = mc_volatility * 4  # Increased QB volatility penalty
        elif row['position'] == 'RB':
            volatility_penalty = mc_volatility * 2.5  # RBs are also volatile
        elif row['position'] == 'WR':
            volatility_penalty = mc_volatility * 1.8  # Reduced WR volatility penalty
        elif row['position'] == 'TE':
            volatility_penalty = mc_volatility * 1.0  # Further reduced TE volatility penalty for PPR stability

        # Enhanced unified big board score with VOR/scarcity/SOS integration
        unified_score = (
            injury_adjusted_points * 0.20 +           # Reduced efficiency-adjusted projection weight
            mc_mean * 0.10 +                        # Reduced Monte Carlo mean weight
            mc_median * 0.02 +                      # Reduced MC median weight
            mc_25th_percentile * 0.01 +             # Conservative MC estimate
            mc_75th_percentile * 0.01 +             # Upside MC estimate
            mc_probability_above_avg * 1.5 +        # Reduced probability bonus
            mc_upside_potential * 0.06 -             # Reduced upside potential bonus
            volatility_penalty +                    # Position-adjusted volatility penalty
            vor_norm * vor_weight * scarcity_boost
        )
        
        # Apply position factor and cap
        unified_score *= position_factor
        if row['position'] == 'QB':
            unified_score *= cap  # Cap QB scores
        df_unified.loc[idx, 'unified_big_board_score'] = unified_score

    df_unified['unified_rank'] = df_unified['unified_big_board_score'].rank(ascending=False, method='min')
    df_unified = df_unified.sort_values('unified_rank')
    return df_unified

def analyze_unified_big_board_insights(df_unified):
    """
    Generate insights about the unified big board rankings.
    """
    print("\n=== UNIFIED BIG BOARD INSIGHTS ===")
    
    # Top 10 overall players
    top_10 = df_unified.head(10)[['player_id', 'position', 'team', 'unified_big_board_score', 'raw_fantasy_points']]
    print("\nTop 10 Players (Unified Big Board):")
    for _, player in top_10.iterrows():
        print(f"  {player['player_id']} ({player['team']} {player['position']}): {player['unified_big_board_score']:.1f} score, {player['raw_fantasy_points']:.1f} pts")
    
    # Position distribution in top 20
    top_20 = df_unified.head(20)
    pos_dist = top_20['position'].value_counts()
    print(f"\nPosition Distribution in Top 20:")
    for pos, count in pos_dist.items():
        print(f"  {pos}: {count} players")
    
    # Best players by position (top 3 each)
    for position in ['QB', 'RB', 'WR', 'TE']:
        pos_players = df_unified[df_unified['position'] == position].head(3)
        print(f"\nTop 3 {position}s:")
        for _, player in pos_players.iterrows():
            print(f"  {player['player_id']} ({player['team']}): {player['unified_big_board_score']:.1f} score, {player['raw_fantasy_points']:.1f} pts")
    
    # Statistical outliers (highest z-scores)
    best_z_scores = df_unified.nlargest(5, 'z_score')[['player_id', 'position', 'z_score', 'unified_rank']]
    print("\nBiggest Statistical Outliers (vs Position Average):")
    for _, player in best_z_scores.iterrows():
        print(f"  {player['player_id']} ({player['position']}): {player['z_score']:.2f} z-score, rank #{player['unified_rank']:.0f}")
    
    # Best risk-adjusted values
    best_risk_adjusted = df_unified.nlargest(5, 'risk_adjusted_value')[['player_id', 'position', 'risk_adjusted_value', 'unified_rank']]
    print("\nBest Risk-Adjusted Values:")
    for _, player in best_risk_adjusted.iterrows():
        print(f"  {player['player_id']} ({player['position']}): {player['risk_adjusted_value']:.1f} value, rank #{player['unified_rank']:.0f}") 