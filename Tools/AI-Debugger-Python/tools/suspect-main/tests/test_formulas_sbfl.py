import math
from suspect.formulas import sbfl as F


def test_formulas_basic_pass_fail():
    # One failing execution only
    ef, ep, Nf, Np = 1, 0, 1, 3
    assert F.ochiai(ef, ep, Nf, Np) == 1.0
    assert F.tarantula(ef, ep, Nf, Np) == 1.0
    assert F.jaccard(ef, ep, Nf, Np) == 1.0
    assert F.sbi(ef, ep, Nf, Np) == 1.0

    # Only passing executions
    ef, ep, Nf, Np = 0, 2, 1, 3
    assert F.ochiai(ef, ep, Nf, Np) == 0.0
    assert F.tarantula(ef, ep, Nf, Np) == 0.0
    assert F.jaccard(ef, ep, Nf, Np) == 0.0
    assert F.sbi(ef, ep, Nf, Np) == 0.0
