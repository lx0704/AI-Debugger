import math

def ochiai(ef, ep, Nf, Np):
    """Ochiai.

    Impact:
    - Measures similarity between failing executions and total executions.
    - Strongly rewards elements executed mostly by failing tests.
    - Less affected by large number of passing tests.
    - Empirically one of the most effective SBFL metrics.
    """
    denom = math.sqrt(Nf * (ef + ep)) or 1.0
    return ef / denom


def tarantula(ef, ep, Nf, Np):
    """Tarantula.

    Impact:
    - Compares fail execution rate vs pass execution rate.
    - Normalizes by total failing and passing tests → global perspective.
    - Works well when dataset is imbalanced.
    - Weakness: can reduce suspiciousness when both rates are small.
    """
    a = (ef / Nf) if Nf else 0.0
    b = (ep / Np) if Np else 0.0
    denom = (a + b) or 1.0
    return a / denom


def jaccard(ef, ep, Nf, Np):
    """Jaccard.

    Impact:
    - Measures overlap between failing executions and total relevant executions.
    - Penalizes when many failing tests do NOT execute the element.
    - Simpler than Ochiai but usually slightly less precise.
    """
    nf = Nf - ef
    denom = (ef + ep + nf) or 1.0
    return ef / denom


def sbi(ef, ep, Nf, Np):
    """SBI (Simple Bug Isolation).

    Impact:
    - Uses only local ratio of failing executions over total executions.
    - Very simple and fast.
    - Ignores global test distribution (Nf, Np).
    - Can be unstable when execution counts are low.
    """
    denom = (ef + ep) or 1.0
    return ef / denom


def dstar(ef, ep, Nf, Np, star=2.0):
    """DStar.

    Impact:
    - Exponentially amplifies failing executions (ef^star).
    - Strongly prioritizes elements executed by many failing tests.
    - Often ranks real faults very high.
    - Weakness: can exaggerate noise when ef is slightly higher.
    """
    nf = Nf - ef
    denom = (ep + nf) or 1.0
    return (ef ** star) / denom


def op2(ef, ep, Nf, Np):
    """Op2.

    Impact:
    - Rewards failing execution rate, penalizes passing execution.
    - Uses smoothing (Np + 1) → avoids instability.
    - More robust when many passing tests exist.
    - Weakness: penalty may be too weak in some scenarios.
    """
    fail_rate = (ef / Nf) if Nf else 0.0
    return fail_rate - ep / (Np + 1.0)


def barinel(ef, ep, Nf, Np):
    """Barinel.

    Impact:
    - Focuses on how rarely passing tests execute the element.
    - High score when ep is small relative to ef.
    - Ignores total failing tests (Nf) → less global sensitivity.
    """
    denom = (ep + ef) or 1.0
    return 1.0 - ep / denom


def naish2(ef, ep, Nf, Np):
    """Naish2.

    Impact:
    - Directly rewards failing executions and penalizes passing ones.
    - Simple and effective for ranking suspicious elements.
    - Not normalized → values not comparable across projects.
    - Works well as a strong baseline metric.
    """
    return ef - ep / (Np + 1.0)
