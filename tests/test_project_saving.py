"""Unsaved work is tracked, and cannot be lost without being offered a save."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from milq.components import Component
from milq.samples import SampleEntry
from milq.session import (
    LEGACY_PROJECT_SUFFIX, PROJECT_SUFFIX, Session,
)


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def session(qapp):
    return Session()


def test_a_fresh_session_has_nothing_to_save(session):
    assert not session.dirty
    assert not session.has_content


def test_changing_the_method_marks_the_session(session):
    session.set_components([Component(name="Cer", precursor=538.5)])
    assert session.dirty
    assert session.has_content


def test_saving_clears_the_mark(session, tmp_path):
    session.set_components([Component(name="Cer", precursor=538.5)])
    session.save_project(str(tmp_path / "p"))
    assert not session.dirty


def test_the_suffix_is_added_when_it_is_missing(session, tmp_path):
    session.save_project(str(tmp_path / "p"))
    assert session.project_path.endswith(PROJECT_SUFFIX)


def test_a_project_saved_under_the_old_suffix_keeps_it(session, tmp_path):
    old = str(tmp_path / f"p{LEGACY_PROJECT_SUFFIX}")
    session.save_project(old)
    assert session.project_path == old


def test_an_old_project_still_opens(session, tmp_path):
    source = Session()
    source.set_components([Component(name="Cer", precursor=538.5)])
    source.entries = [SampleEntry("/d/a.wiff", 0, "A", sample_group="control")]
    old = str(tmp_path / f"p{LEGACY_PROJECT_SUFFIX}")
    source.save_project(old)

    missing = session.load_project(old)
    assert missing == ["/d/a.wiff"]      # the raw file is not there, but the batch is
    assert [c.name for c in session.method.components] == ["Cer"]
    assert session.entries[0].sample_group == "control"
    assert not session.dirty


def test_loading_a_project_leaves_nothing_marked(session, tmp_path):
    source = Session()
    source.set_components([Component(name="Cer", precursor=538.5)])
    path = str(tmp_path / "p")
    source.save_project(path)
    session.load_project(source.project_path)
    assert not session.dirty


def test_closing_everything_clears_the_mark(session):
    session.entries = [SampleEntry("/d/a.wiff", 0, "A")]
    session.set_components([Component(name="Cer", precursor=538.5)])
    session.close_all()
    assert not session.dirty
    assert session.project_path is None
    # the method survives a close, so it can be reused on the next batch
    assert [c.name for c in session.method.components] == ["Cer"]


def test_the_project_signal_fires_once_per_transition(session):
    seen = []
    session.sigProjectChanged.connect(lambda: seen.append(session.dirty))
    session.set_components([Component(name="Cer", precursor=538.5)])
    session.set_components([Component(name="Cer2", precursor=539.5)])
    assert seen == [True]                # already dirty: no second announcement
