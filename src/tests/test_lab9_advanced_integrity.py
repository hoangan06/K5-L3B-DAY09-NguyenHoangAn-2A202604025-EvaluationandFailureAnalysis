"""Extra M7 integrity vectors beyond the public traps (hints in CHECKPOINTS: duplicated rows,
evaluator failures on a green run) plus edits a motivated engineer could make to a report."""
import copy
import math

import pytest

pytestmark = pytest.mark.student


def _report(rows, metrics, items=4, seeds=(1, 2), failures=()):
    return {"manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)},
            "rows": rows, "metrics": metrics, "evaluator_failures": list(failures)}


ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": i != 3 or s != 2, "slices": ["denial"] if i < 2 else []}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "eval_set": "data/eval/eval_set_v2.jsonl",
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                     "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "denial", "metric": "pass_rate", "min": 0.9, "blocking": True}]}


@pytest.fixture(scope="module")
def gate():
    from lab9 import gate

    return gate


def base():
    return _report(copy.deepcopy(ROWS), {"pass_rate": 0.875})


def test_advanced_clean_report_is_trusted(gate):
    assert gate.integrity_check(base(), base(), SPEC, SPEC) == []


def test_advanced_duplicated_row_replacing_a_failure(gate):
    rows = [r for r in copy.deepcopy(ROWS) if r["pass_rate"]]
    rows.append(copy.deepcopy(rows[0]))                  # same row count, failing row swapped out
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base(), SPEC)


def test_advanced_evaluator_failures_on_a_green_run(gate):
    rep = _report(copy.deepcopy(ROWS), {"pass_rate": 0.875}, failures=["E-000@1:TrialPass:boom"])
    assert gate.integrity_check(rep, base(), SPEC)


def test_advanced_hand_edited_metric(gate):
    assert gate.integrity_check(_report(copy.deepcopy(ROWS), {"pass_rate": 1.0}), base(), SPEC)


def test_advanced_inf_metric(gate):
    assert gate.integrity_check(_report(copy.deepcopy(ROWS), {"pass_rate": math.inf}), base(), SPEC)


def test_advanced_item_relabelled_out_of_slice(gate):
    rows = copy.deepcopy(ROWS)
    for r in rows:
        if r["item_id"] == "E-001":
            r["slices"] = []
    assert gate.integrity_check(_report(rows, {"pass_rate": 0.875}), base(), SPEC)


@pytest.mark.parametrize("edit", ["drop_nsd", "non_blocking", "drop_metric", "drop_slice", "slice_min", "bump_version"])
def test_advanced_ratchet(gate, edit):
    loose = copy.deepcopy(SPEC)
    if edit == "drop_nsd":
        loose["metrics"][0]["threshold"].pop("no_significant_drop")
    elif edit == "non_blocking":
        loose["metrics"][0]["blocking"] = False
    elif edit == "drop_metric":
        loose["metrics"] = []
    elif edit == "drop_slice":
        loose["slices"] = []
    elif edit == "slice_min":
        loose["slices"][0]["min"] = 0.5
    elif edit == "bump_version":                      # new version label, same eval set
        loose["eval_set_version"] = "v3"
        loose["metrics"][0]["threshold"]["min"] = 0.5
    assert gate.integrity_check(base(), base(), loose, SPEC)


def test_advanced_stricter_spec_is_fine(gate):
    strict = copy.deepcopy(SPEC)
    strict["metrics"][0]["threshold"]["min"] = 0.85
    strict["slices"][0]["no_significant_drop"] = True
    assert gate.integrity_check(base(), base(), strict, SPEC) == []


def test_advanced_nan_row_value_with_edited_total(gate):
    rows = copy.deepcopy(ROWS)
    rows[-1]["pass_rate"] = float("nan")              # the failing row, hidden as NaN
    assert gate.integrity_check(_report(rows, {"pass_rate": 1.0}), base(), SPEC)


def test_advanced_bool_aggregate_metric(gate):
    assert gate.integrity_check(_report(copy.deepcopy(ROWS), {"pass_rate": True}), base(), SPEC)


def test_advanced_gate_blocks_the_two_cases_end_to_end(gate):
    spec = {**SPEC, "slices": []}
    rows = copy.deepcopy(ROWS)
    rows[-1]["pass_rate"] = float("nan")
    for rep in (_report(rows, {"pass_rate": 1.0}), _report(copy.deepcopy(ROWS), {"pass_rate": True})):
        blocked, _ = gate.check(rep, base(), {**spec, "metrics": [{**spec["metrics"][0], "threshold": {"min": 0.9}}]})
        assert blocked == ["integrity"]


@pytest.mark.parametrize("args", [(5.0, 2, 1), (5, 2.0, 1), (float("inf"), 2, 1), (5, 2, float("nan")), (True, 1, 1), ("5", 2, 1)])
def test_advanced_pass_k_rejects_non_integers(args):
    from lab9 import stats

    for fn in (stats.pass_at_k, stats.pass_hat_k):
        with pytest.raises(ValueError):
            fn(*args)
