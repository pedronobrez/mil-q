"""
The fast routes through the data path, against the slow ones they replaced.

Every test here compares two ways of getting the same answer rather than
asserting a number: the point of each change was that nothing moved, so what
has to be pinned is the agreement. The `.wiff` side needs no instrument —
`_to_numpy` takes anything exporting a buffer, and a Clearcore2 `double[]` is
one of those.
"""

import array

import numpy as np
import pytest

from milq import mzml
from milq.quantify import PeakResult, ResultsSet
from milq.wiff import _to_numpy


# --------------------------------------------------------------------------- #
# _to_numpy: the buffer route and the element walk
# --------------------------------------------------------------------------- #
def _the_slow_way(net_array):
    """What `_to_numpy` did before the buffer protocol."""
    if net_array is None:
        return np.zeros(0, dtype=np.float64)
    return np.asarray(list(net_array), dtype=np.float64)


@pytest.mark.parametrize("values", [
    [],
    [3.5],
    [101.05922835, 101.06206523, 101.06348369, 108.94194257],
    [0.0, -1.0, 1e-300, 1e300],
    list(np.linspace(100.0, 2000.0, 1143)),
])
def test_the_buffer_route_gives_the_same_doubles(values):
    """A `double[]` stands in as an `array('d')`: both export one buffer."""
    buffered = array.array("d", values)
    fast = _to_numpy(buffered)
    slow = _the_slow_way(buffered)
    assert fast.dtype == np.float64
    assert fast.shape == slow.shape
    # byte for byte, not approximately: these are the instrument's numbers
    assert fast.tobytes() == slow.tobytes()


def test_a_measured_zero_survives_the_conversion():
    """`x or default` is a trap for a zero, and so is a falsy empty buffer."""
    assert _to_numpy(array.array("d", [0.0, 0.0])).tolist() == [0.0, 0.0]
    assert _to_numpy(array.array("d", [])).size == 0
    assert _to_numpy(None).size == 0


def test_the_array_owns_its_memory():
    """
    The .NET array is on the managed heap and may be freed or moved; a view
    onto it reads plausible numbers out of memory nobody owns any more.
    """
    out = _to_numpy(array.array("d", [1.0, 2.0, 3.0]))
    assert out.flags.owndata
    assert out.base is None


def test_an_integer_buffer_widens_the_way_the_walk_did():
    ints = array.array("i", [7, 8, 9])
    assert _to_numpy(ints).tolist() == _the_slow_way(ints).tolist()


def test_anything_without_a_buffer_falls_back_to_the_walk():
    """A `List<double>`, a generator, a plain list: refused by memoryview."""
    class OnlyIterable:
        def __iter__(self):
            return iter([1.5, 2.5])

    assert _to_numpy(OnlyIterable()).tolist() == [1.5, 2.5]
    assert _to_numpy([4.0, 5.0]).tolist() == [4.0, 5.0]


# --------------------------------------------------------------------------- #
# mzml: one walk of a spectrum against three
# --------------------------------------------------------------------------- #
def _spectrum_xml(*, rt="1.5", unit_accession="UO:0000031", unit_name="minute",
                  activation=True, namespaced=True):
    ns = ' xmlns="http://psi.hupo.org/ms/mzml"' if namespaced else ""
    dissociation = ""
    if activation:
        dissociation = """
          <precursor>
            <selectedIonList><selectedIon>
              <cvParam accession="MS:1000744" name="selected ion m/z" value="647.5"/>
            </selectedIon></selectedIonList>
            <activation>
              <cvParam accession="MS:1000045" name="collision energy" value="35.0"/>
              <cvParam accession="MS:1000422" name="beam-type collision-induced dissociation" value=""/>
            </activation>
          </precursor>"""
    return f"""<spectrum{ns} index="0" id="scan=1" defaultArrayLength="3">
      <cvParam accession="MS:1000511" name="ms level" value="2"/>
      <cvParam accession="MS:1000129" name="negative scan" value=""/>
      <cvParam accession="MS:1000285" name="total ion current" value="0"/>
      <scanList><scan>
        <cvParam accession="MS:1000016" name="scan start time" value="{rt}"
                 unitAccession="{unit_accession}" unitName="{unit_name}"/>
        <scanWindowList><scanWindow>
          <cvParam accession="MS:1000501" name="scan window lower limit" value="50"/>
          <cvParam accession="MS:1000500" name="scan window upper limit" value="700"/>
        </scanWindow></scanWindowList>
      </scan></scanList>
      <precursorList>{dissociation}</precursorList>
    </spectrum>"""


