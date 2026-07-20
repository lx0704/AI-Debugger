from suspect.adapters.coverage_sbfl import _parse_pytest_junit
import tempfile, textwrap, pathlib


def test_parse_pytest_junit_counts():
    xml = textwrap.dedent(
        """
        <testsuite tests="3" failures="1">
          <testcase classname="t" name="test_ok"/>
          <testcase classname="t" name="test_fail"><failure/></testcase>
          <testcase classname="t" name="test_ok2"/>
        </testsuite>
        """
    )
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "junit.xml"
        p.write_text(xml)
        Nf, Np, failing, passing = _parse_pytest_junit(str(p))
        assert Nf == 1
        assert Np == 2
        assert "test_fail" in failing
        assert "test_ok" in passing and "test_ok2" in passing