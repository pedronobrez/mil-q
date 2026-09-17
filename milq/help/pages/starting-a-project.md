---
title: Starting a project
---
## The start prompt

When the application opens with no file named on the command line it asks
how to begin: **New project…**, **Open project…**, or explore raw files
without a project. The prompt does not block the application — it can be
quit past — and a checkbox makes it stay away in future; the setting is
remembered and can only be undone by clearing the preferences.

## The New project wizard

`File ▸ New project…` (Ctrl+N) walks through the batch in the order the
work needs it.

**Project.** A name and a folder. The project file, `name.oqproj`, is
written when the wizard finishes, so there is a file to save into from the
first change rather than one to remember to create at the end.

**Samples.** Add the raw files. Each becomes one row with its file, a
shortened sample name, a type and a group; select rows and use **Set for
selection** to give them a type — Unknown, Standard, Quality Control,
Blank, Double Blank, Solvent — and a free-text study group. Names are
shortened by dropping the prefix every file shares, so `demo_QC01` and
`demo_STD_L1` become `QC01` and `STD_L1`, and made distinct if two would
collide. All of this can be changed later in the [[samples-workspace]].

**Method.** Where the component table comes from:

- **Import a component list (CSV)** — a file in the layout described in
  [[method-workspace]], headers in English or Portuguese.
- **Generate one component per product-ion channel of the samples** — the
  acquisition method of the first file is read and every product-ion
  experiment becomes a component named after its precursor. This is how an
  eighty-transition method gets in without being typed.
- **Start with an empty method** — and build it in the Method workspace.

**Ready.** A summary of what will be created and any warnings — a file
that could not be opened, a CSV with no valid rows.

When the wizard finishes the files are opened, the project is written, and
the Analytics workspace processes the batch if there is a method to process
it with.

## Adding files to an open project

`File ▸ Add data files…` (Ctrl+O) opens more `.wiff` or mzML files into the
current session; `File ▸ Close all` closes every file and clears the results.
Files added this way appear in the [[samples-workspace]] as Unknown until
told otherwise.

## Saving

`File ▸ Save project` (Ctrl+S) writes the `.oqproj`; `Save project as…`
writes it somewhere else. The title bar carries a `•` while anything is
unsaved, and nothing that would discard the session — quitting, closing the
files, opening another project — does so without offering to save first.

What the project holds, and what it does not, is in [[projects-and-files]].
Projects saved by the program under its earlier name, `.opvproj`, still
open; new ones are written as `.oqproj`.

## Opening a project whose files have moved

The project records the path of every raw file. On opening, a file that is
no longer there is listed by name and the project opens without it: its
rows stay in the samples table, marked as not loaded, and its results are
kept. Put the file back where it was, or add it again, and reprocess.
