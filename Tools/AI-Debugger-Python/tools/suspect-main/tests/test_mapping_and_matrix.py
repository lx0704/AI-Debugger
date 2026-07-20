from suspect.mapping import MethodIndex
from suspect.matrix import Matrix


def test_method_index_simple_function():
    src = """
def foo():
    x = 1
    return x
"""
    idx = MethodIndex()
    idx.add_file("sample.py", src)
    # All lines in foo should map to the function
    for ln in (2, 3, 4):
        assert idx.index[("sample.py", ln)].endswith(":foo")


def test_matrix_merge_and_headers():
    m = Matrix()
    m.merge({"a": {"x": 1, "y": 2}})
    m.merge({"a": {"y": 3}, "b": {"x": 4}})
    headers = m.headers()
    assert headers[0] == "method"
    assert set(headers[1:]) == {"x", "y"}
    rows = m.to_rows()
    # two methods + header
    assert len(rows) == 3