def demo_mix(x: int) -> bool:
    """Method engineered to yield a 2:1 fail/pass kill ratio (mbfl_sbi ≈ 0.6667).

    Structure:
      if x == 3: return True        # mutant 1 (== -> !=) can *repair* baseline failing test
      if x < 0: return True          # mutant 2 (< -> >=) leaves baseline failing test failing
      return x > 10                  # mutant 3 (> -> <=) leaves baseline failing test failing

    Baseline failing test asserts: not demo_mix(3)
    Guard test checks: demo_mix(2) is False, demo_mix(11) is True, demo_mix(-1) is True.

    Mutant behaviors:
      - (== -> !=) Repairs baseline failure (demo_mix(3) becomes False) but causes demo_mix(2) True → new failing guard assertion -> pass bucket.
      - (< -> >=) For x=-1 second clause false (since -1 >= 0 is False) so returns x>10 False path; demo_mix(-1) becomes False (guard expected True) baseline failure persists → fail bucket.
      - (> -> <=) For x=11 final expression False (guard expected True) baseline failure persists → fail bucket.
    => mkf=2, mkp=1, mbfl_sbi=2/3.
    """
    if x == 3:
        return True
    if x < 0:
        return True
    return x > 10


def demo_all_fail(x: int) -> bool:
    """Method engineered so every killed mutant is a *fail* bucket (mbfl_sbi = 1.00).

    Structure:
      if x == 2: return True   # mutant A (== -> !=) creates new failing guard assertion for x=1 but leaves baseline failing test (from demo_mix) untouched
      return x > 5             # mutant B (> -> <=) creates new failing guard assertion for x=6, baseline failing test for demo_mix still failing

    There is NO baseline failing test for this method itself; all fail-bucket kills come from
    (a) baseline failing test in demo_mix still failing, PLUS
    (b) a *new* failing guard assertion for this method.
    Each killed mutant has intersection with the global baseline failing set → bucket=fail.
    """
    if x == 2:
        return True
    return x > 5
