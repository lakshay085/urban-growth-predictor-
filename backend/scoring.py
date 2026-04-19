"""
scoring.py — Growth Velocity Score Calculator

Computes a multi-dimensional Growth Velocity Score (0–100) for each locality
zone by weighting:
  1. Government infrastructure signals (lead indicator)
  2. Rental yield attractiveness (undervaluation signal)
  3. Listing density (developer activity)
  4. Price momentum (appreciation rate)
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler


# ── WEIGHT CONFIGURATION ─────────────────────────────────────────────────────
# Adjust these weights to change how much each factor influences the final score.
# All weights must sum to 1.0
WEIGHTS = {
    "govt_signal":     0.35,   # Infrastructure/government project announcements
    "rental_yield":    0.25,   # High rent vs low price = undervalued zone
    "listing_density": 0.20,   # Active developer interest in the area
    "price_momentum":  0.20,   # Current price appreciation rate
}

# Appreciation projection parameters
BASE_APPRECIATION_RATE = 0.06   # 6% annual base appreciation
HOTSPOT_BOOST = 0.10           # Additional 10% for hotspot zones
EMERGING_BOOST = 0.05          # Additional 5% for emerging zones


def normalize_series(s: pd.Series) -> pd.Series:
    """Scale a series to 0-1 range."""
    if s.std() == 0:
        return pd.Series(0.5, index=s.index)
    scaler = MinMaxScaler()
    values = s.values.reshape(-1, 1)
    return pd.Series(
        scaler.fit_transform(values).flatten(),
        index=s.index
    )


def calculate_growth_velocity_score(
    locality_df: pd.DataFrame,
    govt_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculate Growth Velocity Score (0-100) for each locality.

    Higher score = zone is predicted to appreciate faster.

    Parameters:
        locality_df: Output of aggregate_by_locality()
        govt_df:     Government projects dataframe (from govt_data.py)
    """
    df = locality_df.copy()

    # ── FACTOR 1: Government signal ───────────────────────────────────────────
    # Attach govt project score to each locality by proximity (within ~5km)
    df["govt_signal"] = df.apply(
        lambda row: _get_govt_signal(row, govt_df), axis=1
    )

    # ── FACTOR 2: Rental yield ────────────────────────────────────────────────
    # High rental yield relative to price = market hasn't caught up yet
    df["rental_yield_score"] = df["rental_yield"].clip(
        upper=df["rental_yield"].quantile(0.95)
    )

    # ── FACTOR 3: Listing density ─────────────────────────────────────────────
    # More listings = more developer activity = growing zone
    # Use log scale to reduce impact of extreme outliers
    df["density_score"] = np.log1p(df["listing_count"])

    # ── FACTOR 4: Price momentum ──────────────────────────────────────────────
    # Already computed as z-score in data_loader
    df["momentum_score"] = df["price_momentum"]

    # ── NORMALIZE all factors to 0-1 ─────────────────────────────────────────
    df["n_govt"]     = normalize_series(df["govt_signal"])
    df["n_yield"]    = normalize_series(df["rental_yield_score"])
    df["n_density"]  = normalize_series(df["density_score"])
    df["n_momentum"] = normalize_series(df["momentum_score"])

    # ── WEIGHTED SUM → final score 0-100 ─────────────────────────────────────
    df["growth_velocity_score"] = (
        df["n_govt"]     * WEIGHTS["govt_signal"] +
        df["n_yield"]    * WEIGHTS["rental_yield"] +
        df["n_density"]  * WEIGHTS["listing_density"] +
        df["n_momentum"] * WEIGHTS["price_momentum"]
    ) * 100

    df["growth_velocity_score"] = df["growth_velocity_score"].round(1)

    # ── CATEGORY LABELS ───────────────────────────────────────────────────────
    # Use percentile-based thresholds for meaningful distribution
    p75 = df["growth_velocity_score"].quantile(0.75)
    p90 = df["growth_velocity_score"].quantile(0.90)
    df["zone_category"] = df["growth_velocity_score"].apply(
        lambda s: "Hotspot" if s >= p90 else ("Emerging" if s >= p75 else "Watch")
    )

    # ── PROJECTED APPRECIATION (24-month) ─────────────────────────────────────
    df["projected_appreciation_24m"] = df.apply(
        lambda row: _project_appreciation(row, months=24), axis=1
    )

    # ── INVESTMENT RATING ─────────────────────────────────────────────────────
    df["investment_rating"] = df["growth_velocity_score"].apply(_get_investment_rating)

    return df.sort_values("growth_velocity_score", ascending=False).reset_index(drop=True)


def _get_govt_signal(row: pd.Series, govt_df: pd.DataFrame) -> float:
    """
    For a given locality, sum the signal strength of all government
    projects within 15km radius, with distance decay.
    """
    if govt_df.empty:
        return 0.0

    # Approximate distance using Euclidean (fast, good enough at city scale)
    # 1 degree lat/lon ≈ 111km
    lat_diff = (govt_df["latitude"] - row["latitude"]) * 111
    lon_diff = (govt_df["longitude"] - row["longitude"]) * 111
    distances_km = np.sqrt(lat_diff**2 + lon_diff**2)

    # 15km radius to capture wider infrastructure impact
    nearby = govt_df[distances_km <= 15.0].copy()

    if nearby.empty:
        return 0.0

    # Weight by project importance, decay with distance
    nearby_distances = distances_km[distances_km <= 15.0]
    decay = 1.0 / (1.0 + nearby_distances * 0.3)  # gentler decay
    score = (nearby["signal_weight"] * decay).sum()
    return float(score)


def _project_appreciation(row: pd.Series, months: int = 24) -> float:
    """
    Estimate projected price appreciation over N months.
    Based on the zone's growth velocity score.
    """
    category = str(row["zone_category"])
    if category == "Hotspot":
        annual_rate = BASE_APPRECIATION_RATE + HOTSPOT_BOOST
    elif category == "Emerging":
        annual_rate = BASE_APPRECIATION_RATE + EMERGING_BOOST
    else:
        annual_rate = BASE_APPRECIATION_RATE

    # Compound appreciation
    years = months / 12
    appreciation = ((1 + annual_rate) ** years - 1) * 100
    return round(appreciation, 1)


def _get_investment_rating(score: float) -> str:
    """Map score to a human-readable investment rating."""
    if score >= 80:
        return "Strong Buy"
    elif score >= 66:
        return "Buy"
    elif score >= 50:
        return "Accumulate"
    elif score >= 33:
        return "Hold"
    elif score >= 20:
        return "Underweight"
    else:
        return "Avoid"
