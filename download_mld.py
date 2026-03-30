#!/usr/bin/env python3
"""
Download MLD - HYCOM (0.08 deg, daily samples)
Derives MLD from temperature profiles using 0.5C criterion.
Note: HYCOM data starts from ~2018-12
"""

from config import (
    os, time, np, pd, xr,
    LOCATIONS, START, END, get_output_path
)

URL = "https://tds.hycom.org/thredds/dodsC/GLBy0.08/expt_93.0/ts3z"


def download_mld(name, lat, lon):
    print(f"\n  {name} ({lat}, {lon})")

    out_path = get_output_path(name, "mld")
    failed_months = []

    # Load existing data if any
    if os.path.exists(out_path):
        existing = pd.read_csv(out_path, index_col="time", parse_dates=True)
        print(f"    Existing: {len(existing)} days", flush=True)
    else:
        existing = pd.DataFrame()

    print(f"    Opening HYCOM dataset...", flush=True)
    ds = xr.open_dataset(URL, decode_times=False)

    # Convert time
    times = pd.to_datetime(ds.time.values, unit="h", origin=pd.Timestamp("2000-01-01"))
    ds = ds.assign_coords(time=times)

    # Find nearest grid point
    lat_idx = int(np.abs(ds.lat.values - lat).argmin())
    lon_idx = int(np.abs(ds.lon.values - lon).argmin())
    print(f"    Grid point: ({ds.lat.values[lat_idx]:.2f}, {ds.lon.values[lon_idx]:.2f})", flush=True)

    # Only use depths to 500m (MLD is rarely deeper, saves bandwidth)
    max_depth_idx = np.searchsorted(ds.depth.values, 500)
    depths = ds.depth.values[:max_depth_idx + 1]

    # Generate month list (HYCOM starts ~2018-12)
    start_dt = max(pd.Timestamp(START), pd.Timestamp("2018-12-04"))
    months = pd.date_range(start_dt, END, freq="MS")

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
        for attempt in range(5):
            try:
                # Load entire month at once, only top 500m (much faster)
                month_ds = ds["water_temp"].sel(
                    time=slice(str(month_start), str(month_end)),
                    lat=ds.lat.values[lat_idx],
                    lon=ds.lon.values[lon_idx]
                ).isel(depth=slice(0, max_depth_idx + 1))
                # Subsample to daily (every 8th 3-hourly timestep)
                month_ds = month_ds.isel(time=slice(None, None, 8))
                temp_data = month_ds.load()

                # MLD calculation with linear interpolation
                temp_vals = temp_data.values  # shape: (time, depth)
                sst = temp_vals[:, 0]  # shape: (time,)
                diff = np.abs(temp_vals - sst[:, np.newaxis])  # shape: (time, depth)

                # Find MLD by linear interpolation at 0.5C threshold crossing
                mld = np.full(len(temp_vals), np.nan)
                for t in range(len(temp_vals)):
                    if np.isnan(sst[t]):
                        continue
                    for d in range(1, len(depths)):
                        if diff[t, d] > 0.5 and diff[t, d-1] <= 0.5:
                            # Linear interpolation to find exact depth
                            frac = (0.5 - diff[t, d-1]) / (diff[t, d] - diff[t, d-1])
                            mld[t] = depths[d-1] + frac * (depths[d] - depths[d-1])
                            break
                    # If no crossing found (isothermal), leave as NaN

                df = pd.DataFrame({
                    "time": temp_data.time.values,
                    "mld": mld
                }).set_index("time")
                df = df.dropna()

                # Normalize timestamps to midnight UTC
                df.index = df.index.normalize()
                # Remove duplicates from same day (keep first)
                df = df[~df.index.duplicated(keep='first')]

                if len(df) > 0:
                    existing = pd.concat([existing, df])
                    existing = existing[~existing.index.duplicated(keep='last')].sort_index()
                    existing.to_csv(out_path)
                    print(f"{len(df)} days", flush=True)
                else:
                    print("no data", flush=True)
                success = True
                break

            except Exception as e:
                if attempt < 4:
                    print(f"retry({attempt+1})...", end=" ", flush=True)
                    time.sleep(15 * (attempt + 1))  # 15, 30, 45, 60s
                else:
                    print(f"FAILED", flush=True)

        if not success:
            failed_months.append(month_str)

    print(f"    Total: {len(existing)} days")
    if failed_months:
        print(f"    FAILED MONTHS: {', '.join(failed_months)}")
    return failed_months


if __name__ == "__main__":
    print("Downloading MLD (HYCOM, daily)")
    print("Note: HYCOM data starts from 2018-12")
    print("=" * 50)

    all_failed = {}

    for name, lat, lon in LOCATIONS:
        try:
            failed = download_mld(name, lat, lon)
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
