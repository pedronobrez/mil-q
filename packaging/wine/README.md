# Running the Windows build under Wine or CrossOver

The Windows installer needs **Windows 10 1703 or newer** and will not start
under Wine as it stands. It fails at import with

    ImportError: DLL load failed while importing QtCore: Module not found.

which reads like a broken installer and is not one. `Qt6Core.dll` in the
PyQt6 wheel statically imports eighteen `ucnv_*` symbols from `icuuc.dll` —
ICU's converter API — and the wheel carries no ICU of its own, because
Windows has shipped one in `System32` since that release: a 36 KB
`icuuc.dll` forwarding to a 2.7 MB `icu.dll`. Wine implements neither, and a
static import that cannot be resolved fails the whole library. CrossOver's
own loader says so plainly:

    err:module:import_dll Library icuuc.dll (which is needed by
      ...\_internal\PyQt6\Qt6\bin\Qt6Core.dll) not found

`icuuc_stub.c` here exports those eighteen symbols and nothing else, and
answers as ICU does when it has no converter to offer. Qt then uses the
codecs it implements itself — UTF-8, UTF-16, UTF-32, Latin-1, the system
locale — which is everything this application reads or writes. What is given
up is the long tail of legacy encodings in file dialogs and text import.

## Building and installing it

    x86_64-w64-mingw32-gcc -O2 -shared -o icuuc.dll icuuc_stub.c \
        -nostdlib -Wl,--entry=0 -Wl,--no-seh

Copy the 8 KB result next to `Qt6Core.dll` in the installed application:

    <bottle>/drive_c/users/crossover/AppData/Local/MIL-Q/
        _internal/PyQt6/Qt6/bin/icuuc.dll

## Do not ship this in the installer

On a real Windows machine an application-local `icuuc.dll` is found before
the one in `System32`, so putting this in the MSI would take working ICU away
from every user who has it. It belongs only in a Wine prefix, added by hand
by someone who has read the paragraph above. A test in the suite checks that
the packaging never picks it up.

## What it was verified to do

With the stub in place, CrossOver 26.3 on macOS ran the Windows build, opened
its window, and read a real acquisition. `--digest` was then run three ways on
the same file and the output compared:

    macOS from source        3b24687cb917465f81c242902d4fd17b...
    macOS from the CI disk image  same
    Windows MSI under CrossOver   same

Identical, to the byte, once the CRLF the Windows build writes is normalised.

Repeated over the whole batch of five acquisitions — samples, a QC and a
standard — the three digests are again the same file, sha256
`ebdeebc210177a8d7ab2681a56ae2b0e346e4b69`: 591 lines each, covering 405
channel chromatograms compared by sum, maximum and a SHA-256 of the whole
array, 5 sample TICs, 25 complete spectra, 25 extracted traces and 125
integrated peaks with retention times and areas at nine decimal places — the
numbers a quantitative result is made of.

The comparison is not vacuous: all 405 channel hashes are distinct from one
another, so five genuinely different acquisitions were read, not one read five
times.

What that does and does not establish: the reader, the arithmetic and the
integration give the same answers on both systems, for these files, in one
bottle on one machine. It says nothing about Wine in general, about other
instruments or methods, or about anything the interface does after the numbers
are read.
