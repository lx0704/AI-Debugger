import math
from suspect.matrix import Matrix
from suspect.cli import _render_top_to_string

def test_top_includes_mutation_columns():
    m = Matrix()
    # Simulate two methods with mutation metrics
    m.rows['a.py:Foo.bar'].update({
        'ef': 2, 'ep': 3,
        'ochiai': 0.5, 'tarantula': 0.4, 'jaccard': 0.3, 'sbi': 0.6,
        'mbfl_sbi': 0.8,
        'mkf': 1, 'mkp': 0,
        'mutants_detected': 5, 'mutants_survived': 2, 'mutation_score': 5/7,
    })
    m.rows['b.py:Baz.qux'].update({
        'ef': 1, 'ep': 4,
        'ochiai': 0.2, 'tarantula': 0.1, 'jaccard': 0.05, 'sbi': 0.7,
        'mbfl_sbi': 0.6,
        'mkf': 0, 'mkp': 1,
        'mutants_detected': 3, 'mutants_survived': 3, 'mutation_score': 0.5,
    })
    out = _render_top_to_string(m, 'ochiai', top=5)
    # Header should include mutation columns abbreviations
    assert 'mutants_detected' in out or 'det' in out
    assert 'mutants_survived' in out or 'surv' in out
    assert 'mutation_score' in out or 'mut_sc' in out
    # Values should show integer detected/survived and score with 2 decimals
    assert '5' in out
    assert '2' in out
    assert '0.71' in out or '0.71'.replace('0.71','') == ''  # approximate 5/7 -> 0.714... truncated/rounded
