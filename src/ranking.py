import pandas as pd

def rank_players(df, points_col='weighted_fantasy_points'):
    df = df.copy()
    df['rank'] = df[points_col].rank(ascending=False, method='min')
    df = df.sort_values('rank')
    return df

def export_to_excel(df, filename='fantasy_big_board.xlsx'):
    """
    Export the unified big board to Excel with clean, user-friendly formatting.
    Shows the main big board and position-specific rankings only.
    """
    # Select key columns for the unified big board
    columns = [
        'unified_rank', 'player_id', 'team', 'position', 'raw_fantasy_points',
        'unified_big_board_score', 'vor_final'
    ]

    # Only include columns that exist in the dataframe
    export_columns = [col for col in columns if col in df.columns]

    # Add any missing columns with default values
    for col in columns:
        if col not in df.columns:
            if col == 'unified_rank':
                df[col] = df.get('rank', range(1, len(df) + 1))
            elif col in ['unified_big_board_score', 'vor_final']:
                df[col] = 0.0

    # Reorder columns for export
    final_columns = [col for col in columns if col in df.columns]
    export_df = df[final_columns].copy()

    # Create Excel writer
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Write main unified big board
        export_df.to_excel(writer, sheet_name='Big Board', index=False)

        # Create position-specific ranking sheets
        create_position_sheets(writer, df)

        # Get the workbook and worksheet
        workbook = writer.book
        worksheet = writer.sheets['Big Board']

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

    print(f'[INFO] Clean big board exported to {filename}')
    return filename

def create_position_sheets(writer, df):
    """
    Create position-specific ranking sheets.
    """
    # Position-specific rankings with key metrics
    for pos in ['QB', 'RB', 'WR', 'TE']:
        pos_df = df[df['position'] == pos].copy()
        if not pos_df.empty:
            # Select key columns for position sheets
            pos_columns = ['unified_rank', 'player_id', 'team', 'raw_fantasy_points', 'unified_big_board_score']
            if 'vor_final' in pos_df.columns:
                pos_columns.append('vor_final')
            
            # Only include columns that exist
            pos_export_columns = [col for col in pos_columns if col in pos_df.columns]
            pos_export_df = pos_df[pos_export_columns].copy()
            
            # Sort by unified rank
            pos_export_df = pos_export_df.sort_values('unified_rank')
            
            pos_export_df.to_excel(writer, sheet_name=f'{pos}_Rankings', index=False)
            
            # Auto-adjust column widths for position sheets
            worksheet = writer.sheets[f'{pos}_Rankings']
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