"""
main.py — FastAPI Server for Urban Growth Predictor

Serves the API endpoints and the frontend dashboard.
Loads and scores all data at startup for fast API responses.
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from data_loader import load_data, aggregate_by_locality
from scoring import calculate_growth_velocity_score
from govt_data import load_govt_data

app = FastAPI(
    title="Urban Growth Predictor",
    description="Predictive Geospatial Analytics Engine for Real Estate Investment",
    version="1.0.0",
)

# Allow frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend files
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "../frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")


# ── Load data once at startup ─────────────────────────────────────────────────
print("=" * 60)
print("  Urban Growth Predictor — Starting up")
print("=" * 60)

print("\n[1/4] Loading 99acres data...")
raw_df = load_data()

print("\n[2/4] Aggregating by locality...")
locality_df = aggregate_by_locality(raw_df)

print("\n[3/4] Loading government project data...")
govt_df = load_govt_data()

print("\n[4/4] Computing Growth Velocity Scores...")
scored_df = calculate_growth_velocity_score(locality_df, govt_df)
print(f"\n✓ Ready! {len(scored_df)} locality zones scored and ranked.")
print("=" * 60)


@app.get("/")
def serve_frontend():
    """Serve the main dashboard page."""
    return FileResponse(os.path.join(FRONTEND_PATH, "index.html"))


@app.get("/api/zones")
def get_zones(
    city: str = Query(None, description="Filter by city name"),
    category: str = Query(None, description="Filter by zone_category: Watch, Emerging, Hotspot"),
    min_score: float = Query(None, description="Minimum growth velocity score"),
    limit: int = Query(500, description="Max number of zones to return"),
):
    """
    Returns scored zones for the heatmap.
    Each zone has: locality, city, lat, lng, score, category, metrics.
    """
    df = scored_df.copy()

    if city:
        df = df[df["city"].str.lower() == city.lower()]

    if category:
        df = df[df["zone_category"] == category]

    if min_score is not None:
        df = df[df["growth_velocity_score"] >= min_score]

    df = df.head(limit)

    return {
        "count": len(df),
        "zones": df[[
            "locality", "city", "latitude", "longitude",
            "growth_velocity_score", "zone_category",
            "avg_price", "avg_price_per_sqft", "avg_rent",
            "rental_yield", "listing_count",
            "projected_appreciation_24m", "investment_rating",
            "n_govt", "n_yield", "n_density", "n_momentum"
        ]].to_dict(orient="records"),
    }


@app.get("/api/cities")
def get_cities():
    """Returns list of available cities in the dataset."""
    cities = sorted(scored_df["city"].dropna().unique().tolist())
    return {"cities": cities}


@app.get("/api/govt-projects")
def get_govt_projects(city: str = Query(None, description="Filter by city")):
    """Returns government infrastructure projects for map overlay."""
    df = govt_df.copy()
    if city:
        df = df[df["city"].str.lower() == city.lower()]
    return {"projects": df.to_dict(orient="records")}


@app.get("/api/summary")
def get_summary():
    """Returns high-level stats for the dashboard header."""
    return {
        "total_zones": len(scored_df),
        "hotspots": int((scored_df["zone_category"] == "Hotspot").sum()),
        "emerging": int((scored_df["zone_category"] == "Emerging").sum()),
        "watch": int((scored_df["zone_category"] == "Watch").sum()),
        "avg_score": round(float(scored_df["growth_velocity_score"].mean()), 1),
        "top_zone": scored_df.iloc[0]["locality"] if len(scored_df) > 0 else "N/A",
        "top_score": float(scored_df.iloc[0]["growth_velocity_score"]) if len(scored_df) > 0 else 0,
        "cities_covered": int(scored_df["city"].nunique()),
    }


@app.get("/api/top-zones")
def get_top_zones(
    limit: int = Query(10, description="Number of top zones to return"),
    city: str = Query(None, description="Filter by city"),
):
    """Returns the top-scoring zones for the leaderboard."""
    df = scored_df.copy()
    if city:
        df = df[df["city"].str.lower() == city.lower()]

    df = df.head(limit)
    return {
        "zones": df[[
            "locality", "city", "growth_velocity_score",
            "zone_category", "avg_price_per_sqft",
            "listing_count", "projected_appreciation_24m",
            "investment_rating",
        ]].to_dict(orient="records"),
    }
