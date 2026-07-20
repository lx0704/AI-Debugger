from sorting import insertion_sort, merge_sort, quick_sort


def test_insertion_sort_basic():
    assert insertion_sort([3, 1, 2]) == [1, 2, 3]
    assert insertion_sort([]) == []
    assert insertion_sort([1]) == [1]


def test_merge_sort_basic():
    assert merge_sort([5, 3, 8, 1, 2]) == [1, 2, 3, 5, 8]
    assert merge_sort([2, 2, 1]) == [1, 2, 2]


def test_quick_sort_basic():
    assert quick_sort([10, -1, 2, 5, 0]) == [-1, 0, 2, 5, 10]
    assert quick_sort([3, 3, 3]) == [3, 3, 3]
