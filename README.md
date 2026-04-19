# Urban Growth Predictor Engine

A Predictive Geospatial Analytics Engine for Real Estate Investment.

The Urban Growth Predictor Engine combines real estate data with government infrastructure projects to compute real-time **Growth Velocity Scores** for neighborhoods. It surfaces emerging real estate hotspots proactively, presenting the insights on an interactive map-based dashboard.

## Overview

The engine consists of:
1. **Data Normalization & Scoring (Backend)**: Fast data pipeline built using pandas. Loads thousands of property listings, matches them with planned infrastructure, and applies a multi-factor algorithm.
2. **REST API**: Built with FastAPI to serve scored zones, statistics, and government projects.
3. **Interactive Dashboard (Frontend)**: Real-time map rendering using Leaflet and CARTO dark maps, showcasing heatmaps, zone categorization, and a leaderboard of top investment localities.

## Key Features

- **Growth Velocity Score Model**: Evaluates localities based on four pillars:
  - Government Signal (Infrastructure project proximity)
  - Rental Yield (Implied cap rate)
  - Market Momentum (Avg price changes/levels)
  - Listing Density (Market liquidity)
- **Zone Categories**: Automatically categorizes zones into **Hotspot**, **Emerging**, and **Watch** using percentile thresholds.
- **Geospatial Map**: Built using Leaflet and CartoDB Dark tile layers. Features heatmapping, glowing interactive markers, and map filters.
- **Micro-animations**: Smooth UI interactions, animated numbers, and a sleek side panel for deep analytics on specific zones.

## Tech Stack

- **Backend**: Python, FastAPI, Pandas, Scikit-learn, Uvicorn
- **Frontend**: HTML5, CSS3 (Vanilla), JavaScript
- **Map**: Leaflet, Leaflet.heat
- **Hosting**: Render / Vercel (Configured via `vercel.json` & `render.yaml`)

## Running Locally

### 1. Requirements

Make sure you have Python 3.9+ installed.

### 2. Setup Virtual Environment (Optional but recommended)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Server

```bash
uvicorn main:app --reload --port 8000
```
*Note: If port 8000 is in use, use another port like 8001 (`--port 8001`).*

### 5. Access the Dashboard

Open your browser and navigate to:
[http://localhost:8000](http://localhost:8000)

The root URL serves the frontend `index.html` seamlessly through FastAPI's static file handler.

## Project Structure

```text
urban-growth/
├── backend/
│   ├── main.py             # FastAPI entrypoint and routes
│   ├── scoring.py          # Logic for the Growth Velocity scoring algorithm
│   ├── data_loader.py      # Data cleaning and aggregation logic
│   ├── govt_data.py        # Loading and formatting government projects
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── index.html          # Main dashboard UI
│   ├── index.css           # Styling for the application
│   └── map.js              # Leaflet map logic, API interactions, and UI updates
└── data/
    ├── gurgaon_10k.csv     # Property listings data examples
    └── govt_projects.json  # Mock data for government infra projects
```

## Future Roadmap

- Further enrich government and census datasets.
- Implement more granular temporal models for price appreciation.
- Support real time data ingestion via external APIs.
