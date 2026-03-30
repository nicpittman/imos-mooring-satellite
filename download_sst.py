#!/usr/bin/env python3
"""
Download SST - NOAA OISST v2.1 (0.25 deg, daily)
Downloads month by month, saves incrementally.
"""

from config import (
    os, time, tempfile, requests, pd, xr,
    LOCATIONS, START, END, get_output_path
)

URL = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg_LonPM180.nc"


def download_sst(name, lat, lon):
    print(f"\n  {name} ({lat}, {lon})")

    out_path = get_output_path(name, "sst")
    lat_lo, lat_hi = lat - 0.15, lat + 0.15
    lon_lo, lon_hi = lon - 0.15, lon + 0.15
    failed_months = []

    # Load existing data if any
    if os.path.exists(out_path):
        existing = pd.read_csv(out_path, index_col="time", parse_dates=True)
        print(f"    Existing: {len(existing)} days", flush=True)
    else:
        existing = pd.DataFrame()

    # Generate month list
    months = pd.date_range(START, END, freq="MS")

    for month_start in months:
        month_end = month_start + pd.offsets.MonthEnd(0)
        month_str = month_start.strftime("%Y-%m")

        # Skip if we have this month
        if len(existing) > 0:
            month_data = existing[(existing.index >= month_start) & (existing.index <= month_end)]
            if len(month_data) > 25:
                continue

        print(f"    {month_str}...", end=" ", flush=True)

        success = False
        for attempt in range(3):
            try:
                query = f"?sst[({month_start.date()}):1:({month_end.date()})][(0.0):1:(0.0)][({lat_lo}):1:({lat_hi})][({lon_lo}):1:({lon_hi})]"
                response = requests.get(URL + query, timeout=(30, 120))  # (connect, read) timeout
                response.raise_for_status()

                with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
                    f.write(response.content)
                    path = f.name

                ds = xr.open_dataset(path).load()
                os.unlink(path)

                sst = ds["sst"].sel(latitude=lat, longitude=lon, method="nearest")
                if "zlev" in sst.dims:
                    sst = sst.isel(zlev=0)

                df = sst.to_dataframe().reset_index()[["time", "sst"]]
                df = df.set_index("time")

                # Normalize timestamps to midnight UTC
                df.index = df.index.normalize()

                # Merge and save
                existing = pd.concat([existing, df])
                existing = existing[~existing.index.duplicated(keep='last')].sort_index()
                existing.to_csv(out_path)

                print(f"{len(df)} days", flush=True)
                success = True
                break

            except Exception as e:
                if attempt < 2:
                    print(f"retry({attempt+1})...", end=" ", flush=True)
                    time.sleep(3)
                else:
                    print(f"FAILED", flush=True)

        if not success:
            failed_months.append(month_str)

    print(f"    Total: {len(existing)} days")
    if failed_months:
        print(f"    FAILED MONTHS: {', '.join(failed_months)}")
    return failed_months


if __name__ == "__main__":
    print("Downloading SST (NOAA OISST v2.1, daily)")
    print("=" * 50)

    all_failed = {}

    for name, lat, lon in LOCATIONS:
        try:
            failed = download_sst(name, lat, lon)
            if failed:
                all_failed[name] = failed
        except Exception as e:
            print(f"  {name}... FAILED: {e}")
            all_failed[name] = ["ALL"]

    print("\n" + "=" * 50)
    if all_failed:
        print("FAILED DOWNLOADS (re-run to retry):")
        for loc, months in all_failed.items():
            print(f"  {loc}: {', '.join(months)}")
    else:
        print("All downloads complete!")
    print("=" * 50)
