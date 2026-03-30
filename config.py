"""
Configuration for ocean data downloads.
All common imports are centralized here.
"""

# Standard library
import os
import sys
import time
import tempfile
import subprocess

# Data processing
import numpy as np
import pandas as pd
import xarray as xr
import requests

# Plotting
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Time range
START = "2005-01-01"
END = "2025-01-01"

# Output directory
OUTPUT_DIR = "data"

# NPP temporal resolution: "8day" (reliable) or "daily" (may be slow/unavailable)
NPP_RESOLUTION = "8day"

# Locations: (name, lat, lon) - IMOS National Reference Stations
LOCATIONS = [
    ("maria_island", -42.597, 148.233),       # Tasmania (NRSMAI)
    ("bonney_coast", -38.409, 141.271),       # Victoria (VBM100) - newest
    ("kangaroo_island", -35.833, 136.447),    # South Australia (NRSKAI)
    ("port_hacking", -34.116, 151.219),       # NSW (NRSPHB)
    ("rottnest_island", -31.987, 115.417),    # Western Australia (NRSROT)
    ("north_stradbroke", -27.340, 153.562),   # Queensland (NRSNSI)
    ("yongala", -19.305, 147.622),            # Queensland/GBR (NRSYON)
    ("darwin", -12.338, 130.696),             # Northern Territory (NRSDAR)
]

# Dataset info: (variable, temporal_res, spatial_res)
DATASET_INFO = {
    "sst": ("daily", "0.25deg"),
    "chl": ("daily", "4km"),
    "npp": (NPP_RESOLUTION, "4km"),
    "wind": ("daily", "2deg"),
    "wind_era5": ("daily", "0.25deg"),
    "mld": ("daily", "0.08deg"),
}


def get_output_path(location_name, variable):
    """Get output path for a variable at a location with resolution in filename."""
    loc_dir = os.path.join(OUTPUT_DIR, location_name)
    os.makedirs(loc_dir, exist_ok=True)

    if variable in DATASET_INFO:
        temp_res, spat_res = DATASET_INFO[variable]
        filename = f"{variable}_{temp_res}_{spat_res}.csv"
    else:
        filename = f"{variable}.csv"

    return os.path.join(loc_dir, filename)


# Valid physical ranges for data validation
VALID_RANGES = {
    'sst': (-2, 35),       # Celsius
    'chl': (0.001, 100),   # mg/m3
    'npp': (0, 10000),     # mg C/m2/day
    'wind_speed': (0, 50), # m/s
    'mld': (1, 500),       # meters
}


def validate_data(df, var_name):
    """Validate data values are within physical ranges. Sets invalid values to NaN."""
    if var_name not in VALID_RANGES:
        return df

    lo, hi = VALID_RANGES[var_name]
    col = var_name if var_name in df.columns else df.columns[0]

    invalid = (df[col] < lo) | (df[col] > hi)
    n_invalid = invalid.sum()
    if n_invalid > 0:
        print(f"  WARNING: {n_invalid} values outside valid range [{lo}, {hi}], set to NaN")
        df.loc[invalid, col] = np.nan

    return df
