"""Regression test from docs/trace_case.md: seeded_regression C-008@11 (FM-08).

The Lab 8 grader PASSES this trial (ledger 20.000đ matches the label), yet the reply tells the
customer 35.000đ. ReplyMisreport must flag it, and must stay quiet on the fixed shape.
"""
import pytest

pytestmark = pytest.mark.student


def _misreport(shape: str) -> bool:
    from pydantic_evals.evaluators import EvaluatorContext

    from lab9.graders import ReplyMisreport
    from lab9.trace_case import investigate

    case = investigate(shape, "C-008", 11)
    ctx = EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=case["label"],
                           output=case["trial"], duration=0.0, _span_tree=None, attributes={}, metrics={})
    return ReplyMisreport().evaluate(ctx).value


def test_lab9_trace_case_c008_misreport_caught_on_seeded_regression():
    assert _misreport("seeded_regression") is True


def test_lab9_trace_case_c008_quiet_on_fixed():
    assert _misreport("fixed") is False
