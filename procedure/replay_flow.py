# 公開版。update isolation の意味へコメントを限定している。挙動は研究用と同一。
"""「原作セリフ再現」実験の手動コピペ進行スクリプト（API不使用）。

Web版 ChatGPT の一時チャットへ「貼る全文」を出力し、返ってきた出力を取り込んで成果物に
保存し、次工程へ進める進行役。工程ごとに別チャット（コンテキスト混入防止）。

世代 N（=0,1,2,…）ごとに同一の 4 工程＋test評価:
  analysis → design → gen_train → feedback → gen_test
- study02: N=0 の分析/設計プロンプトは種（common/replay_prompts/seed_*.md）。
- study03: N=0 は外部 baseline を 03_chara_prompt に直置き＝gen0 は analysis/design を
  走らせず gen_train→feedback→gen_test の3工程（init --chara で baseline モード）。
- feedback が分析/設計プロンプトを改訂し、次世代 gen{N+1}/00,02 へ引き継ぐ。
- test 生成（gen_test）はメトリクス用。その出力と評価結果を feedback/update へ戻さない（update isolation）。
  同一入力内に別 target の文脈として原作発話が現れる件は、この仕組みの対象外である。
- judge は別コマンド（世代間 pairwise）。

実験の切替: 環境変数 CHARAGEN_STUDY（既定=study02_script-replay）で runs/ の置き場所を切替。
2条件（N=0a/b）は別バッチ。init --cond で TS にラベル付与、各コマンド --ts で対象バッチ指定可。

運用:
  make replay-init                 # 新バッチ作成（gen0 に種を配置）
  make replay-next                 # 今チャットに貼る全文を _paste.txt に出力
  #   → ChatGPT 一時チャットに貼り、返答を _reply.txt に保存
  make replay-record               # _reply.txt を取り込み成果物保存＋次工程へ
  make replay-judge A=0 B=3        # 世代0 vs 世代3 の test 生成を pairwise 比較する貼付を出力
  make replay-record-judge A=0 B=3 # judge 出力を取り込み保存
  make replay-status               # 現在地
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from config import ROOT, load_config, new_timestamp

PROMPTS = ROOT / "common" / "replay_prompts"
STUDY = os.environ.get("CHARAGEN_STUDY", "study02_script-replay")
RUNS = ROOT / "experiments" / STUDY / "runs"
STUDY_EVAL = ROOT / "experiments" / STUDY / "eval"   # 絶対rubric の内容要素キー等（study共有）
COMMON_DIR = ROOT / "experiments" / STUDY            # _paste.txt / _reply.txt は study 共有（条件が変わっても同じファイル）

# gen_test は feedback の後（feedback を締めてから test 生成＝test 側の出力を update へ戻さない）。
# 同一入力内の別 target からの露出は、この順序では防げない。
STEPS = ["analysis", "design", "gen_train", "feedback", "gen_test"]
# study03: gen0 が外部 baseline 直置きのときは analysis/design を走らせない。
STEPS_GEN0_BASELINE = ["gen_train", "feedback", "gen_test"]


def steps_for(gen: int, st: dict) -> list:
    """その世代の工程列。gen0 が baseline モードなら analysis/design を飛ばす。"""
    if gen == 0 and st.get("gen0_baseline"):
        return STEPS_GEN0_BASELINE
    return STEPS


F = {
    "analysis_prompt": "00_analysis_prompt.md",
    "analysis_sheet":  "01_analysis_sheet.tsv",
    "design_prompt":   "02_design_prompt.md",
    "chara_prompt":    "03_chara_prompt.md",
    "gen_train_raw":   "04_gen_train.txt",
    "gen_train_tsv":   "04_gen_train.tsv",
    "gen_test_raw":    "t04_gen_test.txt",
    "gen_test_tsv":    "t04_gen_test.tsv",
    "diff":            "05_diff.md",
    "feedback_log":    "06_feedback_log.md",
    "next_analysis":   "07_next_analysis_prompt.md",
    "next_design":     "08_next_design_prompt.md",
    "new_rules":       "09_new_content_rules.tsv",
}

PASTE = "_paste.txt"
REPLY = "_reply.txt"


def paste_path() -> Path:
    """貼付テキストの置き場所（study 共有・条件をまたいで同一ファイル）。"""
    return COMMON_DIR / PASTE


def reply_path() -> Path:
    """ChatGPT 返答の貼り先（study 共有・条件をまたいで同一ファイル）。"""
    return COMMON_DIR / REPLY


# ---------- 汎用 ----------
def read(p: Path) -> str:
    return Path(p).read_text(encoding="utf-8")


def write(p: Path, s: str) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(s, encoding="utf-8")


def strip_comment(s: str) -> str:
    """先頭の HTML コメント（メタ情報）を1つ除去。"""
    return re.sub(r"^\s*<!--.*?-->\s*", "", s, count=1, flags=re.S)


def oneline(t: str) -> str:
    return t.replace("\t", " ").replace("\n", " ").strip()


def cell(t: str) -> str:
    """TSV セル用: タブ除去・改行は ' / ' に。"""
    return t.replace("\t", " ").replace("\n", " / ").strip()


def pbcopy(s: str) -> bool:
    try:
        subprocess.run(["pbcopy"], input=s.encode("utf-8"), check=True)
        return True
    except Exception:
        return False


# ---------- データ（発話セット） ----------
def load_sets():
    cfg = load_config()
    src = ROOT / "common" / "source" / cfg.character
    data = json.loads(read(src / "utterance_sets.json"))
    train = [u for u in data["utterance_sets"] if u["split"] == "train"]
    test = [u for u in data["utterance_sets"] if u["split"] == "test"]
    return cfg, src, data, train, test


def ctx_block(ctx) -> str:
    """生成貼付用の文脈（話者ごと1行）。"""
    return "\n".join(f"{c['speaker']}: {oneline(c['text'])}" for c in ctx)


def ctx_inline(ctx) -> str:
    """TSV1セル用の文脈。"""
    return " / ".join(f"{c['speaker']}「{oneline(c['text'])}」" for c in ctx)


def ctx_inline_anon(ctx, target: str) -> str:
    """judge 用に話者ラベルを匿名化した文脈（対象話者→TARGET、他者→他者A/B…）。
    発話の文面（正解・生成・文脈本文）は比較対象なので加工しない＝完全匿名化はしない。"""
    labels: dict[str, str] = {}
    parts = []
    for c in ctx:
        sp = c["speaker"]
        if sp == target:
            lab = "TARGET"
        elif sp == "状況":
            lab = "状況"
        else:
            if sp not in labels:
                labels[sp] = f"他者{chr(ord('A') + len(labels))}"
            lab = labels[sp]
        parts.append(f"{lab}「{oneline(c['text'])}」")
    return " / ".join(parts)


def sets_block(sets) -> str:
    return "\n".join(f"=== {u['id']} ===\n{ctx_block(u['context'])}" for u in sets)


# ---------- 出力パース ----------
_BLK_RE = re.compile(r"^===\s*(u\d+)\s*===\s*$", re.M)


def parse_blocks(text: str) -> dict[str, str]:
    """`=== uXXX ===` 区切りの生成出力を {id: 発話} に。"""
    out = {}
    matches = list(_BLK_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(1)] = text[m.end():end].strip()
    return out


_FB_MARKERS = ["===DIFF===", "===REVISED_ANALYSIS_PROMPT===",
               "===REVISED_DESIGN_PROMPT===", "===FEEDBACK_LOG===",
               "===NEW_CONTENT_RULES===", "===END==="]


def parse_feedback(text: str) -> dict[str, str]:
    idx = []
    for mk in _FB_MARKERS:
        pos = text.find(mk)
        if pos < 0:
            raise SystemExit(f"feedback 出力にマーカーが見つかりません: {mk}")
        idx.append((mk, pos))
    out = {}
    for i, (mk, pos) in enumerate(idx[:-1]):
        seg = text[pos + len(mk): idx[i + 1][1]].strip()
        out[mk] = seg
    return out


def count_status(tsv_text: str) -> dict[str, int]:
    """NEW_CONTENT_RULES の TSV を status 別に集計（飽和=NEW、精緻化継続=REFINED の確認用）。"""
    counts: dict[str, int] = {}
    for ln in tsv_text.splitlines():
        if not ln.strip():
            continue
        cols = ln.split("\t")
        if len(cols) < 2:
            continue
        st = cols[1].strip()
        if st.lower() == "status":   # ヘッダ
            continue
        counts[st.upper()] = counts.get(st.upper(), 0) + 1
    return counts


def count_new_rules(tsv_text: str) -> int:
    """status=NEW の行数（飽和判定用）。"""
    return count_status(tsv_text).get("NEW", 0)


def read_gen_tsv(p: Path) -> dict[str, str]:
    """04_gen_*.tsv (id<TAB>utterance) を {id: 発話} に。"""
    out = {}
    if not p.exists():
        return out
    for ln in read(p).splitlines():
        if not ln.strip() or ln.startswith("id\t"):
            continue
        parts = ln.split("\t", 1)
        if len(parts) == 2:
            out[parts[0].strip()] = parts[1]
    return out


def load_keys() -> dict[str, str]:
    """内容要素キー（id -> '要素1；要素2…'）を study レベル eval から読む。"""
    p = STUDY_EVAL / "content_element_keys.tsv"
    out = {}
    if not p.exists():
        return out
    for ln in read(p).splitlines():
        if not ln.strip() or ln.startswith("id\t"):
            continue
        parts = ln.split("\t", 1)
        if len(parts) == 2:
            out[parts[0].strip()] = parts[1].strip()
    return out


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


# ---------- 状態 ----------
def cur_ts(ts: str | None = None) -> str:
    if ts:
        if not (RUNS / ts).exists():
            raise SystemExit(f"指定バッチがありません: {RUNS / ts}")
        return ts
    if not RUNS.exists():
        raise SystemExit("バッチがありません。先に `make replay-init` を実行してください。")
    ds = sorted(p.name for p in RUNS.iterdir()
                if p.is_dir() and re.fullmatch(r"\d{8}-\d{6}(-.+)?", p.name))
    if not ds:
        raise SystemExit("バッチがありません。先に `make replay-init` を実行してください。")
    return ds[-1]


def load_state(ts: str) -> dict:
    return json.loads(read(RUNS / ts / "state.json"))


def save_state(ts: str, st: dict) -> None:
    write(RUNS / ts / "state.json", json.dumps(st, ensure_ascii=False, indent=2))


def gen_dir(ts: str, gen: int) -> Path:
    return RUNS / ts / f"gen{gen}"


# ---------- paste 組み立て ----------
def build_paste(ts: str, gen: int, step: str, train, test, src: Path) -> str:
    g = gen_dir(ts, gen)
    if step == "analysis":
        ap = read(g / F["analysis_prompt"])
        source = read(src / "analysis_source_train.md")
        return f"{ap}\n\n# アスカのセリフ起こし（train・ト書き除去済み）\n\n{source}"
    if step == "design":
        dp = read(g / F["design_prompt"])
        sheet = read(g / F["analysis_sheet"])
        return f"{dp}\n\n# アスカの分析（シーン単位TSV）\n\n{sheet}"
    if step in ("gen_train", "gen_test"):
        sp = read(g / F["chara_prompt"])
        instr = strip_comment(read(PROMPTS / "gen_instruction.md"))
        sets = train if step == "gen_train" else test
        return f"{sp}\n\n---\n{instr}\n\n# 場面\n{sets_block(sets)}"
    if step == "feedback":
        fb = strip_comment(read(PROMPTS / "diff_feedback.md"))
        # study03 gen0(baseline): 分析シートは未生成。03_chara_prompt は外部 baseline。
        sheet_path = g / F["analysis_sheet"]
        sheet_txt = (read(sheet_path) if sheet_path.exists()
                     else "（N=0: 分析シートなし。03_chara_prompt は前回研究の baseline）")
        assets = (
            f"## 分析プロンプト[N]\n{read(g / F['analysis_prompt'])}\n\n"
            f"## 分析シート(TSV)\n{sheet_txt}\n\n"
            f"## 設計プロンプト[N]\n{read(g / F['design_prompt'])}\n\n"
            f"## システムプロンプト\n{read(g / F['chara_prompt'])}"
        )
        gen_map = read_gen_tsv(g / F["gen_train_tsv"])
        rows = ["id\t文脈\t原作の正解\t生成発話"]
        for u in train:
            rows.append(f"{u['id']}\t{ctx_inline(u['context'])}\t{cell(u['gold'])}\t{cell(gen_map.get(u['id'], ''))}")
        table = "\n".join(rows)
        prev_log = ""
        if gen > 0:
            pl = gen_dir(ts, gen - 1) / F["feedback_log"]
            if pl.exists():
                prev_log = f"\n\n## 過去フェーズのフィードバックログ\n{read(pl)}"
        return (f"{fb}\n\n# 1世代分の資産\n{assets}\n\n"
                f"# train 発話セットの結果（TSV）\n{table}{prev_log}")
    raise SystemExit(f"不明な step: {step}")


# ---------- record（取り込み） ----------
def ingest(ts: str, gen: int, step: str, reply: str, train, test) -> str:
    g = gen_dir(ts, gen)
    if step == "analysis":
        write(g / F["analysis_sheet"], reply.strip() + "\n")
        return f"分析シート -> {F['analysis_sheet']}"
    if step == "design":
        write(g / F["chara_prompt"], reply.strip() + "\n")
        return f"システムプロンプト -> {F['chara_prompt']}"
    if step in ("gen_train", "gen_test"):
        sets = train if step == "gen_train" else test
        raw_key = "gen_train_raw" if step == "gen_train" else "gen_test_raw"
        tsv_key = "gen_train_tsv" if step == "gen_train" else "gen_test_tsv"
        write(g / F[raw_key], reply)
        parsed = parse_blocks(reply)
        rows = ["id\tutterance"]
        for u in sets:
            rows.append(f"{u['id']}\t{cell(parsed.get(u['id'], ''))}")
        write(g / F[tsv_key], "\n".join(rows) + "\n")
        missing = [u["id"] for u in sets if u["id"] not in parsed]
        matched = len(sets) - len(missing)
        msg = f"生成({step}) -> {F[raw_key]} / {F[tsv_key]}  ({matched}/{len(sets)} 件取得)"
        if missing:
            msg += f"\n  ⚠ 未取得 id: {missing}"
        return msg
    if step == "feedback":
        sec = parse_feedback(reply)
        write(g / F["diff"], sec["===DIFF==="] + "\n")
        write(g / F["next_analysis"], sec["===REVISED_ANALYSIS_PROMPT==="] + "\n")
        write(g / F["next_design"], sec["===REVISED_DESIGN_PROMPT==="] + "\n")
        write(g / F["feedback_log"], sec["===FEEDBACK_LOG==="] + "\n")
        write(g / F["new_rules"], sec["===NEW_CONTENT_RULES==="] + "\n")
        st = count_status(sec["===NEW_CONTENT_RULES==="])
        n_new, n_ref = st.get("NEW", 0), st.get("REFINED", 0)
        prev_new = None
        if gen > 0 and (gen_dir(ts, gen - 1) / F["new_rules"]).exists():
            prev_new = count_new_rules(read(gen_dir(ts, gen - 1) / F["new_rules"]))
        sat = "" if prev_new is None else (
            "  → NEW が2世代連続0=飽和停止の候補" if (n_new == 0 and prev_new == 0)
            else f"（前世代NEW={prev_new}）")
        ref = f"／REFINED={n_ref}（>0なら精緻化継続。RUN_NOTESに補足）" if n_ref else ""
        return (f"差分 -> {F['diff']} / ログ -> {F['feedback_log']} / "
                f"改訂版(次世代用) -> {F['next_analysis']},{F['next_design']} / "
                f"新規規則 -> {F['new_rules']}\n"
                f"  status=NEW: {n_new}件{ref}{sat}\n"
                f"  次は gen_test（feedback 済みなので test 出力を見ても更新には戻らない）。")
    raise SystemExit(f"不明な step: {step}")


# ---------- コマンド ----------
def cmd_init(args):
    ts = new_timestamp()
    cond = getattr(args, "cond", None)
    if cond:
        ts = f"{ts}-{cond}"
    if (RUNS / ts).exists():
        ts += "-1"
    g0 = gen_dir(ts, 0)
    g0.mkdir(parents=True, exist_ok=True)
    # 種の分析/設計プロンプトは gen0 に常に配置（baseline モードでも feedback が [N=0] として改訂する）。
    write(g0 / F["analysis_prompt"], strip_comment(read(PROMPTS / "seed_analysis.md")))
    write(g0 / F["design_prompt"], strip_comment(read(PROMPTS / "seed_design.md")))
    state = {"ts": ts, "gen": 0, "step": 0}
    chara = getattr(args, "chara", None)
    baseline_note = ""
    if chara:
        # study03: gen0 の 03_chara_prompt を外部 baseline で直置き＝analysis/design は飛ばす。
        write(g0 / F["chara_prompt"], read(Path(chara)))
        state["gen0_baseline"] = True
        state["baseline_src"] = str(chara)
        baseline_note = (f"- N=0 baseline（前回研究のキャラ付けプロンプト）: {chara}\n"
                         f"- gen0 は analysis/design を走らせず gen_train から開始（baseline モード）\n")
    save_state(ts, state)
    write(RUNS / ts / "RUN_NOTES.md",
          f"# 実行メモ（手動記録）\n\n"
          f"- study: {STUDY}\n"
          f"- バッチ: {ts}\n"
          f"{baseline_note}"
          f"- utterance_sets.json 作成日時: \n"
          f"- 除外件数/理由: 15件（基準・内訳は scripts/build_utterance_sets.py の EXCLUDE と "
          f"common/source/asuka/utterance_sets_preview.md を参照）\n"
          f"- 使用モデル（生成: ChatGPT のモデル名）: \n"
          f"- 使用モデル（judge）: \n"
          f"- 各工程の実行日時: \n"
          f"- 生成回数: 各世代・各文脈につき **1回（単一生成）**。結果は生成揺れを含む。\n"
          f"- update isolation: gen_test は feedback の後に実行。**feedback 完了まで test 出力を評価・参照していない**（要確認・記録）。\n"
          f"- 同一入力内の別 target からの露出は、この順序では防げない（camera-ready の Limitations を参照）。\n"
          f"- judge: A/B 対応は judge 実行時に秘匿。SWAP 実行の有無: \n"
          f"- judge 実施タイミング: 全世代の生成・停止が完了してからまとめて（逐次に結果を見ない）\n"
          f"- 停止理由: （飽和停止＝NEW が2世代連続0／gen4天井停止＝飽和未確認で打切り のいずれかを記入）\n"
          f"- 精緻化(REFINED)の継続: （飽和停止時に REFINED>0 が続いていたら記録）\n"
          f"- 最終世代: \n"
          f"- 備考: \n")
    _, _, data, train, test = load_sets()
    print(f"新バッチ作成: {ts}  (study={STUDY})")
    print(f"  発話セット: train={len(train)} / test={len(test)}（character={data['character']}）")
    if chara:
        print(f"  gen0 = baseline 直置き: {chara}")
        print(f"  gen0 工程: {' → '.join(STEPS_GEN0_BASELINE)}（analysis/design はスキップ）")
    else:
        print(f"  gen0 に種プロンプトを配置（00_analysis_prompt.md / 02_design_prompt.md）")
    print(f"次: make replay-next" + (f"  (TS={ts})" if cond else ""))


def cmd_status(args):
    ts = cur_ts(getattr(args, "ts", None))
    st = load_state(ts)
    gen, sidx = st["gen"], st["step"]
    S = steps_for(gen, st)
    step = S[sidx] if sidx < len(S) else "(完了)"
    print(f"バッチ: {ts}  (study={STUDY})")
    if st.get("gen0_baseline"):
        print(f"  N=0 baseline モード（src: {st.get('baseline_src', '?')}）")
    print(f"世代 N={gen}  工程: [{sidx}] {step}")
    print(f"工程列: {' → '.join(S)}")
    g = gen_dir(ts, gen)
    if g.exists():
        have = sorted(p.name for p in g.iterdir() if p.is_file())
        print(f"gen{gen} の成果物: {have}")


def cmd_next(args):
    ts = cur_ts(getattr(args, "ts", None))
    st = load_state(ts)
    gen, sidx = st["gen"], st["step"]
    S = steps_for(gen, st)
    if sidx >= len(S):
        print("この世代の工程は完了しています。次世代は record 後に自動作成済みです。status を確認してください。")
        return
    step = S[sidx]
    _, src, _, train, test = load_sets()
    paste = build_paste(ts, gen, step, train, test, src)
    pfile = paste_path()
    write(pfile, paste)
    # 返答の貼り先を空ファイルで先出し（ここに ChatGPT 出力を貼って record する）
    rfile = reply_path()
    if not rfile.exists():
        write(rfile, "")
    copied = pbcopy(paste)
    print(f"=== gen{gen} / 工程 {step} ===  (batch={ts})")
    print(f"貼付テキスト: {pfile}  ({len(paste)} 文字){'  [クリップボードにコピー済]' if copied else ''}")
    print(f"返答の貼り先（空で用意済）: {rfile}")
    print("手順:")
    print("  1) ChatGPT で【新しい一時チャット】を開く")
    print(f"  2) {PASTE} の全文（クリップボード可）を貼って送信")
    print(f"  3) 返答を {REPLY} に保存")
    print("  4) make replay-record")


def cmd_record(args):
    ts = cur_ts(getattr(args, "ts", None))
    st = load_state(ts)
    gen, sidx = st["gen"], st["step"]
    S = steps_for(gen, st)
    if sidx >= len(S):
        print("この世代は完了済みです。status を確認してください。")
        return
    step = S[sidx]
    rfile = Path(args.file) if args.file else (reply_path())
    if not rfile.exists():
        raise SystemExit(f"返答ファイルがありません: {rfile}\n  ChatGPT の出力をここに保存してから再実行してください。")
    reply = read(rfile)
    if not reply.strip():
        raise SystemExit(f"返答ファイルが空です: {rfile}")
    _, _, _, train, test = load_sets()
    msg = ingest(ts, gen, step, reply, train, test)
    # 状態前進
    if sidx == len(S) - 1:    # 最終工程(gen_test)の後 → 次世代を作成して引き継ぎ
        g = gen_dir(ts, gen)
        ng = gen_dir(ts, gen + 1)
        write(ng / F["analysis_prompt"], read(g / F["next_analysis"]))
        write(ng / F["design_prompt"], read(g / F["next_design"]))
        save_state(ts, {"ts": ts, "gen": gen + 1, "step": 0})
        nxt = f"gen{gen + 1} / analysis（前世代 feedback の改訂プロンプトを引き継ぎ）"
    else:
        # gen0_baseline 等のフラグを保持したまま step だけ前進
        st2 = dict(st)
        st2["step"] = sidx + 1
        save_state(ts, st2)
        nxt = f"gen{gen} / {S[sidx + 1]}"
    # 取り込んだ返答は _transcripts/ へ退避（二重取り込み防止＋バッチ直下を散らかさない）
    if rfile == reply_path():
        arch = RUNS / ts / "_transcripts"
        arch.mkdir(exist_ok=True)
        rfile.rename(arch / f"_reply.gen{gen}.{step}.txt")
    print(f"取り込み完了（gen{gen}/{step}）: {msg}")
    print(f"次の工程: {nxt}  →  make replay-next" + (f" TS={ts}" if getattr(args, 'ts', None) else ""))


def _judge_cols(a: int, b: int, swap: bool):
    """列A/列B に割り当てる世代。swap で入替（順序バイアス除去の2パス用）。"""
    return (b, a) if swap else (a, b)


def _judge_name(a: int, b: int, swap: bool) -> str:
    return f"judge_g{a}_vs_g{b}{'_swap' if swap else ''}"


def cmd_judge(args):
    ts = cur_ts(getattr(args, "ts", None))
    _, _, data, _, test = load_sets()
    tgt = data.get("target", "")
    a, b, swap = args.A, args.B, args.swap
    colA, colB = _judge_cols(a, b, swap)
    amap = read_gen_tsv(gen_dir(ts, colA) / F["gen_test_tsv"])
    bmap = read_gen_tsv(gen_dir(ts, colB) / F["gen_test_tsv"])
    if not amap or not bmap:
        raise SystemExit(f"gen{a} か gen{b} の test 生成（{F['gen_test_tsv']}）が見つかりません。"
                         f"両世代で gen_test まで進めてください。")
    jb = strip_comment(read(PROMPTS / "judge.md"))
    rows = ["id\t文脈\t原作の正解\t生成A\t生成B"]
    for u in test:
        rows.append(f"{u['id']}\t{ctx_inline_anon(u['context'], tgt)}\t{cell(u['gold'])}\t"
                    f"{cell(amap.get(u['id'], ''))}\t{cell(bmap.get(u['id'], ''))}")
    # 貼付テキストには世代番号を出さない（judge に新旧/優劣の先入観を与えない）
    paste = f"{jb}\n\n# 評価対象\n" + "\n".join(rows)
    pfile = paste_path()
    write(pfile, paste)
    rfile = reply_path()    # 返答の貼り先を空で用意
    if not rfile.exists():
        write(rfile, "")
    copied = pbcopy(paste)
    print(f"=== judge（test {len(test)}件） ===  (batch={ts})")
    print(f"  内部対応（貼付には含めない）: 列A=gen{colA} / 列B=gen{colB}{'  [swap]' if swap else ''}")
    print(f"貼付テキスト: {pfile}{'  [クリップボードにコピー済]' if copied else ''}")
    print(f"返答を {reply_path()} に保存 → "
          f"make replay-record-judge A={a} B={b}{' SWAP=1' if swap else ''}")


def cmd_record_judge(args):
    ts = cur_ts(getattr(args, "ts", None))
    a, b, swap = args.A, args.B, args.swap
    colA, colB = _judge_cols(a, b, swap)
    rfile = Path(args.file) if args.file else (reply_path())
    if not rfile.exists():
        raise SystemExit(f"返答ファイルがありません: {rfile}")
    body = read(rfile).strip()
    if not body or "\t" not in body:
        raise SystemExit(f"返答が空か TSV ではありません: {rfile}\n  judge 出力（id<TAB>... の行）を貼って保存し直してください。")
    out = RUNS / ts / "judges" / f"{_judge_name(a, b, swap)}.tsv"   # judges/ にまとめる
    header = f"# 列A=gen{colA}\t列B=gen{colB}\n"   # judge 出力の A/B がどの世代かの対応
    write(out, header + body + "\n")               # write() が judges/ を自動作成
    if rfile == reply_path():
        arch = RUNS / ts / "_transcripts"
        arch.mkdir(exist_ok=True)
        rfile.rename(arch / f"_reply.{_judge_name(a, b, swap)}.txt")
    print(f"judge 結果を保存: {out}  （列A=gen{colA} / 列B=gen{colB}）")


def cmd_rubric(args):
    """絶対rubric: --keys で内容要素キー列挙、--gen N で gen N の test 生成を採点（モデル毎の単体評価）。"""
    ts = cur_ts(getattr(args, "ts", None))
    _, _, data, _, test = load_sets()
    tgt = data.get("target", "")
    if args.keys:
        prompt = strip_comment(read(PROMPTS / "rubric_keys.md"))
        rows = ["id\t文脈\t原作の正解"]
        for u in test:
            rows.append(f"{u['id']}\t{ctx_inline_anon(u['context'], tgt)}\t{cell(u['gold'])}")
        paste = f"{prompt}\n\n# 対象（test {len(test)}件）\n" + "\n".join(rows)
        tail = "make replay3-record-rubric KEYS=1" + (f" TS={ts}" if getattr(args, "ts", None) else "")
        label = "内容要素キーの列挙（gold から・採点の固定キー）"
    else:
        gen = args.gen
        if gen is None:
            raise SystemExit("--gen <N> か --keys のいずれかを指定してください。")
        keys = load_keys()
        if not keys:
            raise SystemExit(f"内容要素キーがありません: {STUDY_EVAL / 'content_element_keys.tsv'}\n"
                             f"  先に `make replay3-rubric KEYS=1` → 人手確認 で作成してください。")
        gmap = read_gen_tsv(gen_dir(ts, gen) / F["gen_test_tsv"])
        if not gmap:
            raise SystemExit(f"gen{gen} の test 生成（{F['gen_test_tsv']}）が見つかりません。")
        prompt = strip_comment(read(PROMPTS / "rubric_abs.md"))
        rows = ["id\t文脈\t原作の正解\t内容要素キー\t生成発話"]
        for u in test:
            rows.append(f"{u['id']}\t{ctx_inline_anon(u['context'], tgt)}\t{cell(u['gold'])}\t"
                        f"{keys.get(u['id'], '')}\t{cell(gmap.get(u['id'], ''))}")
        paste = f"{prompt}\n\n# 評価対象（test {len(test)}件）\n" + "\n".join(rows)
        tail = f"make replay3-record-rubric GEN={gen}" + (f" TS={ts}" if getattr(args, "ts", None) else "")
        label = f"gen{gen} の絶対rubric採点"
    pfile = paste_path()
    write(pfile, paste)
    rfile = reply_path()
    if not rfile.exists():
        write(rfile, "")
    copied = pbcopy(paste)
    print(f"=== rubric: {label} ===  (batch={ts})")
    print(f"貼付テキスト: {pfile}{'  [クリップボードにコピー済]' if copied else ''}")
    print(f"返答を {reply_path()} に保存 → {tail}")


def cmd_record_rubric(args):
    ts = cur_ts(getattr(args, "ts", None))
    rfile = Path(args.file) if args.file else (reply_path())
    if not rfile.exists():
        raise SystemExit(f"返答ファイルがありません: {rfile}")
    body = read(rfile).strip()
    if not body or "\t" not in body:
        raise SystemExit(f"返答が空か TSV ではありません: {rfile}")
    if args.keys:
        out = STUDY_EVAL / "content_element_keys.tsv"
        write(out, body + "\n")
        n = len([1 for ln in body.splitlines() if ln.strip() and not ln.startswith("id\t")])
        print(f"内容要素キーを保存: {out}  ({n}件)")
        print("  ← 人手で内容を確認・修正してから rubric 採点（--gen）に進む（gold接地の妥当性チェック）")
        tag = "rubric_keys"
    else:
        gen = args.gen
        if gen is None:
            raise SystemExit("--gen <N> を指定してください。")
        out = RUNS / ts / "eval" / f"rubric_gen{gen}.tsv"
        write(out, body + "\n")
        sc = parse_rubric(body)
        if sc:
            mc = sum(r[1] for r in sc) / len(sc)
            ms = sum(r[2] for r in sc) / len(sc)
            print(f"gen{gen} 絶対rubric -> {out}  ({len(sc)}件)")
            print(f"  平均 content再現率={mc:.2f} / style={ms:.2f}")
        else:
            print(f"gen{gen} 絶対rubric -> {out}（数値行をパースできず。TSV列を確認）")
        tag = f"rubric_gen{gen}"
    if rfile == reply_path():
        arch = RUNS / ts / "_transcripts"
        arch.mkdir(exist_ok=True)
        rfile.rename(arch / f"_reply.{tag}.txt")


def main():
    ap = argparse.ArgumentParser(description="原作セリフ再現 進行スクリプト（study02/03）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("--chara", default=None, help="study03: gen0 baseline の 03_chara_prompt パス")
    p_init.add_argument("--cond", default=None, help="条件ラベル（TS に付与。例 condA）")
    p_init.set_defaults(func=cmd_init)
    for name, fn in (("status", cmd_status), ("next", cmd_next)):
        p = sub.add_parser(name)
        p.add_argument("--ts", default=None, help="対象バッチ（省略時は最新）")
        p.set_defaults(func=fn)
    p_rec = sub.add_parser("record")
    p_rec.add_argument("--file", default=None)
    p_rec.add_argument("--ts", default=None, help="対象バッチ（省略時は最新）")
    p_rec.set_defaults(func=cmd_record)
    for name, fn in (("judge", cmd_judge), ("record-judge", cmd_record_judge)):
        p = sub.add_parser(name)
        p.add_argument("--A", type=int, required=True)
        p.add_argument("--B", type=int, required=True)
        p.add_argument("--swap", action="store_true")
        p.add_argument("--file", default=None)
        p.add_argument("--ts", default=None, help="対象バッチ（省略時は最新）")
        p.set_defaults(func=fn)
    p_rub = sub.add_parser("rubric")
    p_rub.add_argument("--ts", default=None)
    p_rub.add_argument("--gen", type=int, default=None)
    p_rub.add_argument("--keys", action="store_true")
    p_rub.set_defaults(func=cmd_rubric)
    p_rrub = sub.add_parser("record-rubric")
    p_rrub.add_argument("--ts", default=None)
    p_rrub.add_argument("--gen", type=int, default=None)
    p_rrub.add_argument("--keys", action="store_true")
    p_rrub.add_argument("--file", default=None)
    p_rrub.set_defaults(func=cmd_record_rubric)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
