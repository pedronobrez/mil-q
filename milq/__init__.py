"""MIL-Q - open source quantitation for LC-MS data (.wiff, .mzML)."""

__version__ = "1.0.2"

# Read every OPENQUANT_* as its MILQ_* twin before anything asks for one.
# Here rather than in each entry point because importing the package is the
# one thing every route has in common — the window, the command line, the
# API and the test suite. See `milq.legacy`.
from .legacy import adopt_environment  # noqa: E402

adopt_environment()

from .components import Component  # noqa: F401
from .method import ProcessingMethod  # noqa: F401
from .samples import SampleEntry  # noqa: F401
from .mzml import MzmlFile, write_mzml  # noqa: F401
from .raw import open_raw  # noqa: F401
from .wiff import Channel, ChannelInfo, Sample, WiffFile  # noqa: F401
