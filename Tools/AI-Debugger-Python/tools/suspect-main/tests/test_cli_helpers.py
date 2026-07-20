from suspect.cli import _looks_like_test_method, _shorten_method


def test_looks_like_test_method():
    assert _looks_like_test_method("tests/test_mod.py:test_func")
    assert _looks_like_test_method("proj/tests/test_mod.py:test_func")
    assert _looks_like_test_method("foo/test_bar.py:test_x")
    assert _looks_like_test_method("test_utils.py:test_y")
    assert not _looks_like_test_method("pkg/mod.py:func")


def test_shorten_method_relpath():
    m = "/home/user/proj/pkg/mod.py:func"
    out = _shorten_method(m, "/home/user/proj")
    assert out.startswith("pkg/mod.py:")