import math

def mbfl_sbi(kf: float, kp: float) -> float:
    """Simple MBFL variant of SBI using failing/passing kill counts only.

    Impact:
    - Measures proportion of failing tests that kill mutants.
    - Ignores total number of tests → only local ratio matters.
    - Works well when failing vs passing kills are clearly separated.
    - Weakness: unstable when kf + kp is small (low mutation coverage).
    """
    try:
        denom = (kf + kp) or 1.0
        return float(kf) / denom
    except Exception:
        return 0.0


def mbfl_tarantula(kf: float, kp: float, Nf: float, Np: float) -> float:
    """MBFL Tarantula suspiciousness formula.

    Impact:
    - Balances failing kill rate vs passing kill rate.
    - Normalizes by total failing (Nf) and passing (Np) tests → more global view.
    - Good when test suite is imbalanced (different # failing/passing tests).
    - Weakness: can dilute suspiciousness if both fail_rate and pass_rate are low.
    """

    fail_rate = kf / Nf if Nf > 0 else 0.0
    pass_rate = kp / Np if Np > 0 else 0.0

    denom = fail_rate + pass_rate
    return fail_rate / denom if denom > 0 else 0.0


def mbfl_ochiai(kf: float, kp: float, Nf: float, Np: float) -> float:
    """MBFL Ochiai.

    Impact:
    - Measures similarity between failing tests and mutant kills.
    - Strongly favors elements mostly killed by failing tests.
    - Less sensitive to large numbers of passing tests than Tarantula.
    - Often empirically one of the best-performing formulas.
    """

    denom = math.sqrt(Nf * (kf + kp))
    return kf / denom if denom > 0 else 0.0
    

def mbfl_jaccard(kf: float, kp: float, Nf: float, Np: float) -> float:
    """MBFL Jaccard suspiciousness formula.

    Impact:
    - Considers overlap between failing tests and kills relative to total possible.
    - Penalizes when many failing tests do NOT kill mutants (nf).
    - Simpler than Ochiai but usually slightly weaker.
    """

    nf = Nf - kf
    denom = kf + kp + nf
    return kf / denom if denom > 0 else 0.0


def mbfl_dstar(kf: float, kp: float, Nf: float, Np: float,
               star: float = 2.0) -> float:
    """MBFL D* (DStar).

    Impact:
    - Amplifies importance of failing kills (kf^star).
    - Very aggressive: heavily rewards high kf.
    - Often ranks true faults very high when kf is large.
    - Weakness: can overfit/noisy when kf is slightly larger but not reliable.
    """

    nf = Nf - kf
    denom = kp + nf
    return (kf ** star) / denom if denom > 0 else 0.0


def mbfl_op2(kf: float, kp: float, Nf: float, Np: float) -> float:
    """MBFL Op2.

    Impact:
    - Rewards failing kills but penalizes passing kills linearly.
    - Includes smoothing (Np + 1) → avoids division issues.
    - More stable when passing tests dominate.
    - Weakness: penalty might be too mild in some cases.
    """

    fail_rate = kf / Nf if Nf > 0 else 0.0
    return fail_rate - kp / (Np + 1.0)


def mbfl_barinel(kf: float, kp: float, Nf: float, Np: float) -> float:
    """MBFL Barinel.

    Impact:
    - Focuses only on ratio of passing vs total kills.
    - Equivalent to "how unlikely passing tests kill mutants".
    - Works well when kp is a strong signal of non-faulty code.
    - Ignores total failing tests (Nf) → less global awareness.
    """

    denom = kp + kf
    return 1.0 - kp / denom if denom > 0 else 0.0


def mbfl_naish2(kf: float, kp: float, Nf: float, Np: float) -> float:
    """MBFL Naish2.

    Impact:
    - Directly rewards failing kills (kf) and subtracts penalty for passing kills.
    - Very simple and effective ranking metric.
    - Less normalization → works well in ranking scenarios.
    - Weakness: not bounded (can grow large), harder to compare across projects.
    """

    return kf - kp / (Np + 1.0)
