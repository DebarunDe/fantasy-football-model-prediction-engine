def injury_weight(games_played, age, position):
    """
    Calculate injury/availability weight based on games played, age, and position.
    """
    games_weight = games_played / 17.0
    age_penalty = 1.0
    if position in ['RB', 'WR']:
        if (position == 'RB' and age is not None and age >= 28) or (position == 'WR' and age is not None and age >= 30):
            age_penalty = 0.95
    return games_weight * age_penalty

def team_context_weight(implied_points, league_avg_points, win_total, league_avg_wins, pace, league_avg_plays, position):
    """
    Calculate team context weight using best-practice parameters and position-specific logic.
    """
    alpha = 0.03  # Implied points (per TD above avg)
    gamma = 0.01  # Pace (per 2 plays above avg)
    # Position-specific beta
    if position == 'RB':
        beta = 0.01
    elif position in ['WR', 'QB', 'TE']:
        beta = -0.01
    else:
        beta = 0.0
    # Avoid division by zero
    league_avg_points = league_avg_points or 1
    league_avg_wins = league_avg_wins or 1
    league_avg_plays = league_avg_plays or 1
    # Calculate weight
    implied_points_component = 1 + alpha * ((implied_points - league_avg_points) / 7)
    win_total_component = 1 + beta * (win_total - league_avg_wins)
    pace_component = 1 + gamma * ((pace - league_avg_plays) / 2)
    return implied_points_component * win_total_component * pace_component 