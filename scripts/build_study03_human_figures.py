"""study03：自動(絶対rubric) vs 人手audit の比較図（pivotストーリー用）。

  fig_auto_vs_human_content.png … 内容再現率を auto と人手で並べた棒（condA/condB×gen0/最終）
                                   ＝「auto は高め・横ばい／人手は低く・上昇」の乖離を可視化
  fig_auto_vs_human_scatter.png … 事例ごとの auto vs 人手（Spearman ρ 付き）

集計は scripts/eval_human_vs_auto.py の関数を再利用（un-blind・flagged除外・ρを一致）。
出力: experiments/study03_baseline-replay/figures/
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

os.environ.setdefault("CHARAGEN_STUDY", "study03_baseline-replay")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import eval_human_vs_auto as H  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.font_manager as fm  # noqa: E402

OUT = ROOT / "experiments" / "study03_baseline-replay" / "figures"
COND = {
    "condA": {"ts": "20260624-035200-condA", "final": 3, "color": "#1f77b4"},
    "condB": {"ts": "20260624-113018-condB", "final": 4, "color": "#d62728"},
}

# --- 日本語フォント自動検出（無ければ英語） ---
jp_font = next((f.name for f in fm.fontManager.ttflist
                if any(k in f.name for k in ("Hiragino", "YuGothic", "Noto Sans CJK",
                                             "Noto Sans JP", "Meiryo", "IPAGothic"))), None)
JP = jp_font is not None
if JP:
    plt.rcParams["font.family"] = jp_font
plt.rcParams["axes.unicode_minus"] = False
print(f"日本語フォント: {jp_font if JP else '英語ラベル'}")


def L(ja, en):
    return ja if JP else en


flagged = H.load_flagged()
C_AUTO = "#9467bd"   # 自動
C_HUM = "#8c564b"    # 人手


def restore_human(label):
    hdir = H.EVAL / "human" / label
    ans = H.read_rows(hdir / "answer.tsv")
    mp = H.read_rows(hdir / "_mapping.tsv")
    hum = {}
    for uid, c in ans.items():
        if uid not in mp:
            continue
        Agen, Bgen = mp[uid][1], mp[uid][2]
        Ac, Bc = H.frac(c[1]), H.frac(c[3])
        d = {}
        if Ac is not None:
            d[Agen] = Ac
        if Bc is not None:
            d[Bgen] = Bc
        hum[uid] = d
    return hum


def stats(label):
    cfg = COND[label]
    ts, final = cfg["ts"], cfg["final"]
    g0, gF = "gen0", f"gen{final}"
    auto0, autoF = H.auto_rubric(ts, 0), H.auto_rubric(ts, final)
    hum = restore_human(label)

    def amean(d):  # auto content mean, flagged除外
        v = [c for i, (c, _) in d.items() if i not in flagged]
        return sum(v) / len(v), len(v)

    def hmean(gk):
        v = [hum[u][gk] for u in hum if u not in flagged and gk in hum[u]]
        return sum(v) / len(v), len(v)

    a0, n = amean(auto0); aF, _ = amean(autoF)
    h0, _ = hmean(g0); hF, _ = hmean(gF)
    # scatter pairs（gen0+最終プール・flagged除外）
    ac, hc = [], []
    for u in hum:
        if u in flagged:
            continue
        for gk, ad in ((g0, auto0), (gF, autoF)):
            if gk in hum[u] and u in ad:
                ac.append(ad[u][0]); hc.append(hum[u][gk])
    rho = H.spearman(hc, ac)
    return {"final": final, "n": n, "auto": (a0, aF), "hum": (h0, hF),
            "ac": ac, "hc": hc, "rho": rho}


S = {c: stats(c) for c in COND}
for c in S:
    print(f"{c}: auto gen0/最終={S[c]['auto'][0]:.3f}/{S[c]['auto'][1]:.3f}  "
          f"人手={S[c]['hum'][0]:.3f}/{S[c]['hum'][1]:.3f}  ρ={S[c]['rho']:.3f} (n={S[c]['n']})")

OUT.mkdir(parents=True, exist_ok=True)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  出力: figures/{name}")


# ===== ① 自動 vs 人手 内容再現率（棒・pivot図） =====
fig, ax = plt.subplots(figsize=(7, 4.2))
cats, autov, humv = [], [], []
for c in COND:
    cats.append(f"{c}\ngen0"); autov.append(S[c]["auto"][0]); humv.append(S[c]["hum"][0])
    cats.append(f"{c}\ngen{S[c]['final']}"); autov.append(S[c]["auto"][1]); humv.append(S[c]["hum"][1])
x = range(len(cats)); w = 0.38
ba = ax.bar([i - w / 2 for i in x], autov, w, color=C_AUTO, label=L("自動（絶対rubric）", "auto (abs-rubric)"))
bh = ax.bar([i + w / 2 for i in x], humv, w, color=C_HUM, label=L("人手audit", "human audit"))
ax.bar_label(ba, fmt="%.2f", fontsize=8); ax.bar_label(bh, fmt="%.2f", fontsize=8)
ax.set_xticks(list(x)); ax.set_xticklabels(cats)
ax.set_ylabel(L("内容要素 再現率", "content reproduction rate"))
ax.set_ylim(0, 1)
ax.set_title(L("内容再現率：自動(絶対rubric) vs 人手audit", "content rate: auto vs human"))
ax.grid(True, axis="y", alpha=0.3)
ax.legend()
ax.text(0.99, 0.97, L("n=11（u017分離）／自動は高め・横ばい、人手は低く上昇＝乖離",
                      "n=11; auto high&flat vs human low&rising = divergence"),
        transform=ax.transAxes, ha="right", va="top", fontsize=7, color="#555")
save(fig, "auto_vs_human_content.png")

# ===== ② 散布図（auto vs 人手・ρ付き） =====
fig, ax = plt.subplots(figsize=(5.2, 5))
ax.plot([0, 1], [0, 1], ls="--", color="#aaa", lw=1, label="y=x")
for c in COND:
    ax.scatter(S[c]["ac"], S[c]["hc"], color=COND[c]["color"], alpha=0.75,
               label=f"{c} (ρ={S[c]['rho']:.2f})")
ax.set_xlabel(L("自動 内容再現率", "auto content rate"))
ax.set_ylabel(L("人手 内容再現率", "human content rate"))
ax.set_xlim(-0.05, 1.05); ax.set_ylim(-0.05, 1.05)
ax.set_title(L("事例ごとの 自動 vs 人手（content）", "per-item auto vs human"))
ax.legend(fontsize=8)
ax.text(0.99, 0.02, L("点が y=x から外れる＝自動と人手の不一致（ρ弱い）",
                      "off-diagonal = weak agreement"),
        transform=ax.transAxes, ha="right", va="bottom", fontsize=7, color="#555")
save(fig, "auto_vs_human_scatter.png")

print("\n完了。auto_vs_human_content.png / auto_vs_human_scatter.png")
