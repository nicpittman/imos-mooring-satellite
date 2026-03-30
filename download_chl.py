#!/usr/bin/env python3
"""
Download Chlorophyll - ESA OC-CCI v6.0 (4km, daily)
Downloads month by month, saves incrementally.
"""

from config import (
    os, time, pd, xr,
    LOCATIONS, START, END, get_output_path
)

URL = "https://rsg.pml.ac.uk/thredds/dodsC/CCI_ALL-v6.0-DAILY"


def download_chl(ds, name, lat, lon, months):
    """Download CHL for a single location."""
    print(f"\n  {name} ({lat}, {lon})")

    out_path = get_output_path(name, "chl")
    failed_months = []

    # Load existing
    if os.path.exists(out_path):
        existing = pd.read_csv(out_path, index_col="time", parse_dates=True)
        print(f"    Existing: {len(existing)} days", flush=True)
    else:
        existing = pd.DataFrame()

    ds_loc = ds.sel(lat=lat, lon=lon, method="nearest")

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
                month_ds = ds_loc.sel(time=slice(str(month_start.date()), str(month_end.date())))
                chl = month_ds["chlor_a"].load()

                df = chl.to_dataframe().reset_index()[["time", "chlor_a"]]
                df = df.rename(columns={"chlor_a": "chl"})
                df = df.set_index("time")

                # Normalize timestamps to midnight UTC
                df.index = df.index.normalize()

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
    print("Downloading Chlorophyll (ESA OC-CCI v6.0, daily)")
    print("=" * 50)

    months = pd.date_range(START, END, freq="MS")
    all_failed = {}

    # Try to open dataset with retries
    ds = None
    for attempt in range(5):
        try:
            print(f"Opening dataset... ", end="", flush=True)
            ds = xr.open_dataset(URL)
            print("OK")
            break
        except Exception as e:
            if attempt < 4:
                print(f"retry({attempt+1})...", end=" ", flush=True)
                time.sleep(5)
            else:
                print(f"\nFAILED to open dataset: {e}")
                print("Server may be down. Try again later.")
                exit(1)

    for name, lat, lon in LOCATIONS:
        try:
            failed = download_chl(ds, name, lat, lon, months)
            if failed:
                all_failed[name] = failed
        except Exception as e:
            print(f"  {name}... FAILED: {e}")
            all_failed[name] = ["ALL"]

    print("\n" + "=" * 50)
    if all_failed:
        print("FAILED DOWNLOADS (re-run to retry):")
        for loc, months_failed in all_failed.items():
            print(f"  {loc}: {', '.join(months_failed)}")
    else:
        print("All downloads complete!")
    print("=" * 50)
