from pathlib import Path

from mediadownloader.utils.filenames import sanitize_filename, unique_path, validate_template


def test_sanitize_windows_filename():
    assert sanitize_filename('a<b>:c"d/e\\f|g?h*') == "a_b__c_d_e_f_g_h_"
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("... ") == "sem_nome"


def test_templates():
    assert validate_template("%(title)s.%(ext)s")[0]
    assert not validate_template("../../%(title)s.%(ext)s")[0]
    assert not validate_template("%(secret)s.%(ext)s")[0]
    assert not validate_template("%(title)s")[0]


def test_unique_path(tmp_path: Path):
    original = tmp_path / "video.mp4"
    original.touch()
    assert unique_path(original).name == "video (1).mp4"

