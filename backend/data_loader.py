"""
data_loader.py — Multi-CSV Data Ingestion Pipeline

Loads Gurgaon, Mumbai, Hyderabad, and Kolkata 99acres datasets,
normalizes their differing column schemas into a unified DataFrame,
and produces locality-level aggregates for scoring.
"""

import pandas as pd
import numpy as np
import os
import ast
import re

# ── DATA DIRECTORY ────────────────────────────────────────────────────────────
# Points to the archive folder with per-city CSVs
ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "../data/source")

# City-specific yield ratios for rent estimation (annual rent as % of price)
# These are typical Indian market yields; adjust if you have better data.
CITY_YIELD_RATIOS = {
    "gurgaon":    0.030,   # ~3.0% annual yield
    "mumbai":     0.025,   # ~2.5%
    "hyderabad":  0.035,   # ~3.5%
    "kolkata":    0.032,   # ~3.2%
    "default":    0.030,   # fallback
}


def _parse_map_details(val):
    """Extract latitude and longitude from MAP_DETAILS string/dict."""
    if pd.isna(val):
        return None, None
    try:
        if isinstance(val, str):
            d = ast.literal_eval(val)
        else:
            d = val
        lat = float(d.get("LATITUDE", 0))
        lng = float(d.get("LONGITUDE", 0))
        if lat == 0 and lng == 0:
            return None, None
        return lat, lng
    except (ValueError, SyntaxError, TypeError):
        return None, None


def _parse_location_locality(val):
    """Extract LOCALITY_NAME from the 'location' dict column (Mumbai/Hyd/Kol)."""
    if pd.isna(val):
        return None
    try:
        if isinstance(val, str):
            d = ast.literal_eval(val)
        else:
            d = val
        return d.get("LOCALITY_NAME", None)
    except (ValueError, SyntaxError, TypeError):
        return None


def _parse_location_city(val):
    """Extract CITY_NAME from the 'location' dict column."""
    if pd.isna(val):
        return None
    try:
        if isinstance(val, str):
            d = ast.literal_eval(val)
        else:
            d = val
        return d.get("CITY_NAME", None)
    except (ValueError, SyntaxError, TypeError):
        return None


def _parse_price_string(val):
    """
    Parse formatted price strings like '2.63 Cr', '19.1 L Onwards', '38500000'.
    Returns numeric value in INR.
    """
    if pd.isna(val):
        return None
    val = str(val).strip()

    # Already numeric
    try:
        return float(val)
    except ValueError:
        pass

    # Remove common suffixes
    val_clean = val.lower().replace("onwards", "").replace("rs.", "").replace("rs", "").strip()

    # Match patterns like "3.85 cr" or "19.1 l"
    match = re.match(r"([\d.]+)\s*(cr|crore|l|lakh|lac|k)", val_clean, re.IGNORECASE)
    if match:
        num = float(match.group(1))
        unit = match.group(2).lower()
        if unit in ("cr", "crore"):
            return num * 1_00_00_000
        elif unit in ("l", "lakh", "lac"):
            return num * 1_00_000
        elif unit == "k":
            return num * 1_000

    # Try extracting just the number
    nums = re.findall(r"[\d.]+", val_clean)
    if nums:
        try:
            return float(nums[0])
        except ValueError:
            pass

    return None


def _parse_area_string(val):
    """
    Parse area strings like '3434 sq.ft.', '518-623  sq.ft.'.
    For ranges, returns the midpoint.
    """
    if pd.isna(val):
        return None
    val = str(val).lower().replace(",", "")

    # Range: "518-623 sq.ft."
    range_match = re.match(r"([\d.]+)\s*[-–]\s*([\d.]+)", val)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return (low + high) / 2

    # Single value: "3434 sq.ft."
    single_match = re.match(r"([\d.]+)", val)
    if single_match:
        return float(single_match.group(1))

    return None


