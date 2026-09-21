"""人手採点(blind)を un-blind し、自動(絶対rubric)との一致を出す。

- eval/human/<label>/answer.tsv（著者記入）＋ _mapping.tsv（A/B→世代）を読む。
- A/B を世代に戻し、人手の content_rate / style を gen0・最終 ごとに復元。
- 自動 rubric_gen{0}.tsv / rubric_gen{final}.tsv の同 id と突き合わせ。
- content_rate（連続）= Spearman 順位相関、style（順序0-2）= 二次重み付きκ を手計算（補助指標）。
- flagged（eval/flagged_test_ids.tsv）は相関から除外。人手 gen0 vs 最終 の平均も出す。

使い方:
  CHARAGEN_STUDY=study03_baseline-replay python scripts/eval_human_vs_auto.py --label condA --gen0 0 --final 3
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY = os.environ.get("CHARAGEN_STUDY", "study02_script-replay")
RUNS = ROOT / "experiments" / STUDY / "runs"
EVAL = ROOT / "experiments" / STUDY / "eval"


def frac(s: str):
    """'2/3' か '0.67' を float に。空なら None。"""
    s = (s or "").strip()
    if not s:
        return None
    if "/" in s:
        a, b = s.split("/", 1)
        a, b = a.strip(), b.strip()
        if not a:
            return None
        return float(a) / float(b)
    return float(s)


def load_flagged():
    p = EVAL / "flagged_test_ids.tsv"
    out = set()
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip() and not ln.startswith("id\t"):
                out.add(ln.split("\t", 1)[0].strip())
    return out


def read_rows(p: Path):
    rows = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("id\t"):
            continue
        c = ln.split("\t")
        rows[c[0].strip()] = c
    return rows


def auto_rubric(ts, gen):
    """id -> (content_rate, style) from rubric_gen{gen}.tsv"""
    p = RUNS / ts / "eval" / f"rubric_gen{gen}.tsv"
    out = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("id\t"):
            continue
        c = ln.split("\t")
        try:
            out[c[0].strip()] = (float(c[1]), float(c[2]))
        except (ValueError, IndexError):
            pass
    return out


def spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    return None if dx == 0 or dy == 0 else num / (dx * dy)


def qwk(a, b, K=3):
    """二次重み付きκ（カテゴリ 0..K-1）。"""
    n = len(a)
    if n == 0:
        return None
    O = [[0] * K for _ in range(K)]
    for x, y in zip(a, b):
        O[x][y] += 1
    ra = [sum(O[i]) for i in range(K)]
    cb = [sum(O[i][j] for i in range(K)) for j in range(K)]
    num = den = 0.0
    for i in range(K):
        for j in range(K):
            w = (i - j) ** 2
            e = ra[i] * cb[j] / n
            num += w * O[i][j]
            den += w * e
    return None if den == 0 else 1 - num / den


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--gen0", type=int, default=0)
    ap.add_argument("--final", type=int, required=True)
    ap.add_argument("--ts", required=True)
    args = ap.parse_args()

    hdir = EVAL / "human" / args.label
    ans = read_rows(hdir / "answer.tsv")
    mp = read_rows(hdir / "_mapping.tsv")    # id -> [id, A_gen, B_gen]
    flagged = load_flagged()
    auto0 = auto_rubric(args.ts, args.gen0)
    autoF = auto_rubric(args.ts, args.final)

    # 人手を世代へ un-blind
    hum = {}  # id -> {gen0:(c,s), final:(c,s)}
    for uid, c in ans.items():
        if uid not in mp:
            continue
        Agen, Bgen = mp[uid][1], mp[uid][2]
        Ac, As, Bc, Bs = frac(c[1]), c[2].strip(), frac(c[3]), c[4].strip()
        d = {}
        if Ac is not None and As != "":
            d[Agen] = (Ac, float(As))
        if Bc is not None and Bs != "":
            d[Bgen] = (Bc, float(Bs))
        hum[uid] = d

    g0k, gFk = f"gen{args.gen0}", f"gen{args.final}"
    # 相関用ペア（flagged除外・両世代プール）
    hc, ac, hs, as_ = [], [], [], []
    h0c, hFc, h0s, hFs = [], [], [], []
    for uid, d in hum.items():
        if uid in flagged:
            continue
        for gk, autod in ((g0k, auto0), (gFk, autoF)):
            if gk in d and uid in autod:
                hc.append(d[gk][0]); ac.append(autod[uid][0])
                hs.append(int(round(d[gk][1]))); as_.append(int(round(autod[uid][1])))
        if g0k in d:
            h0c.append(d[g0k][0]); h0s.append(d[g0k][1])
        if gFk in d:
            hFc.append(d[gFk][0]); hFs.append(d[gFk][1])

    print(f"# 人手 vs 自動（{args.label}, gen{args.gen0} vs gen{args.final}, flagged除外, n_pairs={len(hc)}）")
    print("\n## 人手 平均（flagged除外）")
    if h0c:
        print(f"- gen{args.gen0}: content={sum(h0c)/len(h0c):.3f} / style={sum(h0s)/len(h0s):.3f} (n={len(h0c)})")
    if hFc:
        print(f"- gen{args.final}: content={sum(hFc)/len(hFc):.3f} / style={sum(hFs)/len(hFs):.3f} (n={len(hFc)})")
    print("\n## 自動との一致（補助指標）")
    rho = spearman(hc, ac)
    k = qwk(hs, as_)
    print(f"- content_rate Spearman ρ = {rho:.3f}" if rho is not None else "- content_rate ρ: 計算不可")
    print(f"- style 二次重み付きκ = {k:.3f}" if k is not None else "- style κ: 計算不可")
    print("  ※評価者1名・本人・n小ゆえ補助的な目安（妥当性証明ではない）。")


if __name__ == "__main__":
    main()
