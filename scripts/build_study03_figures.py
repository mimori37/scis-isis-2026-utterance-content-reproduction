"""study03 のスコア図を生成（スライド5/6・単体用）。

3種 × content/style:
  単体    … 絶対rubric の世代別スコア推移（content_rate / style）condA・condB
  隣接    … 隣接世代の pairwise（新世代勝/旧世代勝/tie/unstable）condA・condB
  0vs最終 … gen0 vs 最終世代の pairwise（最終勝/gen0勝/tie/unstable）condA・condB

集計は scripts/build_replay_summary.py の関数を再利用（SWAP安定性の判定を一致させる）。
出力: experiments/study03_baseline-replay/figures/*.png
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

os.environ.setdefault("CHARAGEN_STUDY", "study03_baseline-replay")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_replay_summary as B  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.font_manager as fm  # noqa: E402

OUT = ROOT / "experiments" / "study03_baseline-replay" / "figures"
COND = {
    "condA": {"ts": "20260624-035200-condA", "final": 3, "color": "#1f77b4"},
    "condB": {"ts": "20260624-113018-condB", "final": 4, "color": "#d62728"},
}

# ---- 日本語フォント自動検出（無ければ英語ラベル） ----
JP_KEYS = ("Hiragino", "YuGothic", "Yu Gothic", "Noto Sans CJK", "Noto Sans JP",
           "IPAGothic", "Meiryo", "MS Gothic", "TakaoGothic")
jp_font = None
for f in fm.fontManager.ttflist:
    if any(k in f.name for k in JP_KEYS):
        jp_font = f.name
        break
if jp_font is None:  # mac の .ttc を明示登録して再探索
    for cand in ["/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                 "/System/Library/Fonts/Hiragino Sans GB.ttc",
                 "/Library/Fonts/Arial Unicode.ttf"]:
        if Path(cand).exists():
            try:
                fm.fontManager.addfont(cand)
                jp_font = fm.FontProperties(fname=cand).get_name()
                break
            except Exception:
                pass
JP = jp_font is not None
if JP:
    plt.rcParams["font.family"] = jp_font
plt.rcParams["axes.unicode_minus"] = False
print(f"日本語フォント: {jp_font if JP else '見つからず→英語ラベル'}")


def L(ja: str, en: str) -> str:
    return ja if JP else en


flagged = B.load_flagged()

# pairwise / rubric を両条件分集計
PW = {c: B.agg_pairwise(COND[c]["ts"], flagged) for c in COND}
RB = {c: B.agg_rubric(COND[c]["ts"], flagged) for c in COND}

# 色（勝敗の意味で固定）
C_NEW = "#2ca02c"   # 新しい世代/最終 の勝ち
C_OLD = "#7f7f7f"   # 古い世代/gen0 の勝ち
C_TIE = "#c7c7c7"   # tie
C_UNS = "#ff7f0e"   # unstable

NOTE = L("n=11（u017は文脈不足で分離）", "n=11 (u017 excluded)")


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    fig.tight_layout()
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  出力: figures/{name}")


# ============ ① 単体（絶対rubric 世代別スコア推移） ============
def fig_solo(axis, ylim, title, fname):
    fig, ax = plt.subplots(figsize=(6, 4))
    for c, cfg in COND.items():
        gens = sorted(RB[c])
        ys = [RB[c][g]["content_rate" if axis == "content" else "style"] for g in gens]
        ax.plot(gens, ys, marker="o", color=cfg["color"], label=c)
        for g, y in zip(gens, ys):
            ax.annotate(f"{y:.2f}" if axis == "content" else f"{y:.2f}",
                        (g, y), textcoords="offset points", xytext=(0, 6),
                        ha="center", fontsize=8, color=cfg["color"])
    ax.set_xlabel(L("世代", "generation"))
    ax.set_ylabel(L("内容要素 再現率" if axis == "content" else "style (0–2)",
                    "content reproduction rate" if axis == "content" else "style (0-2)"))
    ax.set_ylim(*ylim)
    ax.set_xticks(range(0, 5))
    ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    ax.text(0.99, 0.02, NOTE, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=7, color="#555")
    save(fig, fname)


fig_solo("content", (0, 1),
         L("単体：絶対rubric 内容要素 再現率（世代別）", "Solo: absolute-rubric content rate"),
         "solo_content.png")
fig_solo("style", (0, 2),
         L("単体：絶対rubric style（世代別）", "Solo: absolute-rubric style"),
         "solo_style.png")


# ============ ② 隣接世代 pairwise ============
def fig_adjacent(cond, axis, fname):
    cfg = COND[cond]
    pairs = [(a, a + 1) for a in range(cfg["final"])]
    labels, newer, older, tie, uns = [], [], [], [], []
    for (a, b) in pairs:
        t = PW[cond].get((a, b), {}).get("tally", {}).get(axis)
        if t is None:
            continue
        labels.append(f"g{a}→g{b}")
        newer.append(t[f"gen{b}"]); older.append(t[f"gen{a}"])
        tie.append(t["stable_tie"]); uns.append(t["unstable"])
    fig, ax = plt.subplots(figsize=(6, 4))
    x = range(len(labels))
    b1 = ax.bar(x, newer, color=C_NEW, label=L("新世代 勝", "newer-gen win"))
    b2 = ax.bar(x, older, bottom=newer, color=C_OLD, label=L("旧世代 勝", "older-gen win"))
    bot2 = [n + o for n, o in zip(newer, older)]
    b3 = ax.bar(x, tie, bottom=bot2, color=C_TIE, label="tie")
    bot3 = [b + t for b, t in zip(bot2, tie)]
    b4 = ax.bar(x, uns, bottom=bot3, color=C_UNS, label="unstable")
    ax.set_xticks(list(x)); ax.set_xticklabels(labels)
    ax.set_ylabel(L("事例数", "count"))
    ax.set_title(L(f"隣接世代 pairwise（{cond}・{axis}）",
                   f"Adjacent pairwise ({cond}, {axis})"))
    ax.legend(fontsize=8, ncol=2)
    ax.text(0.99, 0.98, NOTE, transform=ax.transAxes, ha="right", va="top",
            fontsize=7, color="#555")
    save(fig, fname)


for c in COND:
    for ax_ in ("content", "style"):
        fig_adjacent(c, ax_, f"adjacent_{c}_{ax_}.png")


# ============ ③ gen0 vs 最終世代 pairwise ============
def fig_gen0_final(axis, fname):
    conds = list(COND)
    finalwin, gen0win, tie, uns, labels = [], [], [], [], []
    for c in conds:
        b = COND[c]["final"]
        t = PW[c].get((0, b), {}).get("tally", {}).get(axis)
        labels.append(f"{c}\n(g0 vs g{b})")
        if t is None:
            finalwin.append(0); gen0win.append(0); tie.append(0); uns.append(0); continue
        finalwin.append(t[f"gen{b}"]); gen0win.append(t["gen0"])
        tie.append(t["stable_tie"]); uns.append(t["unstable"])
    fig, ax = plt.subplots(figsize=(5.5, 4))
    x = range(len(conds))
    ax.bar(x, finalwin, color=C_NEW, label=L("最終世代 勝", "final-gen win"))
    bot1 = finalwin
    ax.bar(x, gen0win, bottom=bot1, color=C_OLD, label=L("gen0 勝", "gen0 win"))
    bot2 = [a + b for a, b in zip(bot1, gen0win)]
    ax.bar(x, tie, bottom=bot2, color=C_TIE, label="tie")
    bot3 = [a + b for a, b in zip(bot2, tie)]
    ax.bar(x, uns, bottom=bot3, color=C_UNS, label="unstable")
    for i, (fw, g0) in enumerate(zip(finalwin, gen0win)):
        ax.annotate(f"{fw}", (i, fw / 2), ha="center", va="center", fontsize=9, color="white")
        ax.annotate(f"{g0}", (i, fw + g0 / 2), ha="center", va="center", fontsize=9, color="white")
    ax.set_xticks(list(x)); ax.set_xticklabels(labels)
    ax.set_ylabel(L("事例数", "count"))
    ax.set_title(L(f"gen0 vs 最終世代 pairwise（{axis}）",
                   f"gen0 vs final pairwise ({axis})"))
    ax.legend(fontsize=8, ncol=2)
    ax.text(0.99, 0.98, NOTE, transform=ax.transAxes, ha="right", va="top",
            fontsize=7, color="#555")
    save(fig, fname)


fig_gen0_final("content", "gen0_vs_final_content.png")
fig_gen0_final("style", "gen0_vs_final_style.png")

print("\n完了。figures/ に 単体2・隣接4・0vs最終2 = 計8枚。")