def _parsed(text):
    from xml.etree import ElementTree as ET
    return ET.fromstring(text)


@pytest.mark.parametrize("kwargs", [
    {},
    {"activation": False},
    {"namespaced": False},
    {"rt": "90.0", "unit_accession": "UO:0000010", "unit_name": "second"},
    {"rt": "0.5", "unit_accession": "UO:0000032", "unit_name": "hour"},
    {"rt": "not a number"},
])
def test_one_walk_says_what_three_walks_said(kwargs):
    element = _parsed(_spectrum_xml(**kwargs))
    assert mzml._scan_facts(element) == (
        mzml._params(element), mzml._minutes(element), mzml._activation(element))


def test_the_activations_own_parameters_stay_in_the_dictionary():
    """`_params` collects them, so singling the element out must not drop them."""
    params, _, activation = mzml._scan_facts(_parsed(_spectrum_xml()))
    assert params[mzml.COLLISION_ENERGY] == "35.0"
    assert activation == "beam-type collision-induced dissociation"


def test_a_scan_with_no_activation_reports_nothing_rather_than_guessing():
    _, _, activation = mzml._scan_facts(_parsed(_spectrum_xml(activation=False)))
    assert activation == ""


def test_seconds_are_still_converted_in_the_single_walk():
    _, rt, _ = mzml._scan_facts(_parsed(_spectrum_xml(
        rt="90.0", unit_accession="UO:0000010", unit_name="second")))
    assert rt == pytest.approx(1.5)


def test_stripping_the_namespace_is_memoised_without_changing_it():
    assert mzml._local("{http://psi.hupo.org/ms/mzml}spectrum") == "spectrum"
    assert mzml._local("spectrum") == "spectrum"
    # asking twice must not answer differently
    assert mzml._local("{ns}cvParam") == mzml._local("{ns}cvParam") == "cvParam"


def test_the_memo_stops_growing_rather_than_holding_a_file_open():
    before = dict(mzml._LOCAL_NAMES)
    try:
        mzml._LOCAL_NAMES.clear()
        for i in range(mzml._LOCAL_NAMES_MAX + 50):
            assert mzml._local("{ns%d}cvParam" % i) == "cvParam"
        assert len(mzml._LOCAL_NAMES) == mzml._LOCAL_NAMES_MAX
    finally:
        mzml._LOCAL_NAMES.clear()
        mzml._LOCAL_NAMES.update(before)


# --------------------------------------------------------------------------- #
# ResultsSet.by_component against for_component
# --------------------------------------------------------------------------- #
def _results(samples=4, components=3):
    return ResultsSet([
        PeakResult(sample_key=f"s{s}", sample_name=f"s{s}",
                   component=f"c{c}", area=float(s * 10 + c))
        for s in range(samples) for c in range(components)
    ])


def test_the_index_holds_what_the_filter_found():
    results = _results()
    index = results.by_component()
    for name in ("c0", "c1", "c2"):
        assert index[name] == results.for_component(name)
    assert sum(len(v) for v in index.values()) == len(results)


def test_the_index_keeps_the_order_the_rows_are_held_in():
    results = _results()
    assert [r.area for r in results.by_component()["c1"]] == \
           [r.area for r in results.for_component("c1")]


def test_a_component_with_no_rows_is_absent_rather_than_empty():
    """The callers use `.get(name, ())`, so absence has to mean no rows."""
    assert "nothing" not in _results().by_component()
    assert _results().for_component("nothing") == []


def test_an_empty_set_indexes_to_nothing():
    assert ResultsSet().by_component() == {}
