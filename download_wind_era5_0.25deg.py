#!/usr/bin/env python3
"""
Download Wind (ERA5) - ECMWF ERA5 Reanalysis (0.25 deg, hourly -> daily)
Higher resolution alternative to NCEP.
Downloads month by month, saves incrementally.
"""

from config import (
    os, time, np, pd, xr,
    LOCATIONS, START, END, get_output_path
)

# ERA5 from UCAR RDA - organized by year/month
# 10m u-wind and v-wind
URL_U = "https://thredds.rda.ucar.edu/thredds/dodsC/files/g/d633000/e5.oper.an.sfc/{ym}/e5.oper.an.sfc.128_165_10u.ll025sc.{ym}0100_{ym_end}23.nc"
URL_V = "https://thredds.rda.ucar.edu/thredds/dodsC/files/g/d633000/e5.oper.an.sfc/{ym}/e5.oper.an.sfc.128_166_10v.ll025sc.{ym}0100_{ym_end}23.nc"


def get_month_end(year, month):
    """Get last day of month as YYYYMMDD string."""
    if month == 12:
        next_month = pd.Timestamp(f"{year+1}-01-01")
    else:
        next_month = pd.Timestamp(f"{year}-{month+1:02d}-01")
    last_day = next_month - pd.Timedelta(days=1)
    return last_day.strftime("%Y%m%d")


def download_wind_era5(name, lat, lon):
    print(f"\n  {name} ({lat}, {lon})")

    out_path = get_output_path(name, "wind_era5")
    failed_months = []

    # Load existing
    if os.path.exists(out_path):
        existing = pd.read_csv(out_path, index_col="time", parse_dates=True)
        print(f"    Existing: {len(existing)} days", flush=True)
    else:
        existing = pd.DataFrame()

    # Generate month list
    months = pd.date_range(START, END, freq="MS")

    for month_start in months:
        year = month_start.year
        month = month_start.month
        month_end = month_start + pd.offsets.MonthEnd(0)
        month_str = month_start.strftime("%Y-%m")
        ym = month_start.strftime("%Y%m")
        ym_end = get_month_end(year, month)

        # Skip if we have this month
        if len(existing) > 0:
            month_data = existing[(existing.index >= month_start) & (existing.index <= month_end)]
            if len(month_data) > 25:
                continue

        print(f"    {month_str}...", end=" ", flush=True)

        success = False
        for attempt in range(5):
            try:
                # Build URLs for this month
                u_url = URL_U.format(ym=ym, ym_end=ym_end)
                v_url = URL_V.format(ym=ym, ym_end=ym_end)

                # Open and select location
                u_ds = xr.open_dataset(u_url)
                v_ds = xr.open_dataset(v_url)

                # ERA5 uses 0-360 longitude
                lon_360 = lon if lon >= 0 else lon + 360

                u_ds = u_ds.sel(latitude=lat, longitude=lon_360, method="nearest")
                v_ds = v_ds.sel(latitude=lat, longitude=lon_360, method="nearest")

                # Load data
                u = u_ds["VAR_10U"].load()
                v = v_ds["VAR_10V"].load()

                # Create dataframe with hourly u/v components
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
                success = True
                break

            except Exception as e:
                if attempt < 4:
                    print(f"retry({attempt+1})...", end=" ", flush=True)
                    time.sleep(10 * (attempt + 1))  # Longer delays: 10, 20, 30, 40s
                else:
                    print(f"FAILED", flush=True)

        if not success:
            failed_months.append(month_str)

    print(f"    Total: {len(existing)} days")
    if failed_months:
        print(f"    FAILED MONTHS: {', '.join(failed_months)}")
    return failed_months


if __name__ == "__main__":
    print("Downloading Wind (ERA5, 0.25 deg, daily)")
    print("=" * 50)

    all_failed = {}

    for name, lat, lon in LOCATIONS:
        try:
            failed = download_wind_era5(name, lat, lon)
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
