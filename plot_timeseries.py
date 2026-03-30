#!/usr/bin/env python3
"""
Plot time series for all downloaded ocean variables.
Saves charts to charts/{location}/
"""

from config import (
    os, np, pd, plt, mdates,
    LOCATIONS, OUTPUT_DIR
)

CHART_DIR = "charts"

# Variable configs: (filename_pattern, column, label, color, unit)
VARIABLES = {
    "sst": ("sst_daily_0.25deg.csv", "sst", "Sea Surface Temperature", "#e63946", "°C"),
    "chl": ("chl_daily_4km.csv", "chl", "Chlorophyll-a", "#2a9d8f", "mg/m³"),
    "npp": ("npp_8day_4km.csv", "npp", "Net Primary Production", "#e9c46a", "mg C/m²/day"),
    "wind_speed_era5": ("wind_era5_daily_0.25deg.csv", "wind_speed", "Wind Speed (ERA5 0.25°)", "#457b9d", "m/s"),
    "wind_dir_era5": ("wind_era5_daily_0.25deg.csv", "wind_direction", "Wind Direction (ERA5 0.25°)", "#1d3557", "°"),
    "wind_speed_ncep": ("wind_daily_2deg.csv", "wind_speed", "Wind Speed (NCEP 2°)", "#7eb77f", "m/s"),
    "wind_dir_ncep": ("wind_daily_2deg.csv", "wind_direction", "Wind Direction (NCEP 2°)", "#3d5a3d", "°"),
    "mld": ("mld_daily_0.08deg.csv", "mld", "Mixed Layer Depth", "#6a4c93", "m"),
}


