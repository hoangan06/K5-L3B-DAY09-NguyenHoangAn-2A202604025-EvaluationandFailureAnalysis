"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]

    # 1. aggregate metrics must be finite numbers: NaN compares False against any floor, and a
    #    bool compares as 0/1 (True passes "min 0.9"). None only means "not computed".
    for k, v in (pr.get("metrics") or {}).items():
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            problems.append(f"metric {k} = {v!r} is not a finite number")

    # 2. graders must not have crashed: no evaluator failures, no None for a graded metric.
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s) in the PR report")
    missing = [(r.get("item_id"), r.get("seed"), m) for r in pr.get("rows", []) for m in graded
               if r.get(m) is None]
    if missing:
        problems.append(f"{len(missing)} graded value(s) missing (None), first {missing[0]}")
    # A grader returns a bool per row; anything else (NaN, 0.5, "True") is not a grader result.
    malformed = [(r.get("item_id"), r.get("seed"), m, r.get(m)) for r in pr.get("rows", []) for m in graded
                 if r.get(m) is not None and not isinstance(r.get(m), bool)]
    if malformed:
        problems.append(f"{len(malformed)} graded value(s) are not booleans, first {malformed[0]}")

    # 3. rows must cover exactly items x seeds, once each, and the same (item, seed) set as main.
    for name, rep in (("PR", pr), ("baseline", base)):
        man = rep.get("manifest") or {}
        want = int(man.get("items") or 0) * len(man.get("seeds") or [])
        keys = [(r.get("item_id"), r.get("seed")) for r in rep.get("rows", [])]
        if len(keys) != want:
            problems.append(f"{name} has {len(keys)} rows, manifest says {want} (items x seeds)")
        if len(set(keys)) != len(keys):
            problems.append(f"{name} has {len(keys) - len(set(keys))} duplicated (item, seed) row(s)")
        if {r.get("seed") for r in rep.get("rows", [])} != set(man.get("seeds") or []):
            problems.append(f"{name} row seeds differ from its manifest seeds")
    pr_keys = {(r.get("item_id"), r.get("seed")) for r in pr.get("rows", [])}
    base_keys = {(r.get("item_id"), r.get("seed")) for r in base.get("rows", [])}
    if pr_keys != base_keys:
        problems.append(f"(item, seed) set differs from the baseline's: {len(base_keys - pr_keys)} missing, "
                        f"{len(pr_keys - base_keys)} extra")
    pm, bm = pr.get("manifest") or {}, base.get("manifest") or {}
    if pm.get("items") != bm.get("items") or sorted(pm.get("seeds") or []) != sorted(bm.get("seeds") or []):
        problems.append("manifest items/seeds differ from the baseline's")

    # 4. slice tags are fixed by the label, not by the PR.
    base_tags = {r.get("item_id"): sorted(r.get("slices") or []) for r in base.get("rows", [])}
    relabelled = sorted({r.get("item_id") for r in pr.get("rows", [])
                         if r.get("item_id") in base_tags and sorted(r.get("slices") or []) != base_tags[r.get("item_id")]})
    if relabelled:
        problems.append(f"slice tags differ from the baseline's for {len(relabelled)} item(s), first {relabelled[0]}")

    # 5. reported metrics must be what the rows say (a hand-edited number is not evidence).
    rows = pr.get("rows") or []
    if rows and not missing and not malformed:
        in_spec = {m["id"] for m in spec.get("metrics", [])}
        reported = pr.get("metrics") or {}
        for k, want in _recompute(rows, graded, spec.get("pass_k", [])).items():
            if want is None or (k not in in_spec and k not in reported):
                continue                              # derived metric the report never claimed
            if not math.isfinite(want):
                problems.append(f"metric {k} recomputed from the rows is {want}")
                continue
            got = reported.get(k)
            if got is None or isinstance(got, bool) or not isinstance(got, (int, float)) \
                    or not math.isfinite(got) or abs(got - want) > 1e-3:
                problems.append(f"metric {k} = {got!r} but the rows give {want}")

    # 6. ratchet: on the same eval-set version a threshold may only get stricter. Bumping the
    #    version string while the eval set itself is unchanged is the same eval set.
    if base_spec is not None:
        same_version = base_spec.get("eval_set_version") == spec.get("eval_set_version")
        same_set = (spec.get("eval_set") is not None and spec.get("eval_set") == base_spec.get("eval_set")
                    and pm.get("eval_set_sha") == bm.get("eval_set_sha"))
        if not same_version and same_set:
            problems.append("ratchet: eval_set_version changed but the eval set is the same file and sha")
        if same_version or same_set:
            problems += _ratchet(spec, base_spec)
    return problems


