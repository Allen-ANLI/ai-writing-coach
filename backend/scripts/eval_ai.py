"""Real-AI quality evaluation harness (user decision 2026-11-15 §6).

Runs representative datasets against the CONFIGURED provider (deepseek in
dev; mock only validates the harness itself and is never evidence of real
linguistic quality). Records model, prompt version, latency, tokens and
estimated cost per call; writes a JSON report.

Run from backend/:
  .venv\\Scripts\\python.exe scripts\\eval_ai.py [--dataset NAME]

Datasets: grammar_deep_check_v1, teaching_v1 (extended as expression /
evaluation / rewrite services land in Slices 4/7).
"""

import argparse
import json
import pathlib
import sys
import time
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.ai import llm  # noqa: E402
from app.ai.prompts.registry import get_prompt  # noqa: E402
from app.ai.schemas import DeepCheckResult, TeachingContent  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.exceptions import ApiError  # noqa: E402

BACKEND = pathlib.Path(__file__).resolve().parents[1]
DATASETS = BACKEND / "tests" / "evaluation" / "datasets"
REPORTS = BACKEND.parent / "test-results" / "ai-eval"


def eval_deep_check(cases: list[dict]) -> dict:
    prompt = get_prompt("grammar_deep_check", "v1")
    results = []
    for case in cases:
        user_prompt = prompt.user_template.format(
            sentence=case["sentence"],
            paragraph=case["sentence"],
            fragment=case["fragment"],
            rule_message=case["rule_message"],
        )
        started = time.monotonic()
        try:
            parsed, usage = llm.call_llm(
                system=prompt.system, user=user_prompt, response_model=DeepCheckResult
            )
            confirmed = any(i.confirmed for i in parsed.issues)
            results.append(
                {
                    "id": case["id"],
                    "expected_confirmed": case["expected_confirmed"],
                    "confirmed": confirmed,
                    "correct": confirmed == case["expected_confirmed"],
                    "issues": [i.model_dump() for i in parsed.issues],
                    "usage": usage.__dict__,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "error": None,
                }
            )
        except ApiError as exc:
            results.append(
                {"id": case["id"], "error": f"{exc.code}: {exc.message}", "correct": False}
            )
    scored = [r for r in results if "correct" in r and r.get("error") is None]
    tp = sum(1 for r in scored if r["expected_confirmed"] and r["confirmed"])
    fp = sum(1 for r in scored if not r["expected_confirmed"] and r["confirmed"])
    fn = sum(1 for r in scored if r["expected_confirmed"] and not r["confirmed"])
    tn = sum(1 for r in scored if not r["expected_confirmed"] and not r["confirmed"])
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {
        "dataset": "grammar_deep_check_v1",
        "prompt_version": prompt.version,
        "cases": len(cases),
        "errors": len(results) - len(scored),
        "accuracy": (tp + tn) / len(scored) if scored else None,
        "precision": precision,
        "recall": recall,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "results": results,
    }


def eval_teaching(cases: list[dict]) -> dict:
    prompt = get_prompt("teaching", "v1")
    results = []
    for case in cases:
        user_prompt = prompt.user_template.format(
            current_sentence=case["current_sentence"],
            paragraph_context=case["paragraph_context"],
            category=case["category"],
            anchor_text=case["anchor_text"],
            user_current_text=case["user_current_text"],
            weakness_history="none",
        )
        started = time.monotonic()
        try:
            parsed, usage = llm.call_llm(
                system=prompt.system, user=user_prompt, response_model=TeachingContent
            )
            rubric = case["rubric"]
            sentence_words = set(case["current_sentence"].lower().split())
            explanation_text = f"{parsed.why_wrong} {parsed.grammar_rule}".lower()
            mentions = case["anchor_text"].lower() in explanation_text or any(
                w in explanation_text for w in sentence_words if len(w) > 3
            )
            checks = {
                "mentions_fragment_or_sentence": mentions
                if rubric["mentions_fragment_or_sentence"]
                else True,
                "correction_differs_from_anchor": (
                    parsed.recommended_correction.strip().lower()
                    != case["anchor_text"].strip().lower()
                ),
                "min_examples": len(parsed.examples) >= rubric["min_examples"],
                "personalized_note_null_without_history": parsed.personalized_note is None,
            }
            results.append(
                {
                    "id": case["id"],
                    "checks": checks,
                    "score": sum(checks.values()) / len(checks),
                    "output": parsed.model_dump(),
                    "usage": usage.__dict__,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "error": None,
                }
            )
        except ApiError as exc:
            results.append({"id": case["id"], "error": f"{exc.code}: {exc.message}", "score": 0.0})
    scored = [r for r in results if r.get("error") is None]
    return {
        "dataset": "teaching_v1",
        "prompt_version": prompt.version,
        "cases": len(cases),
        "errors": len(results) - len(scored),
        "mean_rubric_score": sum(r["score"] for r in scored) / len(scored) if scored else None,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="all")
    args = parser.parse_args()

    settings = get_settings()
    provider_name = settings.llm_provider
    if provider_name == "mock":
        print("WARNING: mock provider — this validates the harness ONLY, not AI quality.")
    elif not settings.llm_api_key:
        print("LLM_API_KEY missing — place the rotated key in .env first.")
        return 2

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "provider": provider_name,
        "model": settings.llm_model,
        "real_quality_evidence": provider_name != "mock",
        "datasets": [],
    }

    if args.dataset in ("all", "grammar_deep_check_v1"):
        cases = json.loads((DATASETS / "grammar_deep_check_v1.json").read_text("utf-8"))
        report["datasets"].append(eval_deep_check(cases))
    if args.dataset in ("all", "teaching_v1"):
        cases = json.loads((DATASETS / "teaching_v1.json").read_text("utf-8"))
        report["datasets"].append(eval_teaching(cases))

    total_cost = 0.0
    total_calls = 0
    for dataset in report["datasets"]:
        for result in dataset["results"]:
            usage = result.get("usage")
            if usage:
                total_calls += 1
                total_cost += usage.get("estimated_cost") or 0.0
    report["totals"] = {"llm_calls": total_calls, "estimated_cost": total_cost}

    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out = REPORTS / f"eval-{provider_name}-{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")

    for dataset in report["datasets"]:
        print(f"\n{dataset['dataset']} (prompt {dataset['prompt_version']}):")
        for key in ("accuracy", "precision", "recall", "mean_rubric_score"):
            if dataset.get(key) is not None:
                print(f"  {key}: {dataset[key]:.3f}")
        print(f"  cases: {dataset['cases']}, errors: {dataset['errors']}")
    print(f"\nLLM calls: {total_calls}, estimated cost: {total_cost:.6f}")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
