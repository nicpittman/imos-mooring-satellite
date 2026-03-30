#!/usr/bin/env python3
"""
Generate a map of IMOS reference station locations. Requires Cartopy
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.colors import Normalize
from config import LOCATIONS, get_output_path

def plot_station_map():
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

    # Set extent to Australia
    ax.set_extent([110, 160, -45, -8], crs=ccrs.PlateCarree())

    # Add features
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='lightblue')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
    ax.add_feature(cfeature.STATES, linewidth=0.3, edgecolor='gray')

    # Load mean CHL for each station
    chl_means = {}
    for name, lat, lon in LOCATIONS:
        chl_path = get_output_path(name, "chl")
        if os.path.exists(chl_path):
            df = pd.read_csv(chl_path, index_col="time", parse_dates=True)
            chl_means[name] = df["chl"].mean()
        else:
            chl_means[name] = np.nan

    # Set up colormap
    valid_chl = [v for v in chl_means.values() if not np.isnan(v)]
    if valid_chl:
        vmin, vmax = min(valid_chl), max(valid_chl)
    else:
        vmin, vmax = 0, 1
    norm = Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.YlGn

    # Plot stations colored by CHL
    for name, lat, lon in LOCATIONS:
        chl = chl_means.get(name, np.nan)
        if np.isnan(chl):
            color = 'gray'
        else:
            color = cmap(norm(chl))
        ax.plot(lon, lat, 'o', markersize=12, color=color,
                markeredgecolor='black', markeredgewidth=0.5,
                transform=ccrs.PlateCarree())

        # Offset labels to avoid overlap
        x_offset = 0.5
        y_offset = 0.5

        # Adjust offsets for specific stations
        if name == "darwin":
            y_offset = -1.2
        elif name == "yongala":
            x_offset = 1
        elif name == "north_stradbroke":
            x_offset = -5
            y_offset = -0.5
        elif name == "port_hacking":
            x_offset = 1
        elif name == "maria_island":
            x_offset = 1
        elif name == "bonney_coast":
            y_offset = -1

        label = name.replace("_", " ").title()
        ax.text(lon + x_offset, lat + y_offset, label,
                fontsize=9, transform=ccrs.PlateCarree())

    # Add gridlines
    gl = ax.gridlines(draw_labels=True, linewidth=0.5, alpha=0.5)
    gl.top_labels = False
    gl.right_labels = False

    ax.set_title("IMOS National Reference Stations\nColored by Mean Chlorophyll-a (mg/m³)", fontsize=14, fontweight='bold')

    # Add colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, orientation='horizontal', pad=0.05, shrink=0.6)
    cbar.set_label('Mean Chlorophyll-a (mg/m³)', fontsize=10)

    plt.tight_layout()
    plt.savefig("charts/station_map.png", dpi=150, bbox_inches='tight')
    print("Saved charts/station_map.png")
    plt.close()


if __name__ == "__main__":
    plot_station_map()