def format_time_axis(ax, df):
    """Format time axis based on data range."""
    if df is None or df.empty:
        return

    date_range = (df.index.max() - df.index.min()).days

    if date_range > 365 * 10:  # > 10 years
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    elif date_range > 365 * 3:  # > 3 years
        ax.xaxis.set_major_locator(mdates.YearLocator(1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    elif date_range > 365:  # > 1 year
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    else:  # < 1 year
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

    ax.set_xlim(df.index.min(), df.index.max())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")


def load_data(location, filename):
    """Load CSV data for a location."""
    path = os.path.join(OUTPUT_DIR, location, filename)
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, index_col="time", parse_dates=True)
    return df


def plot_single_variable(df, col, label, color, unit, title, coords, out_path, is_direction=False):
    """Plot a single variable time series."""
    fig, ax = plt.subplots(figsize=(12, 4))

    # Raw data
    ax.plot(df.index, df[col], color=color, linewidth=0.4, alpha=0.4, label="Daily")

    # Skip rolling mean for wind direction (circular averaging not valid)
    if not is_direction:
        # 90-day rolling nanmean with interpolation to fill remaining gaps
        rolling = df[col].rolling(window=90, center=True, min_periods=20).mean()
        was_nan = rolling.isna()  # track gaps before interpolation
        rolling = rolling.interpolate(method="linear", limit=90)  # bridge gaps up to ~3 months

        # Plot real data solid, interpolated sections as gray dashed (tight dashes)
        rolling_real = rolling.where(~was_nan)
        rolling_interp = rolling.where(was_nan | was_nan.shift(-1) | was_nan.shift(1))  # include edges
        ax.plot(df.index, rolling_real, color=color, linewidth=2, label="90-day mean")
        if rolling_interp.notna().any():
            ax.plot(df.index, rolling_interp, color="gray", linewidth=2, linestyle=(0, (2, 1)), label="interpolated")

    ax.set_ylabel(f"{label} ({unit})")
    ax.set_title(f"{title}\n({coords})", fontsize=11, fontweight="bold")
    ax.legend(loc="upper right", framealpha=0.9, fontsize=9)
    ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)

    # Format time axis
    format_time_axis(ax, df)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_overview(location, coords, data_dict, out_path):
    """Plot all variables in a single overview figure."""
    # Filter to variables that have data
    available = {k: v for k, v in data_dict.items() if v is not None and not v.empty}

    if not available:
        return

    n_vars = len(available)
    fig, axes = plt.subplots(n_vars, 1, figsize=(14, 2.5 * n_vars), sharex=True)

    if n_vars == 1:
        axes = [axes]

    # Find overall date range for consistent x-axis
    all_dates = pd.concat([df for df in available.values()])
    date_min, date_max = all_dates.index.min(), all_dates.index.max()

    for ax, (var_key, df) in zip(axes, available.items()):
        cfg = VARIABLES[var_key]
        col, label, color, unit = cfg[1], cfg[2], cfg[3], cfg[4]
        is_direction = "wind_dir" in var_key

        # Plot raw data
        ax.plot(df.index, df[col], color=color, linewidth=0.3, alpha=0.35)

        # Skip rolling mean for wind direction (circular averaging not valid)
        if not is_direction:
            # 90-day rolling nanmean with interpolation
            rolling = df[col].rolling(window=90, center=True, min_periods=20).mean()
            was_nan = rolling.isna()
            rolling = rolling.interpolate(method="linear", limit=90)

            # Plot real data solid, interpolated sections as gray dashed (tight dashes)
            rolling_real = rolling.where(~was_nan)
            rolling_interp = rolling.where(was_nan | was_nan.shift(-1) | was_nan.shift(1))
            ax.plot(df.index, rolling_real, color=color, linewidth=1.8)
            if rolling_interp.notna().any():
                ax.plot(df.index, rolling_interp, color="gray", linewidth=1.6, linestyle=(0, (2, 1)))

        ax.set_ylabel(f"{label}\n({unit})", fontsize=9)
        ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
        ax.set_xlim(date_min, date_max)

        # Invert MLD axis (deeper = down)
        if var_key == "mld":
            ax.invert_yaxis()

    # Format bottom axis
    format_time_axis(axes[-1], all_dates)

    fig.suptitle(f"{location.replace('_', ' ').title()} ({coords})", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_seasonal_cycle(location, coords, data_dict, out_path):
    """Plot seasonal climatology for each variable."""
    available = {k: v for k, v in data_dict.items() if v is not None and not v.empty}

    if not available:
        return

    n_vars = len(available)
    fig, axes = plt.subplots(1, n_vars, figsize=(3 * n_vars, 4))

    if n_vars == 1:
        axes = [axes]

    months = list(range(1, 13))
    month_labels = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]

    # Get date range for subtitle
    all_dates = pd.concat([df for df in available.values()])
    year_range = f"{all_dates.index.min().year}-{all_dates.index.max().year}"

    for ax, (var_key, df) in zip(axes, available.items()):
        cfg = VARIABLES[var_key]
        col, label, color, unit = cfg[1], cfg[2], cfg[3], cfg[4]

        # Calculate monthly climatology
        monthly_clim = df[col].groupby(df.index.month).agg(["mean", "std"])

        # Reindex to ensure all 12 months present
        monthly_clim = monthly_clim.reindex(range(1, 13))

        # Plot with error band (±1 std dev)
        mean_vals = monthly_clim["mean"].values
        std_vals = monthly_clim["std"].fillna(0).values

        ax.fill_between(months, mean_vals - std_vals, mean_vals + std_vals,
                        color=color, alpha=0.25, label="±1 σ")
        ax.plot(months, mean_vals, color=color, linewidth=2.5, marker="o",
                markersize=5, markerfacecolor="white", markeredgewidth=2)

        ax.set_xlabel("Month", fontsize=9)
        ax.set_ylabel(f"{unit}", fontsize=9)
        ax.set_title(label, fontsize=10, fontweight="bold")
        ax.set_xticks(months)
        ax.set_xticklabels(month_labels)
        ax.set_xlim(0.5, 12.5)
        ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)

        if var_key == "mld":
            ax.invert_yaxis()

    fig.suptitle(f"{location.replace('_', ' ').title()} ({coords}) - Seasonal Cycles ({year_range})",
                 fontsize=11, fontweight="bold")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_location(name, lat, lon):
    """Generate all plots for a single location."""
    print(f"\n  {name}")

    # Format coordinates string
    lat_str = f"{abs(lat):.2f}°{'S' if lat < 0 else 'N'}"
    lon_str = f"{abs(lon):.2f}°{'E' if lon > 0 else 'W'}"
    coords = f"{lat_str}, {lon_str}"

    # Create output directory
    chart_dir = os.path.join(CHART_DIR, name)
    os.makedirs(chart_dir, exist_ok=True)

    # Load all data
    data_dict = {}
    for var_key, cfg in VARIABLES.items():
        filename = cfg[0]
        col = cfg[1]
        df = load_data(name, filename)
        if df is not None and col in df.columns:
            data_dict[var_key] = df
            print(f"    {var_key}: {len(df)} days")
        else:
            data_dict[var_key] = None

    if all(v is None for v in data_dict.values()):
        print("    No data found!")
        return

    # Individual variable plots
    for var_key, df in data_dict.items():
        if df is None:
            continue
        cfg = VARIABLES[var_key]
        col, label, color, unit = cfg[1], cfg[2], cfg[3], cfg[4]
        out_path = os.path.join(chart_dir, f"{var_key}.png")
        title = f"{name.replace('_', ' ').title()} - {label}"
        # Skip rolling mean for wind direction (circular averaging not valid)
        is_direction = "wind_dir" in var_key
        plot_single_variable(df, col, label, color, unit, title, coords, out_path, is_direction=is_direction)

    # Overview plot
    plot_overview(name, coords, data_dict, os.path.join(chart_dir, "overview.png"))
    print(f"    -> overview.png")

    # Seasonal cycle plot
    plot_seasonal_cycle(name, coords, data_dict, os.path.join(chart_dir, "seasonal.png"))
    print(f"    -> seasonal.png")

    # Wind comparison plot (ERA5 vs NCEP)
    if plot_wind_comparison(name, coords, os.path.join(chart_dir, "wind_comparison.png")):
        print(f"    -> wind_comparison.png")


