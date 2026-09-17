#!/usr/bin/env python3
"""Draws MIL-Q's application icon with the suite's shared generator.

MIL-Q and OpenDIAL share one mark — the rounded square, the blue gradient, the white
chromatographic peak on a baseline — and differ in what stands behind the peak. MIL-Q's is the
*targeted* variant: one co-eluting peak showing through the front one, the deconvolution of a
known analyte. The drawing lives in OpenDIAL's repository (`tools/make_icon.py`), so the two
applications cannot drift apart; this script finds it and asks for the targeted mark.

    python3 packaging/make_icon.py            # -> packaging/icons/MIL-Q.{icns,ico,svg} and png/

The generator is looked for at $OPENDIAL_ROOT/tools/make_icon.py, then beside this repository
(../OpenDIAL/opendial). The files it writes are committed, so a build does not need OpenDIAL
present; run this again after the shared mark changes.
"""
import importlib.util
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "icons"


def find_generator() -> Path:
    candidates = []
    if os.environ.get("OPENDIAL_ROOT"):
        candidates.append(Path(os.environ["OPENDIAL_ROOT"]) / "tools" / "make_icon.py")
    for sibling in ("OpenDIAL/opendial", "opendial", "OpenDIAL"):
        candidates.append(HERE.parent.parent / sibling / "tools" / "make_icon.py")
    for c in candidates:
        if c.is_file():
            return c
    sys.exit("the shared icon generator was not found; set OPENDIAL_ROOT to the opendial folder of the OpenDIAL repository "
             "(looked in: " + ", ".join(str(c) for c in candidates) + ")")


def main() -> None:
    path = find_generator()
    spec = importlib.util.spec_from_file_location("suite_icon", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.export(str(OUT), "targeted", "MIL-Q")
    print(f"[icon] drawn by {path}")


if __name__ == "__main__":
    main()
