---
title: Mass calculator
---
The **Mass calc** tab of the [[explorer]] turns a formula into the numbers a
mass spectrometrist needs, and a measured mass into an error.

## Formula

Type a molecular formula: `C18H34O4`. The syntax takes groups with
multipliers, `C6H4(NO2)2`, and single isotopes in square brackets, `[13C]`,
with `D` accepted for deuterium — so a labelled internal standard such as
`C18H30D4O4` is typed as it is written. The panel reports the monoisotopic
mass, the average mass, the ring-and-double-bond equivalent (RDBE), and the
m/z of the ion for the adduct chosen.

## Adducts

| Negative | Positive |
|---|---|
| [M−H]⁻ | [M+H]⁺ |
| [M+Cl]⁻ | [M+NH₄]⁺ |
| [M+HCOO]⁻ | [M+Na]⁺ |
| [M+CH₃COO]⁻ | [M+K]⁺ |
| [M−2H]²⁻ | [M+2H]²⁺ |

The ion mass accounts for the electron: a cation is lighter than the sum of
its atoms by one electron mass and an anion heavier, which matters at the
fourth decimal.

The same adduct list is used wherever a precursor is computed from a formula
— in the [[method-workspace]] a component with a formula and an adduct and no
precursor has its precursor filled in from them.

## Mass accuracy

Type a measured m/z under the computed one and the error is shown in mDa and
in ppm. This is the quickest check that a peak on screen is what a formula
says it is.

## Isotope pattern

The theoretical isotope pattern of the ion — m/z and relative abundance of
M, M+1, M+2 and so on — is tabulated, and **Overlay on spectrum** draws it
on the spectrum pane as sticks scaled to the peak nearest the monoisotopic
mass, so the measured satellites can be compared with the expected ones.
**Clear overlay** removes it (so does the spectrum's right-click menu).

The overlay is only meaningful on a spectrum that carries the satellites. A
product-ion scan isolates the monoisotopic precursor in Q1, so its fragments
have no M+1 to compare; overlay on the TOF MS survey channel.

## Send to the formula finder

**Send m/z to formula finder** passes the computed ion mass to the
[[formula-finder]], which is the reverse question: what compositions could
this mass be?
