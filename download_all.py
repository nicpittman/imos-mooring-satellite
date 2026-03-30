#!/usr/bin/env python3
"""
Download all ocean variables for all locations, then generate plots.
Use --parallel or -p flag to run downloads concurrently.
"""

import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

# Set to True to run downloads in parallel by default
PARALLEL = False

# Download scripts
scripts = [
    "download_sst.py",
    "download_chl.py",
    "download_npp.py",
    "download_wind_era5_0.25deg.py",
    "download_mld.py",
]


def run_script(script):
    """Run a download script and return result."""
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True
    )
    return script, result.returncode, result.stdout, result.stderr


if __name__ == "__main__":
    parallel = PARALLEL or "--parallel" in sys.argv or "-p" in sys.argv

    if parallel:
        print("Downloading all variables in parallel...")
        print("=" * 60)

        with ProcessPoolExecutor(max_workers=len(scripts)) as executor:
            futures = {executor.submit(run_script, s): s for s in scripts}

            for future in as_completed(futures):
                script, returncode, stdout, stderr = future.result()
                print(f"\n{'#'*60}")
                print(f"# {script} {'DONE' if returncode == 0 else 'FAILED'}")
                print(f"{'#'*60}")
                print(stdout)
                if stderr:
                    print(stderr)
    else:
        # Sequential downloads
        for script in scripts:
            print(f"\n{'#'*60}")
            print(f"# Running {script}")
            print(f"{'#'*60}\n")
            subprocess.run([sys.executable, script])

    # Generate plots (after all downloads complete)
    print(f"\n{'#'*60}")
    print(f"# Generating plots")
    print(f"{'#'*60}\n")
    subprocess.run([sys.executable, "plot_timeseries.py"])
