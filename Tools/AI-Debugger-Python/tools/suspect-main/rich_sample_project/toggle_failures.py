#!/usr/bin/env python3
"""
Toggle intentional failing tests in rich_sample_project on/off.

Usage:
  python toggle_failures.py on     # enable failing tests
  python toggle_failures.py off    # disable failing tests
  python toggle_failures.py status # show current state
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEST_FILES = {
    # legacy core sample toggles
    ROOT / "test_all.py": [
        "assert acc.withdraw(70) == 70",
        "assert fib(7) == 14",
        "assert not demo_flag(3)",
        "assert not demo_mix(3)",
    ],
    # new sample modules toggles
    ROOT / "test_strings.py": [
        'assert reverse("abc") == "abc"',
        'assert is_palindrome("Hello") is True',
        'assert is_palindrome("Madam, I\'m Adam") is True',
        'assert freq["to"] == 3',
    ],
    ROOT / "test_math_extra.py": [
        "assert gcd(54, 24) == 5",
        "assert mean([1, 2, 3, 4]) == 3.0",
    ],
    ROOT / "test_shopping.py": [
        "assert round(c.subtotal(), 2) == 0.0",
        "assert total == 0.00",
    ],
}


def read_lines(p: Path):
    return p.read_text(encoding="utf-8").splitlines(True)


def write_lines(p: Path, lines):
    p.write_text("".join(lines), encoding="utf-8")


def _strip_leading_comment(s: str) -> tuple[bool, str]:
    s2 = s.lstrip()
    if s2.startswith("#"):
        # remove a single leading comment marker and following space if present
        s2 = s2[1:]
        if s2.startswith(" "):
            s2 = s2[1:]
        return True, s2
    return False, s2


def _split_trailing_comment(s: str) -> tuple[str, str]:
    """Split into (code, trailing_comment_with_prefix_or_empty).

    We consider the first unescaped '#' as the start of trailing comment.
    For our simple assert lines, this is sufficient.
    """
    if "#" not in s:
        return s.rstrip(), ""
    code, comment = s.split("#", 1)
    return code.rstrip(), ("#" + comment.rstrip())


def _matches_target(line: str, target: str) -> bool:
    stripped = line.rstrip("\n")
    _had_hash, body = _strip_leading_comment(stripped)
    code, _comment = _split_trailing_comment(body)
    return code.strip() == target


def _is_uncommented(line: str, target: str) -> bool:
    stripped = line.rstrip("\n")
    # if it starts with a comment, it's commented
    if stripped.lstrip().startswith("#"):
        return False
    # check the code portion contains the target
    code, _comment = _split_trailing_comment(stripped)
    return target in code


def _toggle_line(line: str, target: str, enable: bool) -> str:
    # Preserve indentation and trailing comment
    nl = "\n" if line.endswith("\n") else ""
    prefix = line[: len(line) - len(line.lstrip(" "))]
    stripped = line[len(prefix):].rstrip("\n")
    had_hash, body = _strip_leading_comment(stripped)
    code, tail_comment = _split_trailing_comment(body)
    if target not in code:
        return line
    if enable:
        # ensure uncommented
        new_body = f"{target}"
    else:
        # ensure commented
        new_body = f"# {target}"
    if tail_comment:
        new_body = f"{new_body}  {tail_comment}"
    return f"{prefix}{new_body}{nl}"


def toggle(enable: bool) -> bool:
    overall_changed = False
    for path, targets in TEST_FILES.items():
        lines = read_lines(path)
        changed = False
        new_lines = []
        for line in lines:
            out = line
            for t in targets:
                if _matches_target(line, t):
                    out = _toggle_line(line, t, enable)
                    if out != line:
                        changed = True
                    break
            new_lines.append(out)
        if changed:
            write_lines(path, new_lines)
            overall_changed = True
    return overall_changed


def status() -> str:
    # If any target in any file is uncommented, consider failures enabled
    for path, targets in TEST_FILES.items():
        lines = read_lines(path)
        for line in lines:
            for t in targets:
                if _matches_target(line, t) and _is_uncommented(line, t):
                    return "on"
    return "off"


def main():
    ap = argparse.ArgumentParser(description="Toggle failing tests in rich_sample_project")
    ap.add_argument("mode", choices=["on", "off", "status"], help="Toggle mode")
    args = ap.parse_args()
    if args.mode == "status":
        print(status())
        return
    enable = args.mode == "on"
    changed = toggle(enable)
    print(f"failures {'enabled' if enable else 'disabled'}" + (" (changed)" if changed else " (no changes)"))


if __name__ == "__main__":
    main()
