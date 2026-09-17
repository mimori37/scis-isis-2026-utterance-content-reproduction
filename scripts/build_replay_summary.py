"""study02/03 の評価結果（pairwise judge ＋ 絶対rubric）を集計して結果表用サマリを出す。

- pairwise: runs/<ts>/judges/judge_g{a}_vs_g{b}[_swap].tsv を読み、
  通常パスと SWAP パスを「勝った世代」で突き合わせ、各 test 事例を
  stable_win / stable_tie / unstable に分類して世代別に集計（content/style 別）。
- 絶対rubric: runs/<ts>/eval/rubric_gen{n}.tsv の content_rate / style の平均を世代別に。

使い方:
  CHARAGEN_STUDY=study03_baseline-replay python scripts/build_replay_summary.py --ts <batch>
  （--ts 省略時は最新バッチ）
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY = os.environ.get("CHARAGEN_STUDY", "study02_script-replay")
RUNS = ROOT / "experiments" / STUDY / "runs"
STUDY_EVAL = ROOT / "experiments" / STUDY / "eval"


def load_flagged() -> set:
    """文脈不足等でフラグした test id（主集計から分離）。"""
    p = STUDY_EVAL / "flagged_test_ids.tsv"
    out = set()
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("id\t"):
            continue
        out.add(ln.split("\t", 1)[0].strip())
    return out


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def latest_ts() -> str:
    ds = sorted(p.name for p in RUNS.iterdir()
                if p.is_dir() and re.fullmatch(r"\d{8}-\d{6}(-.+)?", p.name))
    if not ds:
        raise SystemExit(f"バッチがありません: {RUNS}")
    return ds[-1]


def parse_judge(path: Path):
    """判定 tsv を {id: {'content': gen|'tie', 'style': gen|'tie'}} に。
    先頭行 '# 列A=genX\t列B=genY' で A/B→世代を解決。"""
    lines = read(path).splitlines()
    colA = colB = None
    out = {}
    for ln in lines:
        if ln.startswith("#"):
            m = re.findall(r"列([AB])=gen(\d+)", ln)
            for col, g in m:
                if col == "A":
                    colA = int(g)
                else:
                    colB = int(g)
            continue
        if not ln.strip() or ln.startswith("id\t"):
            continue
        c = ln.split("\t")
        if len(c) < 3:
            continue
        cid = c[0].strip()

        def to_gen(w: str):
            w = w.strip().upper()
            if w == "A":
                return colA
            if w == "B":
                return colB
            return "tie"
        out[cid] = {"content": to_gen(c[1]), "style": to_gen(c[2])}
    return colA, colB, out


def classify(normal, swap):
    """通常 vs SWAP の勝った世代を突き合わせ stable_win(gen)/stable_tie/unstable。"""
    if swap is None:
        # SWAP なし: 単発判定（安定性は不明）
        return ("single", normal)
    if normal == swap:
        return ("stable", normal) if normal != "tie" else ("stable_tie", "tie")
    # 不一致（勝者世代が違う / 片方tie）
    return ("unstable", None)


def agg_pairwise(ts: str, flagged: set = frozenset()):
    jdir = RUNS / ts / "judges"
    if not jdir.exists():
        return {}
    pairs = {}
    for p in sorted(jdir.glob("judge_g*_vs_g*.tsv")):
        m = re.match(r"judge_g(\d+)_vs_g(\d+)(_swap)?\.tsv", p.name)
        if not m:
            continue
        a, b, sw = int(m.group(1)), int(m.group(2)), bool(m.group(3))
        pairs.setdefault((a, b), {})[("swap" if sw else "normal")] = parse_judge(p)
    result = {}
    for (a, b), got in pairs.items():
        _, _, nmap = got.get("normal", (None, None, {}))
        swap_part = got.get("swap")
        smap = swap_part[2] if swap_part else None
        tally = {ax: {f"gen{a}": 0, f"gen{b}": 0, "stable_tie": 0, "unstable": 0,
                      "single": {f"gen{a}": 0, f"gen{b}": 0, "tie": 0}}
                 for ax in ("content", "style")}
        for cid, axes in nmap.items():
            if cid in flagged:
                continue
            for ax in ("content", "style"):
                nv = axes[ax]
                sv = smap[cid][ax] if (smap and cid in smap) else None
                kind, gen = classify(nv, sv)
                if kind == "stable":
                    tally[ax][f"gen{gen}"] += 1
                elif kind == "stable_tie":
                    tally[ax]["stable_tie"] += 1
                elif kind == "unstable":
                    tally[ax]["unstable"] += 1
                else:  # single
                    key = "tie" if nv == "tie" else f"gen{nv}"
                    tally[ax]["single"][key] = tally[ax]["single"].get(key, 0) + 1
        n_used = sum(1 for cid in nmap if cid not in flagged)
        result[(a, b)] = {"has_swap": smap is not None, "n": n_used, "tally": tally}
    return result


def parse_rubric(tsv_text: str):
    """絶対rubric出力 (id<TAB>content_rate<TAB>style<TAB>…) を [(id, rate, style)] に。"""
    rows = []
    for ln in tsv_text.splitlines():
        if not ln.strip() or ln.startswith("id\t"):
            continue
        c = ln.split("\t")
        if len(c) < 3:
            continue
        try:
            rows.append((c[0].strip(), float(c[1]), float(c[2])))
        except ValueError:
            continue
    return rows


def agg_rubric(ts: str, flagged: set):
    """各世代の content_rate/style を macro 平均。flagged は主集計から分離し別掲。"""
    edir = RUNS / ts / "eval"
    out = {}
    if not edir.exists():
        return out
    for p in sorted(edir.glob("rubric_gen*.tsv")):
        m = re.match(r"rubric_gen(\d+)\.tsv", p.name)
        if not m:
            continue
        gen = int(m.group(1))
        rows = parse_rubric(read(p))           # [(id, rate, style)]
        kept = [(i, r, s) for (i, r, s) in rows if i not in flagged]
        flg = [(i, r, s) for (i, r, s) in rows if i in flagged]
        if kept:
            out[gen] = {
                "n": len(kept),
                "content_rate": sum(r for _, r, _ in kept) / len(kept),
                "style": sum(s for _, _, s in kept) / len(kept),
                "flagged": {i: (r, s) for i, r, s in flg},
                "n_all": len(rows),
                "content_rate_all": sum(r for _, r, _ in rows) / len(rows),
            }
    return out


def main():
    ap = argparse.ArgumentParser(description="replay 評価集計（pairwise＋絶対rubric）")
    ap.add_argument("--ts", default=None)
    args = ap.parse_args()
    ts = args.ts or latest_ts()
    flagged = load_flagged()
    print(f"# study={STUDY}  batch={ts}（flagged 除外: {sorted(flagged) or 'なし'}）\n")

    pw = agg_pairwise(ts, flagged)
    print("## pairwise（世代間・SWAP安定性込み・flagged除外）")
    if not pw:
        print("  （judges/ に判定 tsv がありません）")
    for (a, b), r in sorted(pw.items()):
        sw = "SWAP有" if r["has_swap"] else "SWAP無(単発)"
        print(f"- gen{a} vs gen{b}  (n={r['n']}, {sw})")
        for ax in ("content", "style"):
            t = r["tally"][ax]
            if r["has_swap"]:
                print(f"    {ax:7s}: gen{a}勝={t[f'gen{a}']} / gen{b}勝={t[f'gen{b}']} / "
                      f"stable_tie={t['stable_tie']} / unstable={t['unstable']}")
            else:
                s = t["single"]
                print(f"    {ax:7s}: gen{a}勝={s.get(f'gen{a}',0)} / gen{b}勝={s.get(f'gen{b}',0)} / tie={s.get('tie',0)}")

    rb = agg_rubric(ts, flagged)
    print(f"\n## 絶対rubric（モデル毎・世代別 macro平均。flagged 分離: {sorted(flagged) or 'なし'}）")
    if not rb:
        print("  （eval/rubric_gen*.tsv がありません）")
    for gen in sorted(rb):
        v = rb[gen]
        flg = " / ".join(f"{i}=content{r:.2f},style{s:.0f}" for i, (r, s) in v["flagged"].items())
        print(f"- gen{gen}: content再現率={v['content_rate']:.3f} / style={v['style']:.3f}  (n={v['n']}; "
              f"flagged含む全体={v['content_rate_all']:.3f}/n={v['n_all']})"
              + (f"  [flagged {flg}]" if flg else ""))


if __name__ == "__main__":
    main()
