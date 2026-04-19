"""
govt_data.py — Government Infrastructure Data Handler

Loads government/municipal infrastructure project data from JSON.
In production, this would be scraped from municipal corporation portals.
"""

import json
import os
import pandas as pd

GOVT_PATH = os.path.join(os.path.dirname(__file__), "../data/govt_projects.json")


def load_govt_data() -> pd.DataFrame:
    """
    Load government infrastructure project data.
    In production this would be scraped from municipal portals.
    For now it reads from the local JSON mock file.
    """
    if not os.path.exists(GOVT_PATH):
        print("⚠ No govt_projects.json found. Government signals will be zero.")
        return pd.DataFrame(columns=[
            "name", "type", "city", "latitude", "longitude",
            "signal_weight", "status", "horizon_months", "description"
        ])

    with open(GOVT_PATH, "r") as f:
        projects = json.load(f)

    df = pd.DataFrame(projects)
    print(f"✓ Loaded {len(df)} government infrastructure projects")
    return df
