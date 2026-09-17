#!/usr/bin/env python3
"""
Quick environment check: open the .wiff files in the current directory, pull a
TIC, BPC, XIC and spectra out of each, and print a summary. No GUI involved.

    python3 selftest.py [file.wiff ...]
"""

from __future__ import annotations

import glob
import sys
import time

from milq import WiffFile


def report(path: str) -> None:
    started = time.time()
    wiff = WiffFile(path)
    sample = wiff.sample(0)
    rt, tic = sample.tic()

    print(f"\n=== {wiff.filename}")
    print(f"    sample     : {sample.name}")
    print(f"    instrument : {sample.instrument}   ({sample.acquisition_time})")
    print(f"    channels   : {len(sample.channels)}")
    print(f"    TIC        : {rt.size} points, RT {rt[0]:.2f}–{rt[-1]:.2f} min, "
          f"max {tic.max():,.0f} cps")

    ms1 = [c for c in sample.channels if c.info.is_ms1]
    ms2 = [c for c in sample.channels if not c.info.is_ms1]
    print(f"    MS1: {len(ms1)}   MS/MS: {len(ms2)}")

    best, best_max = None, -1.0
    for channel in ms2:
        peak = float(channel.tic()[1].max()) if channel.tic()[1].size else 0.0
        if peak > best_max:
            best, best_max = channel, peak
    if best is None:
        return

    x, y = best.tic()
    apex = int(y.argmax())
    mz, intensity = best.spectrum(apex)
    avg_mz, _ = best.spectrum_rt_range(x[apex] - 0.15, x[apex] + 0.15)
    top = float(mz[intensity.argmax()]) if mz.size else 0.0
    xrt, xy = best.xic(top, tolerance=0.02)

    print(f"    strongest channel: {best.info.label}")
    print(f"      apex     : RT {x[apex]:.3f} min, {best_max:,.0f} cps "
          f"(scan {apex + 1}/{best.info.n_scans})")
    print(f"      spectrum : {mz.size} points, base peak m/z {top:.4f}")
    print(f"      average  : {avg_mz.size} points over ±0.15 min")
    print(f"      XIC {top:.4f}: max {xy.max():,.0f} cps @ {xrt[xy.argmax()]:.3f} min")
    print(f"      BPC      : max {best.bpc()[1].max():,.0f} cps")
    print(f"    elapsed: {time.time() - started:.2f} s")
    wiff.close()


def main(argv: list[str]) -> int:
    paths = argv or sorted(glob.glob("*.wiff"))
    if not paths:
        print("No .wiff file found.")
        return 1
    for path in paths:
        report(path)
    print("\nOK — SCIEX file reading works.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
