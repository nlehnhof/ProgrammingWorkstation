"""Tests for the og_*/working-copy staging shared by TR's two template folders."""

import os

import pytest

from resources.utilities.templating import (
    TemplateError,
    patch_file,
    refresh_working_copy,
    stage_template,
)


def make_template(tmp_path, files):
    source = tmp_path / "og_thing"
    source.mkdir()
    for name, content in files.items():
        (source / name).write_text(content, encoding="utf-8")
    return source, tmp_path / "thing"


def test_refresh_copies_every_file(tmp_path):
    source, dest = make_template(tmp_path, {"a": "1", "b": "2"})
    assert refresh_working_copy(str(source), str(dest)) == ["a", "b"]
    assert (dest / "a").read_text() == "1"


def test_refresh_overwrites_a_stale_working_copy(tmp_path):
    """The reason the old 'revert the file afterwards' step is unnecessary."""
    source, dest = make_template(tmp_path, {"network": "ip '10.28.18.2'"})
    dest.mkdir()
    (dest / "network").write_text("ip '10.99.99.99'", encoding="utf-8")

    refresh_working_copy(str(source), str(dest))
    assert (dest / "network").read_text() == "ip '10.28.18.2'"


def test_refresh_ignores_subdirectories(tmp_path):
    source, dest = make_template(tmp_path, {"a": "1"})
    (source / "__pycache__").mkdir()
    assert refresh_working_copy(str(source), str(dest)) == ["a"]


def test_refresh_raises_on_missing_or_empty_template(tmp_path):
    with pytest.raises(TemplateError):
        refresh_working_copy(str(tmp_path / "nope"), str(tmp_path / "out"))

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(TemplateError):
        refresh_working_copy(str(empty), str(tmp_path / "out"))


def test_patch_replaces_and_reports_count(tmp_path):
    path = tmp_path / "network"
    path.write_text("a '10.28.18.2'\nb '10.28.18.2'\n", encoding="utf-8")

    assert patch_file(str(path), "10.28.18.2", "172.18.43.202") == 2
    assert "172.18.43.202" in path.read_text()
    assert "10.28.18.2'" not in path.read_text()


def test_patch_does_not_corrupt_a_longer_address(tmp_path):
    """Replacing 10.28.18.2 must not eat the 2 out of 10.28.18.20."""
    path = tmp_path / "network"
    path.write_text("gate '10.28.18.2'\nother '10.28.18.20'\n", encoding="utf-8")

    assert patch_file(str(path), "10.28.18.2", "10.1.1.5") == 1
    text = path.read_text()
    assert "gate '10.1.1.5'" in text
    assert "other '10.28.18.20'" in text


def test_patch_raises_when_the_placeholder_is_absent(tmp_path):
    """A silently-failed substitution used to ship the previous gate's config."""
    path = tmp_path / "network"
    path.write_text("nothing to see here", encoding="utf-8")

    with pytest.raises(TemplateError, match="does not contain"):
        patch_file(str(path), "10.28.18.2", "10.1.1.5")


def test_patch_verifies_by_count_not_by_presence(tmp_path):
    """The old check ('is the new IP in the file?') passes on an unchanged file
    that already held that address. This one does not."""
    path = tmp_path / "network"
    path.write_text("already '10.1.1.5'", encoding="utf-8")

    with pytest.raises(TemplateError):
        patch_file(str(path), "10.28.18.2", "10.1.1.5")


def test_patch_enforces_an_expected_occurrence_count(tmp_path):
    path = tmp_path / "network"
    path.write_text("a '10.28.18.2'\nb '10.28.18.2'\n", encoding="utf-8")

    with pytest.raises(TemplateError, match="expected 1"):
        patch_file(str(path), "10.28.18.2", "10.1.1.5", occurrences=1)


def test_patch_is_a_noop_when_the_gate_sits_on_the_template_address(tmp_path):
    path = tmp_path / "network"
    path.write_text("ip '10.28.18.2'", encoding="utf-8")

    assert patch_file(str(path), "10.28.18.2", "10.28.18.2") == 0
    assert path.read_text() == "ip '10.28.18.2'"


def test_stage_template_refreshes_then_patches(tmp_path):
    source, dest = make_template(
        tmp_path, {"network": "ip '10.28.18.2'", "other": "untouched"}
    )
    staged = stage_template(
        str(source), str(dest), "network", "10.28.18.2", "10.1.1.5"
    )

    assert os.path.isfile(staged)
    assert (dest / "network").read_text() == "ip '10.1.1.5'"
    assert (dest / "other").read_text() == "untouched"


def test_stage_template_raises_when_the_named_file_is_missing(tmp_path):
    source, dest = make_template(tmp_path, {"other": "x"})
    with pytest.raises(TemplateError, match="not in"):
        stage_template(str(source), str(dest), "network", "a", "b")
