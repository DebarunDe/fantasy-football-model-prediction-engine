# Fantasy Football Model Prediction Engine

## Overview
This project automates the process of collecting NFL player prop data and team context from free APIs, processes the data to calculate full PPR fantasy points, applies injury and team context weightings, and outputs a ranked big board to Excel. The entire pipeline is automated and can be run via GitHub Actions.

## Features
- Collects player prop data from The Odds API
- Downloads and processes nflfastR data for games played, age, position, and pace of play
- Calculates full PPR fantasy points from prop data
- Weights fantasy points by injury proxy (games played, age, position) and team context (win totals, implied points, pace)
- Outputs a ranked big board to Excel
- Fully automated via GitHub Actions

## Setup
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Add your The Odds API key to a `.env` file or as a GitHub Actions secret (see below).

## Usage
- To run locally:
  ```bash
  python src/main.py
  ```
- To run via GitHub Actions:
  - Trigger the workflow manually or on a schedule.
  - The output Excel file will be available as a workflow artifact.

## API Keys
- The Odds API: [https://the-odds-api.com/](https://the-odds-api.com/)
- Store your API key in an environment variable named `ODDS_API_KEY`.

## Data Sources
- Player props, team context: The Odds API
- Games played, age, position, pace: nflfastR (automatically downloaded)

## Output
- Excel file with player rankings, weighted fantasy points, and all relevant stats.

## Customization
- The pipeline is modular and can be extended to include additional data sources or weighting logic as needed.