def _recompute(rows: list[dict], graded: list[str], k_values: list[int]) -> dict[str, float | None]:
    """Same rules as lab9.eval.aggregate, limited to what the rows alone determine."""
    out: dict[str, float | None] = {}
    for m in graded:
        vals = [r[m] for r in rows if r.get(m) is not None]
        if m in ("secret_leak", "approval_bypass"):
            out[m] = float(sum(vals))
        else:
            out[m] = round(sum(vals) / len(vals), 4) if vals else None
    if "pass_rate" in graded:
        by_item: dict[str, list[bool]] = {}
        for r in rows:
            by_item.setdefault(r["item_id"], []).append(bool(r.get("pass_rate")))
        out["pass_5"] = round(sum(all(v) for v in by_item.values()) / len(by_item), 4) if by_item else None
        for k in k_values:
            if not by_item or min(len(v) for v in by_item.values()) < k:
                continue
            for name, fn in (("pass_at", stats.pass_at_k), ("pass_hat", stats.pass_hat_k)):
                try:
                    est = [fn(len(v), sum(v), k) for v in by_item.values()]
                except (NotImplementedError, ValueError):
                    continue
                out[f"{name}_{k}"] = round(sum(est) / len(est), 4)
    return out


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    problems: list[str] = []

    def compare(kind: str, key: str, new: dict | None, old: dict) -> None:
        label = f"{kind} {key}"
        if new is None:
            problems.append(f"ratchet: {label} was removed")
            return
        if old.get("blocking") and not new.get("blocking"):
            problems.append(f"ratchet: {label} is no longer blocking")
        th_new = new.get("threshold", new) if kind == "metric" else new
        th_old = old.get("threshold", old) if kind == "metric" else old
        for bound in ("max", "max_increase"):
            if bound in th_old and (bound not in th_new or th_new[bound] > th_old[bound]):
                problems.append(f"ratchet: {label} {bound} loosened {th_old[bound]} -> {th_new.get(bound)}")
        if "min" in th_old and ("min" not in th_new or th_new["min"] < th_old["min"]):
            problems.append(f"ratchet: {label} min loosened {th_old['min']} -> {th_new.get('min')}")
        if th_old.get("no_significant_drop") and not th_new.get("no_significant_drop"):
            problems.append(f"ratchet: {label} dropped no_significant_drop")

    new_metrics = {m["id"]: m for m in spec.get("metrics", [])}
    for m in base_spec.get("metrics", []):
        compare("metric", m["id"], new_metrics.get(m["id"]), m)
    new_slices = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        compare("slice", f"{s['name']}/{s['metric']}", new_slices.get((s["name"], s["metric"])), s)
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        sid = f"slice:{name}/{metric}"
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        verdict, note = "ok", ""
        val = round(sum(a.values()) / len(a), 4) if a else None
        if val is None:
            verdict = "missing"
        elif "min" in sl and val < sl["min"]:
            verdict = "fail"
        elif "max" in sl and val > sl["max"]:
            verdict = "fail"
        if sl.get("no_significant_drop") and a and b:
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        th = {k: sl[k] for k in ("min", "max", "no_significant_drop") if k in sl}
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        lines.append(f"  {sid:<42} {val!s:<8} n={len(a):<3} {json.dumps(th):<36} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
