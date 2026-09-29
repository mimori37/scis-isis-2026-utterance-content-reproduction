#!/usr/bin/env python3
"""Recompute every reported number that does not depend on withheld text.

    python3 reproduce_paper_results.py

Reads only derived/*.tsv. No third-party packages. Each section prints the paper
table or figure it backs, so the printed value can be compared with the paper
directly. Aggregation rules are the ones stated in the paper:

  content-reproduction rate  per judgment item 1 / 0.5 / 0, macro-averaged over
                             cases; main aggregate is n=11 (u017 excluded)
  pairwise                   a winner counts only when both presentation orders
                             agree, otherwise the pair is unstable
  LLM majority               two or more of the three judges agreeing on the same
                             stable outcome; three different outcomes is unstable
  direction agreement        tie and unstable folded into "no difference"
"""
import csv
from collections import defaultdict
from pathlib import Path

D = Path(__file__).resolve().parent / "derived"
CONDS = ["c_inner", "c_style"]
FINAL_GEN = {"c_inner": 3, "c_style": 4}
JUDGES = ["gpt-5.5", "opus-4.8", "gemini-3.1-pro"]
SCORE = {"○": 1.0, "△": 0.5, "×": 0.0}


def load(name):
    with (D / name).open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def head(title):
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


# ---------------------------------------------------------------- Table III
def table_iii():
    head("Table III  content-reproduction rate by generation (main aggregate, n=11)")
    rows = [r for r in load("absolute_scores.tsv") if r["in_main_aggregate"] == "yes"]
    by = defaultdict(list)
    for r in rows:
        by[(r["condition"], r["scorer"], int(r["generation"]))].append(float(r["content_rate"]))
    print(f"{'prompt':9s} {'scored by':10s} " + " ".join(f"gen{g}   " for g in range(5)))
    for c in CONDS:
        for s in ("auto", "human"):
            cells = []
            for g in range(5):
                v = by.get((c, s, g))
                cells.append(f"{mean(v):.3f}" + ("*" if g == FINAL_GEN[c] else " ")
                             if v else "---  ")
            print(f"{c:9s} {s:10s} " + "  ".join(cells))
    print("  * = final generation of that condition; n per cell =",
          len({r['target_id'] for r in rows}))


# ------------------------------------------------------- pairwise foundation
def stable_outcomes():
    """(target, condition, judge) -> gen0 | final | tie | unstable."""
    per = defaultdict(dict)
    for r in load("pairwise_judgments.tsv"):
        per[(r["target_id"], r["condition"], r["judge"])][r["presentation_order"]] = r["winner"]
    out = {}
    for k, v in per.items():
        assert set(v) == {"normal", "swap"}, f"missing an order for {k}"
        out[k] = v["normal"] if v["normal"] == v["swap"] else "unstable"
    return out


def majority(outcomes, target, cond):
    picks = [outcomes[(target, cond, j)] for j in JUDGES]
    for p in set(picks):
        if picks.count(p) >= 2:
            return p
    return "unstable"


def pair_keys(outcomes):
    return sorted({(t, c) for t, c, _ in outcomes})


# ------------------------------------------------------------------- Fig. 2
def fig_2(outcomes, pairs):
    head("Fig. 2  final vs gen0: distribution of stable outcomes over 22 pairs")
    order = ["final", "tie", "gen0", "unstable"]
    print(f"{'judge':16s} " + " ".join(f"{k:>9s}" for k in order) + "    total")
    for j in JUDGES + ["majority", "human"]:
        if j == "majority":
            picks = [majority(outcomes, t, c) for t, c in pairs]
        else:
            picks = [outcomes[(t, c, j)] for t, c in pairs]
        counts = [picks.count(k) for k in order]
        print(f"{j:16s} " + " ".join(f"{n:9d}" for n in counts) + f"    {sum(counts):5d}")


# ------------------------------------------------------------------- Fig. 3
def fig_3():
    head("Fig. 3  generation trajectory (auto and human) and new-rule count")
    rows = [r for r in load("absolute_scores.tsv") if r["in_main_aggregate"] == "yes"]
    by = defaultdict(list)
    for r in rows:
        by[(r["condition"], r["scorer"], int(r["generation"]))].append(float(r["content_rate"]))
    nr = {(r["condition"], int(r["generation"])): int(r["new_rules"])
          for r in load("new_rule_counts.tsv")}
    for c in CONDS:
        gens = range(FINAL_GEN[c] + 1)
        auto = [f"{mean(by[(c, 'auto', g)]):.3f}" for g in gens]
        human = [f"{mean(by[(c, 'human', g)]):.3f}" if by.get((c, "human", g)) else "  -  "
                 for g in gens]
        print(f"{c:9s} auto      " + "  ".join(auto))
        print(f"{c:9s} human     " + "  ".join(human))
        print(f"{c:9s} new rules " + "  ".join(f"{nr[(c, g)]:5d}" for g in gens))


