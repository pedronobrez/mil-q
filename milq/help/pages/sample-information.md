---
title: Sample information
---
The **Sample** tab of the Explorer's side panels lists what the acquisition
file records about the selected sample and about the active channel. It is
read-only; **Copy all** puts the whole tree on the clipboard as text.

## Sample

What the file declares: the sample's name in the batch, the vial position,
the injection volume, the acquisition method's name, the batch and
acquisition date and time, and — where the method records them — the
declustering potential and collision energy in use. What it does **not**
declare is the sample's role: every injection in a `.wiff` comes back as
`kUnknown`, which is why sample type, concentration and dilution are held
in the [[samples-workspace]] and saved with the project instead.

The acquisition time is what the [[batch-qc]] page and the injection-order
axis of the [[metric-plot]] use to put the injections in the order the
instrument ran them.

## Active channel

For the channel selected at the top of the window: its index and name, the
experiment type (`TOF MS`, `TOF PI` — a product-ion scan — or an MRM
transition), polarity, precursor, mass range, the number of scans, and the
collision energy.

For an mzML these fields are the ones the converter carried across, and the
channel itself may have been inferred from the cycle of acquisition rather
than declared — see [[formats]].