def plot_cross_region_timeseries(var_key, all_data, out_path):
    """Plot a single variable across all locations."""
    cfg = VARIABLES[var_key]
    col, label, _, unit = cfg[1], cfg[2], cfg[3], cfg[4]

    # Sort locations by latitude (north to south)
    locations_sorted = sorted(all_data.keys(), key=lambda x: all_data[x]["lat"], reverse=True)

    fig, ax = plt.subplots(figsize=(14, 6))

    # Color palette for locations
    colors = plt.cm.viridis(np.linspace(0, 0.9, len(locations_sorted)))

    is_direction = "wind_dir" in var_key

    for i, loc in enumerate(locations_sorted):
        df = all_data[loc].get(var_key)
        if df is None or df.empty:
            continue

        lat = all_data[loc]["lat"]
        loc_label = f"{loc.replace('_', ' ').title()} ({lat:.1f}°)"

        # Skip rolling mean for wind direction (circular averaging not valid)
        if is_direction:
            ax.plot(df.index, df[col], color=colors[i], linewidth=0.4, alpha=0.6, label=loc_label)
        else:
            # 90-day rolling mean
            rolling = df[col].rolling(window=90, center=True, min_periods=20).mean()
            rolling = rolling.interpolate(method="linear", limit=90)
            ax.plot(df.index, rolling, color=colors[i], linewidth=1.5, label=loc_label, alpha=0.85)

    ax.set_ylabel(f"{label} ({unit})")
    ax.set_title(f"{label} - All Locations", fontsize=12, fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, ncol=2, framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)

    # Format time axis
    if locations_sorted:
        first_loc = locations_sorted[0]
        df = all_data[first_loc].get(var_key)
        if df is not None:
            format_time_axis(ax, df)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_cross_region_seasonal_heatmap(var_key, all_data, out_path):
    """Plot seasonal heatmap across all locations."""
    cfg = VARIABLES[var_key]
    col, label, _, unit = cfg[1], cfg[2], cfg[3], cfg[4]

    # Sort locations by latitude (north to south)
    locations_sorted = sorted(all_data.keys(), key=lambda x: all_data[x]["lat"], reverse=True)

    # Build climatology matrix
    clim_data = []
    loc_labels = []

    for loc in locations_sorted:
        df = all_data[loc].get(var_key)
        if df is None or df.empty:
            continue

        lat = all_data[loc]["lat"]
        monthly_mean = df[col].groupby(df.index.month).mean()
        monthly_mean = monthly_mean.reindex(range(1, 13))
        clim_data.append(monthly_mean.values)
        loc_labels.append(f"{loc.replace('_', ' ').title()} ({lat:.1f}°)")

    if not clim_data:
        return

    clim_matrix = np.array(clim_data)

    fig, ax = plt.subplots(figsize=(12, max(4, len(loc_labels) * 0.6)))

    # Heatmap
    im = ax.imshow(clim_matrix, aspect="auto", cmap="viridis")

    # Labels
    month_labels = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    ax.set_xticks(range(12))
    ax.set_xticklabels(month_labels)
    ax.set_yticks(range(len(loc_labels)))
    ax.set_yticklabels(loc_labels)

    ax.set_xlabel("Month")
    ax.set_title(f"{label} - Seasonal Climatology ({unit})", fontsize=12, fontweight="bold")

    # Colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label(unit)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_wind_comparison(name, coords, out_path):
    """Plot ERA5 vs NCEP wind comparison for a location."""
    # Load both wind datasets
    era5_df = load_data(name, "wind_era5_daily_0.25deg.csv")
    ncep_df = load_data(name, "wind_daily_2deg.csv")

    if era5_df is None and ncep_df is None:
        return False

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Wind Speed comparison
    ax = axes[0]
    if era5_df is not None and "wind_speed" in era5_df.columns:
        rolling = era5_df["wind_speed"].rolling(window=90, center=True, min_periods=20).mean()
        rolling = rolling.interpolate(method="linear", limit=90)
        ax.plot(era5_df.index, rolling, color="#457b9d", linewidth=1.8, label="ERA5 (0.25°)")

    if ncep_df is not None and "wind_speed" in ncep_df.columns:
        rolling = ncep_df["wind_speed"].rolling(window=90, center=True, min_periods=20).mean()
        rolling = rolling.interpolate(method="linear", limit=90)
        ax.plot(ncep_df.index, rolling, color="#7eb77f", linewidth=1.8, label="NCEP (2°)")

    ax.set_ylabel("Wind Speed (m/s)")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)
    ax.set_title(f"{name.replace('_', ' ').title()} ({coords}) - Wind Product Comparison", fontsize=12, fontweight="bold")

    # Wind Direction comparison (raw data only - rolling mean not valid for circular data)
    ax = axes[1]
    if era5_df is not None and "wind_direction" in era5_df.columns:
        ax.plot(era5_df.index, era5_df["wind_direction"], color="#1d3557", linewidth=0.4, alpha=0.6, label="ERA5 (0.25°)")

    if ncep_df is not None and "wind_direction" in ncep_df.columns:
        ax.plot(ncep_df.index, ncep_df["wind_direction"], color="#3d5a3d", linewidth=0.4, alpha=0.6, label="NCEP (2°)")

    ax.set_ylabel("Wind Direction (°)")
    ax.set_ylim(0, 360)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.5)

    # Format time axis on bottom
    ref_df = era5_df if era5_df is not None else ncep_df
    format_time_axis(axes[-1], ref_df)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return True


