#!/usr/bin/env python3
"""How the headline-forecast pairs were made, from the Upworthy Research
Archive (https://osf.io/jd64p/, the exploratory packages file; CC BY 4.0).

Two steps, both deterministic:

    build_headline_pairs.py pool <packages.csv> <out.jsonl> <n> <seed> [clear|unpublished]
    build_headline_pairs.py select <clear pool.jsonl> <unpublished pool.jsonl>

``pool`` reads the archive and writes pairs with a clear real winner. A test
qualifies when every package shares one image, excerpt and lede, so the
headline is the only thing that varied, and each headline had at least 1,000
impressions. The pair is the best and the worst headline by click-through
rate, kept when a two-proportion z-test puts the gap at p < 0.001 (strict,
because best against worst of several arms is a picked contrast). In
``unpublished`` mode the test's top performer and any headline flagged as
its winner are left out first: what remains was not what Upworthy went on to
publish. The pools the fixtures came from were written by this step on
2026-11-16 (400 clear pairs, 300 unpublished). Their seeds were not kept, so
``pool`` reproduces the method and not those exact samples; every fixture
row carries its ``source_test_id``, so each pair and its rates can be
checked against the archive directly.

``select`` draws the two fixture files from those pools: no test from the
weeks the archive's authors advise against (2013-06-25 to 2014-01-10), no
test in both files, PAIRS pairs each, the winner on side A in exactly half.
It writes eval_runner/fixtures/headline-forecast/pairs_{clear,unpublished}.jsonl;
run ``scripts/gen_workflow_tasks.py --write`` afterwards.
"""
from __future__ import annotations

import collections
import csv
import json
import math
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "eval_runner" / "fixtures" / "headline-forecast"
MIN_IMPRESSIONS = 1000
P_MAX = 0.001
PAIRS = 100
SELECT_SEED = 20261120
# ISO weeks of the tests the archive's authors advise against using.
DISCOURAGED_WEEKS = (201326, 201402)


def two_sided_p(c1: int, n1: int, c2: int, n2: int) -> float:
    pooled = (c1 + c2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    return math.erfc(abs(c1 / n1 - c2 / n2) / se / math.sqrt(2))


def pool(src: str, out: str, n: int, seed: int, mode: str = "clear") -> None:
    csv.field_size_limit(10**9)
    tests = collections.defaultdict(list)
    with open(src, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            tests[row["clickability_test_id"]].append(row)

    eligible = []
    for test_id, rows in sorted(tests.items()):
        if any(len({r[k] for r in rows}) != 1 for k in ("eyecatcher_id", "excerpt", "lede")):
            continue
        by_headline: dict[str, list[int]] = collections.OrderedDict()
        flagged = set()
        for r in rows:
            head = " ".join(r["headline"].split())
            if not head:
                continue
            if r["winner"] == "True" or r["first_place"] == "True":
                flagged.add(head)
            agg = by_headline.setdefault(head, [0, 0])
            agg[0] += int(r["impressions"])
            agg[1] += int(r["clicks"])
        arms = [(h, imp, clk) for h, (imp, clk) in by_headline.items() if imp >= MIN_IMPRESSIONS]
        if len(arms) < 2:
            continue
        if mode == "unpublished":
            top = max(arms, key=lambda a: a[2] / a[1])
            arms = [a for a in arms if a is not top and a[0] not in flagged]
            if len(arms) < 2:
                continue
        best = max(arms, key=lambda a: a[2] / a[1])
        worst = min(arms, key=lambda a: a[2] / a[1])
        if best[0].lower() == worst[0].lower():
            continue
        p = two_sided_p(best[2], best[1], worst[2], worst[1])
        if p >= P_MAX:
            continue
        eligible.append({
            "test_id": test_id, "arms_in_test": len(arms), "p_value": p, "test_week": rows[0]["test_week"],
            "winner": {"text": best[0], "impressions": best[1], "clicks": best[2]},
            "loser": {"text": worst[0], "impressions": worst[1], "clicks": worst[2]},
        })

    sample = random.Random(seed).sample(eligible, min(n, len(eligible)))
    with open(out, "w", encoding="utf-8") as handle:
        for i, item in enumerate(sample):
            win_ctr = item["winner"]["clicks"] / item["winner"]["impressions"]
            lose_ctr = item["loser"]["clicks"] / item["loser"]["impressions"]
            winner_is_a = i % 2 == 0
            handle.write(json.dumps({
                "pair_id": f"upworthy-{mode}-{item['test_id']}",
                "dataset": "upworthy",
                "a": item["winner"]["text"] if winner_is_a else item["loser"]["text"],
                "b": item["loser"]["text"] if winner_is_a else item["winner"]["text"],
                "answer": "A" if winner_is_a else "B",
                "winner_rate": round(win_ctr, 5),
                "loser_rate": round(lose_ctr, 5),
                "lift": round(win_ctr / lose_ctr, 3) if lose_ctr > 0 else None,
                "p_value": item["p_value"],
                "arms_in_test": item["arms_in_test"],
                "test_week": item["test_week"],
            }, ensure_ascii=False) + "\n")
    print(f"eligible tests: {len(eligible)}; wrote {len(sample)} pairs to {out}")


def _read(path: str) -> list[dict]:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    kept = [row for row in rows if not DISCOURAGED_WEEKS[0] <= int(row["test_week"]) <= DISCOURAGED_WEEKS[1]]
    return sorted(kept, key=lambda row: row["pair_id"])


def _test_id(row: dict) -> str:
    return row["pair_id"].rsplit("-", 1)[-1]


def select(clear_pool: str, unpublished_pool: str) -> None:
    rng = random.Random(SELECT_SEED)
    taken: set[str] = set()
    for name, path in (("clear", clear_pool), ("unpublished", unpublished_pool)):
        chosen = rng.sample([row for row in _read(path) if _test_id(row) not in taken], PAIRS)
        taken |= {_test_id(row) for row in chosen}
        winner_on_a = set(rng.sample(range(PAIRS), PAIRS // 2))
        lines = []
        for index, row in enumerate(chosen):
            winner, loser = (row["a"], row["b"]) if row["answer"] == "A" else (row["b"], row["a"])
            on_a = index in winner_on_a
            lines.append(json.dumps({
                "id": f"P{index + 1:03d}",
                "a": winner if on_a else loser,
                "b": loser if on_a else winner,
                "answer": "A" if on_a else "B",
                "winner_rate": row["winner_rate"],
                "loser_rate": row["loser_rate"],
                "lift": row["lift"],
                "p_value": row["p_value"],
                "arms_in_test": row["arms_in_test"],
                "test_week": row["test_week"],
                "source_test_id": _test_id(row),
            }, ensure_ascii=False))
        (FIXTURE_DIR / f"pairs_{name}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"pairs_{name}.jsonl: {len(lines)} pairs")


def main(argv: list[str]) -> int:
    if len(argv) >= 5 and argv[0] == "pool":
        pool(argv[1], argv[2], int(argv[3]), int(argv[4]), argv[5] if len(argv) > 5 else "clear")
    elif len(argv) == 3 and argv[0] == "select":
        select(argv[1], argv[2])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
