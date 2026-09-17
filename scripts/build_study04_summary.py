"""study04（文脈充足度）集計スクリプト。

入力: experiments/study04_context-sufficiency/labeling/02_label.tsv
      （taichi が STEP2→STEP3 で記入。Claude はラベル内容に関与しない＝集計のみ）

出力（stdout ＋ analysis/summary.md）:
  1. 規定度分布（規定度0-3 のキー数。STEP3.5 分布ゲート判定の材料）
  2. 規定度別の再現率・欠落率（A_gen0/A_final/B_gen0/B_final、○1/△0.5/×0）
  3. 不足タイプ別傾向（低規定度キーがどの不足タイプに集中し、どれが欠落に効くか）
  4. u017 含む/除く 感度（規定度別再現率と Spearman を両方で）
  5. pilot 候補一覧（手動フラグ＋設計基準による自動サジェスト）

主張レベル：診断（「文脈不足が一因の可能性」まで）。強い統計・因果は出さない。
Spearman は n=21 ゆえ「補助」。scipy 非依存（順位相関を手実装、同順位は平均順位）。
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S4 = ROOT / "experiments" / "study04_context-sufficiency"
LABEL = S4 / "labeling" / "02_label.tsv"
OUTDIR = S4 / "analysis"

GEN_COLS = ["A_gen0", "A_final", "B_gen0", "B_final"]
DEGREES = [3, 2, 1, 0]  # 明示/推定可能/外部文脈依存/不可視


def parse_score(s: str):
    """○/△/× または 1/0.5/0 を [0,1] に。空/不明は None（未記入＝集計から除外）。"""
    t = (s or "").strip()
    if not t:
        return None
    if t in ("○", "◯", "〇", "o", "O", "1", "1.0"):
        return 1.0
    if t in ("△", "0.5", ".5"):
        return 0.5
    if t in ("×", "x", "X", "0", "0.0"):
        return 0.0
    try:
        v = float(t)
        if 0.0 <= v <= 1.0:
            return v
    except ValueError:
        pass
    return None  # 想定外表記は未記入扱い（notes で警告）


def parse_degree(s: str):
    t = (s or "").strip()
    if not t:
        return None
    for ch in t:
        if ch in "0123":
            return int(ch)
    return None


def load_rows():
    if not LABEL.exists():
        sys.exit(f"未検出: {LABEL}")
    lines = LABEL.read_text(encoding="utf-8").splitlines()
    if not lines:
        sys.exit(f"空ファイル: {LABEL}")
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}

    def col(parts, key, default=""):
        # ヘッダ名の前方一致で許容（"規定度0-3" / "auto参考(...)" など）
        for name, i in idx.items():
            if name.startswith(key):
                return parts[i] if i < len(parts) else default
        return default

    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        p = ln.split("\t")
        rows.append({
            "id": col(p, "id"),
            "key_id": col(p, "key_id"),
            "key_text": col(p, "key_text"),
            "degree": parse_degree(col(p, "規定度")),
            "deficit_type": col(p, "不足タイプ").strip(),
            "support_reason": col(p, "support_reason"),
            "scores": {g: parse_score(col(p, g)) for g in GEN_COLS},
            "pilot_flag": col(p, "pilot候補").strip(),
            "notes": col(p, "notes"),
        })
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(v, nd=3):
    return "—" if v is None else f"{v:.{nd}f}"


def spearman(pairs):
    """[(x, y)] の Spearman ρ。同順位は平均順位。n<3 や分散0は None。"""
    pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None, n

    def ranks(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        r = [0.0] * len(vals)
        i = 0
        while i < len(vals):
            j = i
            while j + 1 < len(vals) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0  # 1始まり平均順位
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    rx, ry = ranks(xs), ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    dy = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    if dx == 0 or dy == 0:
        return None, n
    return num / (dx * dy), n


def section_distribution(rows):
    out = ["## 1. 規定度分布（STEP3.5 ゲート材料）", ""]
    labeled = [r for r in rows if r["degree"] is not None]
    out.append(f"- 記入済みキー: {len(labeled)} / 全 {len(rows)}")
    dist = {d: sum(1 for r in labeled if r["degree"] == d) for d in DEGREES}
    names = {3: "明示", 2: "推定可能", 1: "外部文脈依存", 0: "不可視"}
    for d in DEGREES:
        out.append(f"  - 規定度{d}（{names[d]}）: {dist[d]}")
    low = dist[0] + dist[1]
    out += ["",
            f"- 低規定度(0/1)合計: {low}",
            "- **ゲート判定**: 規定度0/1が複数あり欠落/部分が多い→文脈不足仮説を比較分析(STEP5)。"
            "0/1がほとんど無い→不足タイプ/生成側中心の質的記述＋pilot。"]
    return out, dist


def section_by_degree(rows):
    out = ["", "## 2. 規定度別の再現率・欠落率", "",
           "再現率=平均スコア(○1/△0.5/×0)、欠落率=×(=0)の割合。", "",
           "| 規定度 | n | " + " | ".join(GEN_COLS) + " | 欠落率(final平均) |",
           "|---|---|" + "---|" * len(GEN_COLS) + "---|"]
    for d in DEGREES:
        grp = [r for r in rows if r["degree"] == d]
        if not grp:
            continue
        cells = [fmt(mean([r["scores"][g] for r in grp])) for g in GEN_COLS]
        finals = [r["scores"][g] for r in grp for g in ("A_final", "B_final")]
        finals = [x for x in finals if x is not None]
        miss = fmt(sum(1 for x in finals if x == 0.0) / len(finals)) if finals else "—"
        out.append(f"| {d} | {len(grp)} | " + " | ".join(cells) + f" | {miss} |")
    out += ["", "gen0→final 差分(規定度別・条件平均):"]
    for d in DEGREES:
        grp = [r for r in rows if r["degree"] == d]
        if not grp:
            continue
        g0 = mean([r["scores"][g] for r in grp for g in ("A_gen0", "B_gen0")])
        gf = mean([r["scores"][g] for r in grp for g in ("A_final", "B_final")])
        delta = (gf - g0) if (g0 is not None and gf is not None) else None
        out.append(f"  - 規定度{d}: gen0 {fmt(g0)} → final {fmt(gf)} (Δ {fmt(delta)})")
    return out


def section_by_deficit(rows):
    out = ["", "## 3. 不足タイプ別傾向（低規定度キー中心）", "",
           "低規定度(0/1)キーがどのタイプに集中し、どれが欠落に効くか＝pilot/次段の根拠。", ""]
    low = [r for r in rows if r["degree"] in (0, 1)]
    if not low:
        out.append("（低規定度キー未検出 or 未記入）")
        return out
    types = sorted({r["deficit_type"] for r in low if r["deficit_type"]})
    if not types:
        out.append("（不足タイプ未記入）")
        return out
    out += ["| 不足タイプ | n(低規定度) | final再現率 | 欠落率(final) |", "|---|---|---|---|"]
    for t in types:
        grp = [r for r in low if r["deficit_type"] == t]
        finals = [r["scores"][g] for r in grp for g in ("A_final", "B_final")]
        finals = [x for x in finals if x is not None]
        rate = fmt(mean(finals)) if finals else "—"
        miss = fmt(sum(1 for x in finals if x == 0.0) / len(finals)) if finals else "—"
        out.append(f"| {t} | {len(grp)} | {rate} | {miss} |")
    return out


def section_u017(rows):
    out = ["", "## 4. u017 含む/除く 感度", "",
           "u017=文脈不足で評価不能の強い事例。引っ張りすぎない＝補助分析。", ""]

    def degree_rate_table(rs, label):
        lines = [f"### {label}", "", "| 規定度 | n | final再現率 |", "|---|---|---|"]
        for d in DEGREES:
            grp = [r for r in rs if r["degree"] == d]
            if not grp:
                continue
            finals = mean([r["scores"][g] for r in grp for g in ("A_final", "B_final")])
            lines.append(f"| {d} | {len(grp)} | {fmt(finals)} |")
        # Spearman（規定度 × final再現率, key単位の平均）補助
        pairs = []
        for r in rs:
            if r["degree"] is None:
                continue
            fr = mean([r["scores"]["A_final"], r["scores"]["B_final"]])
            pairs.append((r["degree"], fr))
        rho, n = spearman(pairs)
        lines += ["", f"- Spearman ρ(規定度 × final再現率) = {fmt(rho, 2)} (n={n}) ＝補助・n小ゆえ参考"]
        return lines

    out += degree_rate_table(rows, "含む（全 key）")
    out += [""]
    out += degree_rate_table([r for r in rows if r["id"] != "u017"], "除く（u017 を外す）")
    return out


def section_pilot(rows):
    out = ["", "## 5. pilot 候補一覧", "",
           "基準: 規定度0/1 & gen0・final で当該keyが欠落/部分(≤0.5) & 不足タイプが重複しすぎない、代表5件。", ""]
    manual = [r for r in rows if r["pilot_flag"]]
    if manual:
        out += ["### 手動フラグ(pilot候補列)", ""]
        for r in manual:
            out.append(f"- {r['key_id']} [{r['pilot_flag']}] {r['key_text']}")
        out.append("")

    def low_repro(r):
        vals = [r["scores"][g] for g in GEN_COLS if r["scores"][g] is not None]
        return vals and all(v <= 0.5 for v in vals)

    auto = [r for r in rows if r["degree"] in (0, 1) and low_repro(r)]
    out += ["### 自動サジェスト（基準充足・要 taichi 確認）", ""]
    if not auto:
        out.append("（該当なし or 未記入）")
    else:
        seen_types = {}
        for r in auto:
            seen_types.setdefault(r["deficit_type"], []).append(r)
        for r in auto:
            dup = "（不足タイプ重複）" if len(seen_types.get(r["deficit_type"], [])) > 1 else ""
            out.append(f"- {r['key_id']} 規定度{r['degree']} 型[{r['deficit_type'] or '—'}] "
                       f"{r['key_text']} {dup}")
        out += ["", f"※ {len(auto)}件中から不足タイプを散らして代表5件を taichi が最終選定。"]
    return out


def main():
    rows = load_rows()
    lines = ["# study04 集計（文脈充足度診断）", "",
             f"対象: test {len(set(r['id'] for r in rows))}事例 / content key {len(rows)}件",
             "主張レベル: 診断（文脈不足が低到達度の一因の**可能性**まで）。強い統計/因果は出さない。", ""]
    labeled = sum(1 for r in rows if r["degree"] is not None)
    if labeled == 0:
        lines += ["> ⚠ 02_label.tsv が未記入です。taichi の STEP2→STEP3 記入後に再実行してください。",
                  "> （スクリプトは記入済みキーのみ集計し、空欄は除外します）", ""]
    d_sec, _ = section_distribution(rows)
    lines += d_sec
    lines += section_by_degree(rows)
    lines += section_by_deficit(rows)
    lines += section_u017(rows)
    lines += section_pilot(rows)

    # 表記ゆれ警告
    warns = []
    for r in rows:
        if r["degree"] is None and any(r["scores"][g] is not None for g in GEN_COLS):
            warns.append(f"{r['key_id']}: 再現は記入だが規定度が空")
    if warns:
        lines += ["", "## 注意（要確認）", ""] + [f"- {w}" for w in warns]

    report = "\n".join(lines) + "\n"
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "summary.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"[書き出し] {OUTDIR / 'summary.md'}")


if __name__ == "__main__":
    main()