def plot_cross_region(all_data):
    """Generate all cross-region comparison plots."""
    print("\n  Cross-region plots")

    cross_dir = os.path.join(CHART_DIR, "cross_region")
    os.makedirs(cross_dir, exist_ok=True)

    for var_key in VARIABLES:
        # Check if any location has this variable
        has_data = any(
            all_data[loc].get(var_key) is not None and not all_data[loc].get(var_key).empty
            for loc in all_data
        )
        if not has_data:
            continue

        # Time series comparison
        out_path = os.path.join(cross_dir, f"{var_key}_comparison.png")
        plot_cross_region_timeseries(var_key, all_data, out_path)
        print(f"    -> {var_key}_comparison.png")

        # Seasonal heatmap
        out_path = os.path.join(cross_dir, f"{var_key}_seasonal_heatmap.png")
        plot_cross_region_seasonal_heatmap(var_key, all_data, out_path)
        print(f"    -> {var_key}_seasonal_heatmap.png")


if __name__ == "__main__":
    print("Generating plots")
    print("=" * 50)

    # Collect all data for cross-region plots
    all_data = {}

    for name, lat, lon in LOCATIONS:
        try:
            plot_location(name, lat, lon)

            # Also collect data for cross-region plots
            all_data[name] = {"lat": lat, "lon": lon}
            for var_key, cfg in VARIABLES.items():
                filename = cfg[0]
                col = cfg[1]
                df = load_data(name, filename)
                if df is not None and col in df.columns:
                    all_data[name][var_key] = df
                else:
                    all_data[name][var_key] = None

        except Exception as e:
            print(f"  {name}... FAILED: {e}")

    # Generate cross-region comparison plots
    try:
        plot_cross_region(all_data)
    except Exception as e:
        print(f"  Cross-region plots FAILED: {e}")

    print("\n" + "=" * 50)
    print(f"Charts saved to {CHART_DIR}/")
