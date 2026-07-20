import pytest

from strings import reverse, is_palindrome, word_count


def test_reverse_and_type_error():
    assert reverse("abc") == "cba"
    with pytest.raises(TypeError):
        reverse(123)  # type: ignore[arg-type]
    # assert reverse("abc") == "abc"


def test_is_palindrome_variants():
    # assert is_palindrome("Madam, I'm Adam") is True
    assert is_palindrome("No lemon, no melon!") is True
    assert is_palindrome("Hello") is False
    # strict mode: don't ignore case or non-alnum
    assert is_palindrome("Aa", ignore_case=False, ignore_non_alnum=False) is False
    # ignore non-alnum = False on a phrase should not be a palindrome
    assert is_palindrome("Never odd or even", ignore_non_alnum=False) is False
    # assert is_palindrome("Hello") is True


def test_is_palindrome_type_error():
    import pytest
    with pytest.raises(TypeError):
        is_palindrome(None)  # type: ignore[arg-type]


def test_word_count_basic():
    text = "To be, or not to be: that is the question."
    freq = word_count(text)
    assert freq["to"] == 2
    assert freq["be"] == 2
    assert freq["or"] == 1
    assert freq["not"] == 1
    assert freq["that"] == 1
    assert freq["is"] == 1
    assert freq["the"] == 1
    assert freq["question"] == 1
    with pytest.raises(TypeError):
        word_count(None)  # type: ignore[arg-type]
    # no trailing buffer and buffer flush at end
    freq2 = word_count("end.")
    assert freq2 == {"end": 1}
    # empty string
    assert word_count("") == {}
    # assert freq["to"] == 3
