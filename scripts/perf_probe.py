"""Non-AI endpoint latency probe (Slice 11b, Directive §I performance report).

Registers a throwaway user against the running dev backend, exercises the key
non-AI endpoints N times each, and reports P50/P95/max. Target: P95 < 500 ms.
Writes a JSON report to test-results/perf/.

    python scripts/perf_probe.py [--base-url http://127.0.0.1:8000/api/v1] [--n 30]
"""

import argparse
import json
import pathlib
import statistics
import time
import uuid

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))
    return ordered[idx]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--n", type=int, default=30)
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=30)
    email = f"perf-{uuid.uuid4().hex[:10]}@example.com"
    password = "PerfProbePassword123"

    reg = client.post("/auth/register", json={"email": email, "password": password})
    reg.raise_for_status()
    headers = {"Authorization": f"Bearer {reg.json()['data']['access_token']}"}

    essay = client.post(
        "/essays", json={"writing_type": "free_writing", "title": "perf"}, headers=headers
    )
    essay.raise_for_status()
    essay_id = essay.json()["data"]["id"]

    def timed(method: str, path: str, **kwargs) -> float:
        started = time.perf_counter()
        response = client.request(method, path, headers=headers, **kwargs)
        elapsed = (time.perf_counter() - started) * 1000
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:200]}")
        return elapsed

    doc = client.get(f"/essays/{essay_id}/working-document", headers=headers).json()["data"]
    revision = doc["server_revision"]

    scenarios: dict[str, list[float]] = {}

    def run(name: str, method: str, path: str, **kwargs) -> None:
        samples = []
        for _ in range(args.n):
            samples.append(timed(method, path, **kwargs))
        scenarios[name] = samples

    run("GET /essays", "GET", "/essays")
    run("GET /essays/{id}", "GET", f"/essays/{essay_id}")
    run("GET working-document", "GET", f"/essays/{essay_id}/working-document")

    saves = []
    for i in range(args.n):
        payload = {
            "base_revision": revision,
            "client_revision": i + 1,
            "content_json": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": f"Perf sample {i}."}]}
                ],
            },
        }
        started = time.perf_counter()
        response = client.put(
            f"/essays/{essay_id}/working-document", json=payload, headers=headers
        )
        saves.append((time.perf_counter() - started) * 1000)
        response.raise_for_status()
        revision = response.json()["data"]["server_revision"]
    scenarios["PUT working-document (autosave)"] = saves

    run("POST snapshot", "POST", f"/essays/{essay_id}/snapshots",
        json={"version_type": "checkpoint", "source_revision": revision})
    run("GET versions", "GET", f"/essays/{essay_id}/versions")
    run("GET /ielts/questions", "GET", "/ielts/questions?limit=20")
    run("GET /ielts/tags", "GET", "/ielts/tags")
    run("GET /billing/plans", "GET", "/billing/plans")
    run("GET /learning/summary", "GET", "/learning/summary")
    run("GET /users/me", "GET", "/users/me")

    report = {}
    print(f"{'endpoint':<38}{'p50':>9}{'p95':>9}{'max':>9}")
    for name, samples in scenarios.items():
        p50 = percentile(samples, 50)
        p95 = percentile(samples, 95)
        mx = max(samples)
        report[name] = {
            "samples": len(samples),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "max_ms": round(mx, 2),
            "mean_ms": round(statistics.mean(samples), 2),
        }
        print(f"{name:<38}{p50:>8.1f} {p95:>8.1f} {mx:>8.1f}")

    worst_p95 = max(item["p95_ms"] for item in report.values())
    report["_meta"] = {
        "base_url": args.base_url,
        "n_per_endpoint": args.n,
        "worst_p95_ms": worst_p95,
        "target_p95_ms": 500,
        "target_met": worst_p95 < 500,
    }
    out = ROOT / "test-results" / "perf" / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nworst P95 = {worst_p95:.1f} ms (target < 500 ms) -> {'PASS' if worst_p95 < 500 else 'FAIL'}")
    print(f"report: {out}")

    # Clean up the throwaway account.
    client.delete("/users/me", headers=headers)
    client.close()
    return 0 if worst_p95 < 500 else 1


if __name__ == "__main__":
    raise SystemExit(main())
