---
title: Contour view
---
**View ▸ Contour** at the top of the [[explorer]] draws the active channel as
a surface: retention time across, m/z up, intensity as colour. A
chromatogram sums the mass axis away and a spectrum sums the time axis
away; the contour is the same data with neither summed, so an interference
sitting beside a target, or a ridge running down the whole run at one mass,
is visible rather than inferred.

## What is drawn

Each scan of the channel is a row and each m/z bin a column. The mass axis
is divided into about 1,400 bins — roughly one per screen pixel across a
wide range; finer than that the picture is the same, only slower. A long
run has more scans than a screen has rows, and the scans over the limit of
about 900 rows are **averaged into their row, not skipped**: sampling every
k-th scan is faster and loses a one-scan peak entirely, which is the
opposite of what a picture of the data is for. The average rather than the
sum, because the last group is usually short and a row that is dimmer only
for that would be a lie about the data.

Spectra are taken without their restored zeros: a histogram of intensities
cannot be changed by adding points of intensity zero, and restoring them
was measured to triple the time for the same grid.

## Controls

| Control | Effect |
|---|---|
| **Intensity** | how intensities become colour: *sqrt* (default), *log* or *linear*. A linear ramp over four decades shows the base peak and nothing else; square root lifts the minor ions into view without the flattening that makes a log plot look uniformly grey |
| **Colours** | the palette: inferno, viridis, magma, turbo, CET-L9 |
| **Extract this view** | the chromatogram and the spectrum of the rectangle on screen — both taken from the reader, not from the grid |
| **Rebuild** | rebuild the grid over the range currently on screen, at full resolution for that range |
| click | the spectrum of the scan under the cursor, in the spectrum pane |
| readout | the retention time, m/z and intensity under the cursor |

The top of the colour scale is the 99.7th percentile of the intensities,
not the maximum: a single saturated or spiking scan would otherwise set the
scale for everything else and leave the rest of the surface black.

## An infusion as a film

On a sample read as a [[direct-infusion]] the same surface is a film. There
is no chromatography, so nothing moves along the time axis except the spray:
a fragment is a **ridge at constant m/z running the whole length of the run**,
and a spray transient is a **bright column one scan wide**. The average an
infusion is read from hides both, which is what the film is for.

Three things appear, and only on an infusion:

| | |
|---|---|
| **the strip** | the channel's own total ion current, one point per scan, on the surface's time axis. It is the instrument's chromatogram, not a row of the grid: the grid's rows may be several scans averaged and its m/z bins are wider than the instrument's steps |
| **the ✕ marks** | the scans left out of the average, marked on the strip and shaded on the surface |
| **Play** | steps the spectrum pane through every scan of the run, at ten scans a second times the speed beside it (1×, 5×, 20×). Press again to pause; it stops on its own at the last scan, and starting it there begins again at the first |

The cursor on both the strip and the surface is the scan the spectrum pane is
showing, wherever it came from — Play, the ◀ ▶ buttons, the arrow keys, the
scan number, or a click on the surface.

### What it showed on the real infusions

Two ZenoTOF 7600 bile-acid infusions, one product-ion channel each, a scan
every 0.25 s:

| | `DCA-d4_TOFMSMS_Mix1` | `CA-d4_…EAD_22CE…_mix1` |
|---|---|---|
| scans, length | 473, 1.98 min | 146, 0.62 min |
| the grid | 473 rows × 1,400 bins | 146 × 1,400 |
| scans averaged into a row | none — 473 is under the 900-row limit | none |
| built and drawn | 1.4 s | 0.8 s |
| left out of the average | 4 scans (the first second) | 4 scans |
| the tallest scan | **4.38×** the run's median | 1.04× |

`DCA-d4_TOFMSMS_Mix1` is the file the infusion rule was written against, and
the film is where its three transients become visible rather than statistical:
scan 2 at 0.0084 min at 4.38 times the median total, and two more mid-run at
1.0819 and 1.0988 min at 2.40 and 4.36 times. All three read in the strip as
spikes and on the surface as bright columns, and because no scans are grouped
into a row here the grid's own row totals carry the same three ratios — 4.38,
2.40 and 4.36. The other file has no transient at all: its tallest scan is
1.04 times its median, and its strip is a flat band.

**Play runs at the rate the file can be drawn.** The timer asks for a scan
every 100 ms at 1×, 20 ms at 5× and 5 ms at 20×; a frame — read the scan,
draw it, label it — was measured at **52 ms** on `DCA-d4_TOFMSMS_Mix1` and
**89 ms** on the CA-d4 EAD file. So 1× runs as asked — ten scans a second is
two and a half times life at a 0.25 s cycle, and the 473-scan run is 47
seconds of film — while 20× reaches about nineteen scans a second rather than
two hundred. A tick arriving while the last one is still drawing is dropped,
so the film runs slower rather than falling behind itself. Those figures are what they are because the spectrum pane is **not
rescaled while Play is running** — the scale stays where it was, so what moves
on screen is the data rather than the axes. With the rescale left in, the same
two frames cost 245 ms and 880 ms.

## Nothing is quantified from the contour

Its m/z bins are wider than the instrument's steps and its rows may be
several scans averaged, so it is a picture, deliberately. *Extract this
view* goes back to the reader for both the XIC and the spectrum, and those
are what the [[manual-xic]] and the Results tab work with.

The readout under the cursor searches the bin edges to the right, because
that is where a value sitting exactly on an edge is put by the histogram;
searching left reads the cell next door and the readout disagrees with the
picture — caught by a test, not by eye.
