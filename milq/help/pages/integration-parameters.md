---
title: Integration parameters
---
The **Integration** panel of the [[analytics-workspace]] holds the settings
the selected component's peaks are found and measured with. A method
carries a set of defaults and a component may override them, so one
awkward analyte can be tuned without disturbing the rest of the batch. The
panel's title says which it is showing: *method defaults* or *component
override*.

## The settings

| Setting | Meaning |
|---|---|
| **Smooth σ** | Gaussian smoothing of the XIC, in scans; 0 turns it off. Applied to the trace before detection, integration and drawing alike |
| **Baseline (min)** | the window over which a lower envelope is estimated and subtracted; 0 turns it off. Must be wider than the broadest peak worth keeping |
| **Min. height** | the smallest peak kept, as a fraction of the tallest in the detection range — 0.05 keeps peaks at least 5% of the largest |
| **Min. S/N** | peaks whose height over the noise falls below this are dropped; 3 to start. What "noise" is here is on [[signal-to-noise]] |
| **Noise as** | how the noise in a noise region is measured: *peak-to-peak* (the full swing, the stricter reading) or *standard deviation* |
| **Peak** | which peak in the window is the component when more than one clears the gates: *largest*, or *nearest the expected RT* — see below |
| **Algorithm** | how the area is arrived at: valley, summation, or Gaussian fit — see [[integration-algorithms]] |
| **Noise region** | the stretch of baseline the noise is measured over, set from a panel of the [[peak-review]] grid; *automatic* means the whole trace |

**Update method for component** writes the settings as this component's
override; **Update method for group** writes them to every component of the
same group; **Back to method defaults** removes the override. **Copy** and
**Paste** carry settings between components. Changing a value previews it
on the grid; only Update keeps it.

Update also reintegrates, and only what it has to. Every setting in the
table above is part of the component's *fingerprint* — the digest each
integrated row carries of what produced it (see
[[analytics-workspace|Processing only what changed]]) — so applying a
setting to one component reads that component's rows in every sample and
leaves the rest of the batch untouched. A component with an override of its
own does **not** move when the method defaults change: what is fingerprinted
is the parameters in force, and an override is what is in force. Rows that
were integrated by hand under the old settings are integrated again with the
rest, because a boundary drawn on one trace is not a decision about another;
the [[audit-trail]] line says how many there were.

## How a peak is found

The detector works on the stretch of the XIC it is given, which is the
retention-time window plus three scans either side — see *The margin*
below — and does this:

1. The trace is smoothed for detection (one scan by default; the
   integration itself uses the conditioned trace, not this smoothing) and
   every local maximum at least **Min. height** of the tallest is a
   candidate apex, strongest first.
2. From each apex the boundary is walked outwards, to the left and to the
   right, until either the signal has come down to the baseline — the
   trace's median plus the larger of the noise and 5% of the peak's height
   above it — or it has climbed back by more than the noise, which is a
   valley between two peaks. Walking "while not going up" was tried first
   and gave peaks minutes wide, because an XIC is mostly flat baseline and
   flat counts as not going up.
3. A straight baseline is drawn between the two boundaries and the area
   above it is the peak's area; height is measured from that baseline;
   width is the full width at half that height.
4. Peaks whose height is below **Min. S/N** times the noise are dropped.
5. Peaks whose apex falls outside the declared window — in the margin — are
   dropped: they belong to something else.
6. Of what is left, **Peak** decides which is the component.

## The window and the margin

The retention-time window says where the apex may be. It is **not** a
statement about where the peak ends, and handing the detector exactly that
window had two consequences, both found by reprocessing a real batch: the
peak was truncated at the boundary, biasing its area, and — worse — the
detector declines below five points, so a ±0.5 min window on a method
sampling one transition every 14.6 s held four scans and came back empty
whatever was in it. A peak of 44,875 counts read as "no peak above noise",
and whether a component was integrated depended on whether its window
happened to catch four scans or five, which is set by the channel's start
offset. So the detector is given three scans either side and the apex is
required to land inside the declared window afterwards. On that batch this
took the rows with a peak from 1,771 to 2,665 and the components with any
peak at all from 89 to 139 of 141. The margin is small on purpose:
everything inside it competes on relative height with the real peak.

A window narrower than five points still returns nothing, and the row says
so — *only 4 points to detect in; the window is narrower than the sampling
can resolve* — rather than *no peak above noise*, which sends somebody
looking for signal that is plainly there. [[check-method]] warns of windows
under eight points and [[suggest-from-data]] widens them.

## Which peak: largest or nearest

*Largest* takes the biggest peak in the window, which is what a single peak
with noise beside it needs and is the default, so that no saved project
changes its numbers. *Nearest the expected RT* uses the method's retention
time to decide, and is what two co-eluting species need — an isobaric or
isomeric neighbour inside a ±0.6 min window is ordinary in lipidomics, and
there the taller peak wins whether or not the method points at it.

Proximity is decided **among the peaks that already passed the height and
S/N gates**, so those gates are what stops *nearest* picking noise that
happens to sit on the expected time; a method whose window is full of small
peaks needs Min. height raised, not a different rule. When proximity
overrules size, the row says what it passed over — *chosen by proximity;
the largest peak in the window is at 11.62 min and 2.3× the area* — because
a policy that silently takes the smaller peak cannot be reviewed. Without
an expected time the rule falls back to largest and says so.

## The notes a row can carry

| Note | Meaning |
|---|---|
| no matching channel | no channel of the sample carries the component's precursor and target — see [[method-workspace]] |
| no data | the channel returned nothing |
| channel does not cover 5.10–6.10 min | the matched channel was not acquired over the window |
| only 4 points to detect in… | the window is narrower than the sampling can resolve |
| no peak above noise | nothing cleared the gates with its apex inside the window |
| chosen by proximity… | *nearest* overruled *largest* |
| no expected retention time; took the largest peak | *nearest* had nothing to be near |
| Gaussian fit not possible (…); valley area kept | the fit fell back — see [[integration-algorithms]] |
| summation needs a retention-time window | summation has no window to sum over |
| S/N not measured | a signal-to-noise criterion could not be evaluated — see [[signal-to-noise]] |
