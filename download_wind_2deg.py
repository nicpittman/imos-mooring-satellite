#!/usr/bin/env python3
"""
Download Wind - NCEP Reanalysis (~2 deg, daily means from 6-hourly)
Downloads year by year, saves incrementally.
"""

from config import (
    os, np, pd, xr,
    LOCATIONS, START, END, get_output_path
)

URL_U = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/surface_gauss/uwnd.10m.gauss.{year}.nc"
URL_V = "https://psl.noaa.gov/thredds/dodsC/Datasets/ncep.reanalysis/surface_gauss/vwnd.10m.gauss.{year}.nc"


def download_wind(name, lat, lon):
    print(f"  {name} ({lat}, {lon})")

    out_path = get_output_path(name, "wind")
    lon_360 = lon if lon >= 0 else lon + 360
    start_year = int(START[:4])
    end_year = int(END[:4])

    # Load existing data if any
    if os.path.exists(out_path):
        existing = pd.read_csv(out_path, index_col="time", parse_dates=True)
        print(f"    Existing: {len(existing)} days", flush=True)
    else:
        existing = pd.DataFrame()

    for year in range(start_year, end_year + 1):
        # Skip if we have this year
        if len(existing) > 0:
            year_data = existing[existing.index.year == year]
            if len(year_data) > 350:
                print(f"    {year}: skipping (have {len(year_data)} days)", flush=True)
                continue

        print(f"    {year}...", end=" ", flush=True)
        try:
            u_ds = xr.open_dataset(URL_U.format(year=year))
            v_ds = xr.open_dataset(URL_V.format(year=year))

            u_ds = u_ds.sel(lat=lat, lon=lon_360, method="nearest")
            v_ds = v_ds.sel(lat=lat, lon=lon_360, method="nearest")

            u = u_ds["uwnd"].load()
            v = v_ds["vwnd"].load()

            # Create dataframe with u/v components
            df = pd.DataFrame({
                "time": u.time.values,
                "u": u.values,
                "v": v.values,
            }).set_index("time")

            # Resample to daily means of u/v components (correct for vector averaging)
            df = df.resample("D").mean()

            # Compute speed and direction from daily mean vectors
            df["wind_speed"] = np.sqrt(df["u"]**2 + df["v"]**2)
            df["wind_direction"] = (270 - np.degrees(np.arctan2(df["v"], df["u"]))) % 360
            df = df[["wind_speed", "wind_direction"]]

            # Normalize timestamps to midnight UTC
            df.index = df.index.normalize()

            # Merge and save
            existing = pd.concat([existing, df])
            existing = existing[~existing.index.duplicated(keep='last')].sort_index()
            existing.to_csv(out_path)

            print(f"{len(df)} days", flush=True)

        except Exception as e:
            print(f"FAILED: {e}", flush=True)

    print(f"    Total: {len(existing)} days -> {out_path}")


if __name__ == "__main__":
    print("Downloading Wind (NCEP Reanalysis, daily)")
    print("=" * 50)

    for name, lat, lon in LOCATIONS:
        try:
            download_wind(name, lat, lon)
        except Exception as e:
            print(f"  {name}... FAILED: {e}")

    print("\nDone!")