# ------------------------------------------------------------------- Fig. 4
def fig_4():
    head("Fig. 4  character-prompt length by generation (tiktoken o200k_base)")
    by = defaultdict(dict)
    for r in load("character_prompt_length.tsv"):
        by[r["condition"]][int(r["generation"])] = int(r["prompt_tokens_o200k_base"])
    for c in CONDS:
        gens = sorted(by[c])
        print(f"{c:9s} " + "  ".join(f"{by[c][g]:5d}" for g in gens)
              + f"    (gen0 -> final: x{by[c][max(gens)] / by[c][0]:.1f})")


# ------------------------------------------------------------------- Fig. 5
def fig_5(outcomes, pairs):
    head("Fig. 5  judge-human agreement over 22 pairs")

    def direction(x):
        return "nodiff" if x in ("tie", "unstable") else x

    print(f"{'judge':16s} {'direction':>10s} {'exact':>8s}")
    for j in JUDGES + ["majority"]:
        d = e = 0
        for t, c in pairs:
            h = outcomes[(t, c, "human")]
            m = majority(outcomes, t, c) if j == "majority" else outcomes[(t, c, j)]
            d += direction(m) == direction(h)
            e += m == h
        print(f"{j:16s} {d:7d}/{len(pairs)} {e:5d}/{len(pairs)}")
    nd = sum(direction(outcomes[(t, c, 'human')]) == "nodiff" for t, c in pairs)
    print(f"{'always-nodiff':16s} {nd:7d}/{len(pairs)}     (baseline for the human column)")
    rev = [(t, c) for t, c in pairs
           if {direction(outcomes[(t, c, 'human')]),
               direction(majority(outcomes, t, c))} == {"gen0", "final"}]
    print("  clear reversals (human vs LLM majority):", rev or "none")


# --------------------------------------------------- Fig. 6 and Table V
def spearman(pairs):
    n = len(pairs)

    def ranks(v):
        o = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2.0 + 1.0
            i = j + 1
        return r
    x, y = [p[0] for p in pairs], [p[1] for p in pairs]
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    return num / (dx * dy)


def fig_6_and_table_v():
    rows = load("context_sufficiency.tsv")
    g0 = {r["item_id"]: mean([SCORE[r["c_inner_gen0"]], SCORE[r["c_style_gen0"]]]) for r in rows}
    fin = {r["item_id"]: mean([SCORE[r["c_inner_final"]], SCORE[r["c_style_final"]]]) for r in rows}

    head("Fig. 6  content reproduction by author-rated scene-context sufficiency")
    print(f"{'level':>5s} {'n':>3s} {'gen0':>7s} {'final':>7s} {'missing(final)':>15s}")
    for lvl in (3, 2, 1, 0):
        grp = [r for r in rows if int(r["sufficiency_level"]) == lvl]
        if not grp:
            continue
        finals = [SCORE[r[c]] for r in grp for c in ("c_inner_final", "c_style_final")]
        print(f"{lvl:5d} {len(grp):3d} {mean([g0[r['item_id']] for r in grp]):7.3f} "
              f"{mean([fin[r['item_id']] for r in grp]):7.3f} "
              f"{finals.count(0.0) / len(finals):15.3f}")
    rho = spearman([(int(r["sufficiency_level"]), fin[r["item_id"]]) for r in rows])
    print(f"  Spearman rho(sufficiency, final reproduction) = {rho:.3f}  (n={len(rows)})")

    head("Table V  reproduction by deficit type among sufficiency-level-1 items")
    print(f"{'deficit type':22s} {'n':>3s} {'final reproduction':>19s}")
    lvl1 = [r for r in rows if int(r["sufficiency_level"]) == 1]
    for cat in sorted({r["deficit_category"] for r in lvl1}):
        grp = [r for r in lvl1 if r["deficit_category"] == cat]
        print(f"{cat:22s} {len(grp):3d} {mean([fin[r['item_id']] for r in grp]):19.3f}")


def main():
    outcomes = stable_outcomes()
    pairs = pair_keys(outcomes)
    table_iii()
    fig_2(outcomes, pairs)
    fig_3()
    fig_4()
    fig_5(outcomes, pairs)
    fig_6_and_table_v()
    print()


if __name__ == "__main__":
    main()