def _load_single_csv(filepath: str, fallback_city: str) -> pd.DataFrame:
    """
    Load a single 99acres CSV and normalize it to standard columns.
    """
    print(f"  Loading {os.path.basename(filepath)}...")
    df = pd.read_csv(filepath, low_memory=False)
    original_count = len(df)

    # ── Extract coordinates from MAP_DETAILS ───────────────────────────────
    coords = df["MAP_DETAILS"].apply(_parse_map_details)
    df["latitude"] = coords.apply(lambda x: x[0])
    df["longitude"] = coords.apply(lambda x: x[1])

    # ── Determine locality ─────────────────────────────────────────────────
    if "LOCALITY" in df.columns:
        # Gurgaon format: has LOCALITY column directly
        df["locality"] = df["LOCALITY"]
    elif "location" in df.columns:
        # Mumbai/Hyderabad/Kolkata: locality is inside 'location' dict
        df["locality"] = df["location"].apply(_parse_location_locality)
    elif "LOCALITY_WO_CITY" in df.columns:
        df["locality"] = df["LOCALITY_WO_CITY"]
    else:
        df["locality"] = "Unknown"

    # ── Determine city ─────────────────────────────────────────────────────
    if "CITY" in df.columns:
        df["city"] = df["CITY"]
    elif "location" in df.columns:
        df["city"] = df["location"].apply(_parse_location_city)
        # Fill remaining with fallback
        df["city"] = df["city"].fillna(fallback_city)
    else:
        df["city"] = fallback_city

    # ── Price per sqft ─────────────────────────────────────────────────────
    df["price_per_sqft"] = pd.to_numeric(df["PRICE_SQFT"], errors="coerce")

    # ── Price (numeric) ────────────────────────────────────────────────────
    # Try MIN_PRICE first (usually numeric), fallback to PRICE (formatted)
    if "MIN_PRICE" in df.columns:
        df["price"] = pd.to_numeric(df["MIN_PRICE"], errors="coerce")
    else:
        df["price"] = None

    # Fill gaps from PRICE column (formatted string)
    if "PRICE" in df.columns:
        parsed_prices = df["PRICE"].apply(_parse_price_string)
        df["price"] = df["price"].fillna(parsed_prices)

    # ── Area ───────────────────────────────────────────────────────────────
    if "AREA" in df.columns:
        df["area_sqft"] = df["AREA"].apply(_parse_area_string)
    elif "MIN_AREA_SQFT" in df.columns:
        df["area_sqft"] = pd.to_numeric(df["MIN_AREA_SQFT"], errors="coerce")
    else:
        df["area_sqft"] = None

    # If price_per_sqft is missing, compute from price and area
    mask = df["price_per_sqft"].isna() & df["price"].notna() & df["area_sqft"].notna() & (df["area_sqft"] > 0)
    df.loc[mask, "price_per_sqft"] = df.loc[mask, "price"] / df.loc[mask, "area_sqft"]

    # ── Property type ──────────────────────────────────────────────────────
    df["property_type"] = df.get("PROPERTY_TYPE", pd.Series(["Unknown"] * len(df)))

    # ── Bedrooms ───────────────────────────────────────────────────────────
    if "BEDROOM_NUM" in df.columns:
        df["bedrooms"] = pd.to_numeric(df["BEDROOM_NUM"], errors="coerce")
    else:
        df["bedrooms"] = None

    # ── Transaction type (buy/rent indicator) ──────────────────────────────
    if "TRANSACT_TYPE" in df.columns:
        df["transact_type"] = pd.to_numeric(df["TRANSACT_TYPE"], errors="coerce")
    else:
        df["transact_type"] = 1  # assume sale

    # ── Estimate rent ──────────────────────────────────────────────────────
    # Since there's no direct rent column, estimate monthly rent from price
    city_lower = fallback_city.lower()
    yield_ratio = CITY_YIELD_RATIOS.get(city_lower, CITY_YIELD_RATIOS["default"])
    df["rent"] = (df["price"] * yield_ratio) / 12  # annual yield / 12 months

    # ── Select standard columns ────────────────────────────────────────────
    std_cols = [
        "city", "locality", "price", "price_per_sqft", "rent",
        "latitude", "longitude", "property_type", "bedrooms",
        "area_sqft", "transact_type"
    ]
    result = df[std_cols].copy()

    # ── Basic cleaning ─────────────────────────────────────────────────────
    # Drop rows without coordinates (can't map them)
    result = result.dropna(subset=["latitude", "longitude"])

    # Drop rows without price (can't score them)
    result = result.dropna(subset=["price"])

    # Clamp coordinates to India bounding box
    result = result[
        (result["latitude"].between(8.0, 37.5)) &
        (result["longitude"].between(68.0, 97.5))
    ]

    # Remove obviously bad prices (negative or unreasonably small)
    result = result[result["price"] > 10000]

    # Remove extreme outlier prices (above 200 Cr)
    result = result[result["price"] < 2_000_000_000]

    print(f"    → {len(result)}/{original_count} rows retained after cleaning")
    return result.reset_index(drop=True)


def load_data() -> pd.DataFrame:
    """
    Load and merge all city CSVs into a single cleaned DataFrame.
    Each row = one property listing with standardized columns.
    """
    csv_configs = [
        ("gurgaon_10k.csv", "Gurgaon"),
        ("mumbai.csv", "Mumbai"),
        ("hyderabad.csv", "Hyderabad"),
        ("kolkata.csv", "Kolkata"),
    ]

    frames = []
    for filename, city in csv_configs:
        filepath = os.path.join(ARCHIVE_DIR, filename)
        if os.path.exists(filepath):
            try:
                df = _load_single_csv(filepath, city)
                frames.append(df)
            except Exception as e:
                print(f"  ⚠ Error loading {filename}: {e}")
        else:
            print(f"  ⚠ File not found: {filepath}")

    if not frames:
        raise FileNotFoundError(
            f"No CSV files found in {ARCHIVE_DIR}. "
            "Please place the 99acres CSV files there."
        )

    combined = pd.concat(frames, ignore_index=True)

    # Fill remaining NaN values in numeric columns with column median
    for col in ["price", "price_per_sqft", "rent"]:
        if col in combined.columns:
            combined[col] = combined[col].fillna(combined[col].median())

    print(f"\n✓ Total loaded: {len(combined)} listings across {combined['city'].nunique()} cities")
    return combined


def aggregate_by_locality(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group individual listings into locality-level summaries.
    Each row = one locality zone with aggregated metrics.
    """
    agg = df.groupby(["locality", "city"], as_index=False).agg(
        listing_count=("price", "count"),
        avg_price=("price", "mean"),
        avg_price_per_sqft=("price_per_sqft", "mean"),
        avg_rent=("rent", "mean"),
        latitude=("latitude", "mean"),
        longitude=("longitude", "mean"),
        avg_area=("area_sqft", "mean"),
        avg_bedrooms=("bedrooms", "mean"),
    )

    # Filter out localities with too few listings (noise)
    agg = agg[agg["listing_count"] >= 3]

    # Rental yield = annual rent / price (higher = undervalued)
    agg["rental_yield"] = (agg["avg_rent"] * 12) / agg["avg_price"]

    # Price momentum: z-score of price_per_sqft across all localities
    mean_psf = agg["avg_price_per_sqft"].mean()
    std_psf = agg["avg_price_per_sqft"].std()
    agg["price_momentum"] = (agg["avg_price_per_sqft"] - mean_psf) / (std_psf + 1e-9)

    print(f"✓ Aggregated into {len(agg)} locality zones")
    return agg.reset_index(drop=True)
