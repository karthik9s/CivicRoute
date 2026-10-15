"""Evaluate intent routing, retrieval and answers against eval/golden.jsonl.

    python -m eval.run_eval            # uses the configured store / embedder / LLM
    python -m eval.run_eval --no-llm   # retrieval + extractive answers only (free)

Metrics
  intent@1      top predicted service == expected service
  intent@3      expected service within top 3
  retrieval@k   at least one of the top-k chunks is tagged with the expected service (or is general)
  must-contain  answer contains every required fact string (case-insensitive)
  cited         answer cites at least one source [n]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--out", default=str(Path(__file__).with_name("results.json")))
    args = ap.parse_args()
    if args.no_llm:
        os.environ["LLM_PROVIDER"] = "none"

    from app.intent import detect_intent
    from app.rag import answer, route_and_retrieve

    golden = [json.loads(l) for l in Path(__file__).with_name("golden.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows, t0 = [], time.time()
    for g in golden:
        intents = [r["service_id"] for r in detect_intent(g["q"], top_n=3)]
        hits, _ = route_and_retrieve(g["q"])
        exp = g["service"]
        retr_ok = exp is None or any(exp in h.chunk.service_ids or not h.chunk.service_ids for h in hits)
        res = answer(g["q"], service_id=None)
        text = res["answer"]
        must_ok = all(m.lower() in text.lower() for m in g["must"])
        rows.append({"q": g["q"], "expected": exp, "intent": intents, "intent1": exp is None or intents[0] == exp,
                     "intent3": exp is None or exp in intents, "retrieval": retr_ok, "must": must_ok,
                     "cited": bool(re.search(r"\[\d+\]", text)), "mode": res["mode"], "answer": text})

    def pct(key, subset=None):
        sub = [r for r in rows if subset is None or subset(r)]
        return round(100 * sum(r[key] for r in sub) / max(1, len(sub)), 1)

    summary = {"n": len(rows), "intent@1": pct("intent1", lambda r: r["expected"]), "intent@3": pct("intent3", lambda r: r["expected"]),
               "retrieval@6": pct("retrieval"), "must_contain": pct("must"), "cited": pct("cited"),
               "mode": rows[0]["mode"] if rows else None, "seconds": round(time.time() - t0, 1)}
    Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    for r in rows:
        flags = "".join(["" if r["intent1"] else " INTENT", "" if r["retrieval"] else " RETRIEVAL", "" if r["must"] else " MISSING-FACT"])
        if flags:
            print(f"-{flags}: {r['q']}  (expected {r['expected']}, got {r['intent'][:2]})")


if __name__ == "__main__":
    main()
