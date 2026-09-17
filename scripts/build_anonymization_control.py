#!/usr/bin/env python3
"""査読 R2-3 への統制。固有名を伏せたキャラ付けプロンドで生成し直し、想起の寄与を測る。

統制の対象はキャラ付けプロンプトと生成指示だけである。場面の文脈は触らない。
理由は PUB-002 の材料 §8 にある。文脈は原作の文字起こしなので、仮名化すると
ある対象発話の原作発話に含まれる人物名が消え、逐語一致が
機械的に落ちる。想起が消えたからではないので、近逐語を説明する統制がその事例で壊れる。

判断カテゴリの語は残す。えこひいき、七光り、命令権拒否、世界で唯一の居場所、人形、
日本人のはっきりしなさ。これらは固有名ではなく手法が作った判断軸なので、
消すと手法そのものを変えてしまう。

測るものは2つ。
  overlap  原作発話との逐語一致。近逐語が固有名の露出に依存していたかを見る
  leak     生成文に出た、その場面の文脈に無い原作固有語。想起の直接の証拠

使い方。
  python3 scripts/build_anonymization_control.py build
  python3 scripts/build_anonymization_control.py record --reply <返答を保存したファイル>
  python3 scripts/build_anonymization_control.py measure
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from replay_flow import ctx_block, parse_blocks, sets_block, strip_comment  # noqa: E402

S3 = ROOT / "experiments" / "study03_baseline-replay"
SRC = ROOT / "common" / "source" / "asuka"
PROMPTS = ROOT / "common" / "replay_prompts"
OUT = S3 / "runs" / "20260915-anon-control"

# 6月の実行のうち、近逐語一致が出た条件と世代。表4の3つめの例がここ。
BASE_RUN = "20260624-113018-condB"
BASE_GEN = "gen4"

# 置換表。長い語を先に置く。順序が結果を決めるので並べ替えない。
SUBST = [
    ("ヱヴァンゲリヲン新劇場版：破", "本作品"),
    ("式波・アスカ・ラングレー", "対象人物"),
    ("バカシンジ", "バカ少年A"),  # 罵倒呼称そのものが判断カテゴリなので、罵倒の印を残す
    ("碇司令", "最高責任者"),
    ("エヴァンゲリヲン", "機体"),
    ("ヱヴァンゲリヲン", "機体"),
    ("アスカ", "対象人物"),
    ("式波", "対象人物"),
    ("シンジ", "少年A"),
    ("綾波", "少女B"),
    ("ミサト", "上官C"),
    ("ヒカリ", "同級生D"),
    ("加持", "成人E"),
    ("初号機", "機体1"),
    ("2号機", "機体2"),
    ("0号機", "機体0"),
    ("3号機", "機体3"),
    ("エヴァ", "機体"),
    ("ヱヴァ", "機体"),
    ("使徒", "敵"),
    ("シンちゃん", "少年Aちゃん"),
    ("ケンスケ", "同級生K"),
    ("トウジ", "同級生T"),
    ("シゲル", "職員S"),
    ("マコト", "職員N"),
    ("ネルフ", "組織"),
    ("プラグスーツ", "搭乗服"),
    ("ATフィールド", "防壁"),
]

# 置換しない語。固有名ではなく手法が作った判断軸か、一般語である。
KEEP = ["えこひいき", "七光り", "命令権拒否", "世界で唯一の居場所", "人形",
        "日本人のはっきりしなさ", "エリート", "状況"]

# leak の判定に使う原作固有語。置換表の左側と、文脈に出る話者名を合わせたもの。
SOURCE_TERMS = [
    "シンちゃん", "アスカ", "式波", "シンジ", "碇", "綾波", "レイ", "ミサト", "葛城", "ヒカリ", "加持",
    "ケンスケ", "トウジ", "マヤ", "リツコ", "シゲル", "マコト", "ゲンドウ", "冬月", "ペンペン",
    "エヴァ", "ヱヴァ", "使徒", "ネルフ", "NERV", "プラグスーツ", "ATフィールド",
    "初号機", "2号機", "0号機", "3号機", "4号機", "セカンドインパクト", "サードインパクト",
]


# §0 に揃えた置換表。2026年9月15日。update-prompts §0「話者の表記」と「作品固有の語が本文に出る場合」。
# 在席の系列は test に話者として出た順。アスカは再現対象なので 〔A〕 に固定する。
# 不在の系列は test の話者に出ない人物。碇司令だけが当たる。
# 振り方は全場面で共通にした。要件5から外れる1点で、理由は PUB-011 の log にある。
SUBST_SYM = [
    ("ヱヴァンゲリヲン新劇場版：破", "〔本作品〕"),
    ("式波・アスカ・ラングレー", "〔A〕"),
    ("バカシンジ", "バカ〔E〕"),
    ("シンちゃん", "〔E〕ちゃん"),
    ("碇司令", "〔X〕"),
    ("エヴァンゲリヲン", "〔機体〕"),
    ("ヱヴァンゲリヲン", "〔機体〕"),
    ("シングルコンバット", "単独戦闘"),
    ("アスカ", "〔A〕"), ("式波", "〔A〕"),
    ("加持", "〔B〕"), ("ケンスケ", "〔C〕"), ("トウジ", "〔D〕"),
    ("シンジ", "〔E〕"), ("綾波", "〔F〕"), ("レイ", "〔F〕"),
    ("シゲル", "〔G〕"), ("マコト", "〔H〕"), ("ヒカリ", "〔I〕"),
    ("ミサト", "〔J〕"), ("葛城", "〔J〕"),
    ("碇", "〔X〕"),
    ("2号機", "〔機体A〕"), ("0号機", "〔機体B〕"), ("初号機", "〔機体C〕"), ("3号機", "〔機体D〕"),
    ("エヴァ", "〔機体〕"), ("ヱヴァ", "〔機体〕"),
    ("使徒", "〔敵〕"),
    ("ATフィールド", "〔防御の仕組み〕"),
    ("ネルフ", "〔組織A〕"),
    ("プラグスーツ", "〔搭乗服〕"),
]

SPEAKER_SYM = {"状況": "〔※〕"}

TABLE = {"words": SUBST, "symbols": SUBST_SYM}
SCHEME = ["words"]


def anon(s: str) -> str:
    for a, b in TABLE[SCHEME[0]]:
        s = s.replace(a, b)
    if SCHEME[0] == "symbols":
        for a, b in SPEAKER_SYM.items():
            s = s.replace(a, b)
    return s


def test_sets() -> list[dict]:
    data = json.loads((SRC / "utterance_sets.json").read_text(encoding="utf-8"))
    t = [u for u in data["utterance_sets"] if u["split"] == "test"]
    t.sort(key=lambda x: x["id"])
    return t


def read_gen_tsv(p: Path) -> dict[str, str]:
    out = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("id\t"):
            continue
        c = ln.split("\t", 1)
        if len(c) == 2:
            out[c[0].strip()] = c[1].strip()
    return out



def norm(t: str) -> str:
    return "".join(t.split())


def conflicts(a: dict, b: dict) -> bool:
    """a の原作発話が b の文脈に丸ごと入っているか。どちらの向きも見る。"""
    for x, y in ((a, b), (b, a)):
        g = norm(x["gold"])
        ctx = norm(" ".join(c["text"] for c in y["context"]))
        if len(g) >= 10 and g[:20] in ctx:
            return True
    return False


def split_batches(sets: list[dict], size: int = 3) -> list[list[dict]]:
    """答えが同じ貼り付けに入らない組み方。決め方は決定的で、乱数を使わない。

    u047 から u050 は互いに全部衝突するので4バッチが下限である。
    バッチの大きさをそろえるのは、大きさ自体が別の変数になるのを避けるため。
    """
    by_id = {u["id"]: u for u in sets}
    con = {u["id"]: {v["id"] for v in sets if v["id"] != u["id"] and conflicts(u, v)} for u in sets}
    n = max(len(con[i]) + 1 for i in con)
    n = max(n, -(-len(sets) // size))
    batches: list[list[dict]] = [[] for _ in range(n)]
    for i in sorted((i for i in con if con[i]), key=lambda x: (-len(con[x]), x)):
        for b in batches:
            if len(b) < size and all(not conflicts(by_id[i], u) for u in b):
                b.append(by_id[i])
                break
        else:
            raise SystemExit(f"{i} を置けるバッチが無い。size を上げる")
    for i in sorted(i for i in con if not con[i]):
        min(batches, key=len).append(by_id[i])
    for b in batches:
        b.sort(key=lambda u: u["id"])
    return batches


def anon_sets(sets: list[dict]) -> list[dict]:
    """文脈と原作発話の両方へ同じ置換をかける。片方だけだと比較が成り立たない。"""
    out = []
    for u in sets:
        v = dict(u)
        v["context"] = [{"speaker": anon(c["speaker"]), "text": anon(c["text"])} for c in u["context"]]
        v["gold"] = anon(u["gold"])
        out.append(v)
    return out


def cmd_build(args):
    OUT.mkdir(parents=True, exist_ok=True)
    sp_orig = (S3 / "runs" / BASE_RUN / BASE_GEN / "03_chara_prompt.md").read_text(encoding="utf-8")
    instr_orig = strip_comment((PROMPTS / "gen_instruction.md").read_text(encoding="utf-8"))
    SCHEME[0] = args.scheme
    arm = "orig" if args.arm == "orig" else args.scheme
    if args.arm == "anon":
        sp, instr, sets = anon(sp_orig), anon(instr_orig), anon_sets(test_sets())
    else:
        sp, instr, sets = sp_orig, instr_orig, test_sets()
    batches = split_batches(sets, args.size)
    header = f"{sp}\n\n---\n{instr}\n\n# 場面\n"
    pastes = [header + sets_block(b) for b in batches]
    paste = "\n".join(pastes)

    left = sorted({t for t in SOURCE_TERMS if t in paste})
    (OUT / f"03_chara_prompt.{arm}.md").write_text(sp, encoding="utf-8")
    (OUT / f"gen_instruction.{arm}.md").write_text(instr, encoding="utf-8")
    for n, pt in enumerate(pastes, 1):
        (OUT / f"_paste.{arm}.batch{n}.txt").write_text(pt, encoding="utf-8")
    (OUT / "batches.tsv").write_text(
        "\n".join(["batch\tids"] + [f"{n}\t{','.join(u['id'] for u in b)}"
                                   for n, b in enumerate(batches, 1)]) + "\n", encoding="utf-8")
    (OUT / f"gold.{arm}.tsv").write_text(
        "\n".join(["id\tgold_anon"] + [f"{u['id']}\t{u['gold'].replace(chr(10), ' ')}" for u in sets]) + "\n",
        encoding="utf-8")
    tbl = ["元の語\t置換後\t貼り付け全体での件数"]
    orig_paste = f"{sp_orig}\n{instr_orig}\n{sets_block(test_sets())}"
    tbl += [f"{a}\t{b}\t{orig_paste.count(a)}" for a, b in TABLE[SCHEME[0]]]
    (OUT / f"subst_table.{SCHEME[0]}.tsv").write_text("\n".join(tbl) + "\n", encoding="utf-8")

    print(f"出力先: {OUT}")
    print(f"  条件: {'固有名を伏せた' if arm == 'anon' else '固有名あり'}")
    print(f"  もとの世代: {BASE_RUN}/{BASE_GEN}")
    print(f"  場面: {len(sets)}件")
    print(f"  置換した総件数: {sum(orig_paste.count(a) for a, _ in SUBST)}")
    print(f"  貼り付けに残った原作語: {', '.join(left) if left else 'なし'}")
    print(f"  残す判断軸: {', '.join(w for w in KEEP if w in paste)}")
    for n, (b, pt) in enumerate(zip(batches, pastes), 1):
        print(f"  バッチ{n}: {', '.join(u['id'] for u in b)}  {len(pt)}字 → _paste.{arm}.batch{n}.txt")


def cmd_record(args):
    SCHEME[0] = args.scheme
    arm = "orig" if args.arm == "orig" else args.scheme
    blocks = {}
    for f in args.reply:
        blocks.update(parse_blocks(Path(f).read_text(encoding="utf-8")))
    sets = test_sets()
    miss = [u["id"] for u in sets if u["id"] not in blocks]
    rows = ["id\tgen"] + [f"{u['id']}\t{blocks.get(u['id'], '')}" for u in sets]
    (OUT / f"t04_gen_test.{arm}.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (OUT / f"_reply.{arm}.txt").write_text(
        "\n".join(Path(f).read_text(encoding="utf-8") for f in args.reply), encoding="utf-8")
    print(f"取り込み: {len(blocks)}/{len(sets)}件 → t04_gen_test.{arm}.tsv")
    if miss:
        print(f"  欠け: {', '.join(miss)}")


def ngram_overlap(gen: str, gold: str, n: int = 3) -> float:
    """原作発話の n-gram のうち、生成文に出た割合。文字単位。"""
    def grams(s):
        s = "".join(s.split())
        return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}
    g = grams(gold)
    return len(g & grams(gen)) / len(g) if g else 0.0


def cmd_measure(args):
    sets = {u["id"]: u for u in anon_sets(test_sets())}
    anon_gen = read_gen_tsv(OUT / "t04_gen_test.tsv")
    base_gen = read_gen_tsv(S3 / "runs" / BASE_RUN / BASE_GEN / "t04_gen_test.tsv")
    base_sets = {u["id"]: u for u in test_sets()}

    print(f"{'場面':6}{'逐語一致 元':>12}{'逐語一致 匿名':>14}{'差':>8}   文脈に無い原作語")
    rows = ["id\toverlap_base\toverlap_anon\tleak_base\tleak_anon"]
    tb = ta = 0.0
    lb = la = 0
    for sid, u in sets.items():
        gold = u["gold"]
        ctx = ctx_block(u["context"])
        ob = ngram_overlap(base_gen.get(sid, ""), base_sets[sid]["gold"])
        oa = ngram_overlap(anon_gen.get(sid, ""), gold)
        leak_b = sorted({t for t in SOURCE_TERMS if t in base_gen.get(sid, "") and t not in ctx})
        leak_a = sorted({t for t in SOURCE_TERMS if t in anon_gen.get(sid, "") and t not in ctx})
        tb += ob
        ta += oa
        lb += len(leak_b)
        la += len(leak_a)
        print(f"{sid:6}{ob:>12.3f}{oa:>14.3f}{oa - ob:>+8.3f}   元={','.join(leak_b) or '-'} / 匿名={','.join(leak_a) or '-'}")
        rows.append(f"{sid}\t{ob:.3f}\t{oa:.3f}\t{'|'.join(leak_b)}\t{'|'.join(leak_a)}")
    n = len(sets)
    print(f"\n平均の逐語一致  元={tb / n:.3f}  匿名={ta / n:.3f}  差={ta / n - tb / n:+.3f}")
    print(f"文脈に無い原作語の総数  元={lb}件  匿名={la}件")
    (OUT / "measure.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"→ {OUT / 'measure.tsv'}")



# 流入元を切り分けるための的を絞った条件。2026年9月15日。
# nickname: 型2。愛称から本名を当てられるかを見る。文脈の「シンちゃん」は残し、
#   それ以外の「シンジ」だけを伏せる。作品は同定できる状態に保つ。u030 の1場面だけ。
# letters: 型3。「機体3」から「3号機」が出たのが数字の手がかりか記憶かを分ける。
#   個体の記号から数字を外し、機体a から機体d にする。u048 を含むバッチ。
PROBES = {
    "同定あり愛称あり": {
        "scenes": ["u030"],
        "subst": [("バカシンジ", "バカ少年A"), ("シンジ", "少年A")],
        "keep": ["シンちゃん"],
    },
    # 型2の追い込み。愛称も伏せる。他は「同定あり愛称あり」と同じ。
    # 文脈の引き金が無くても実名が出るかを見る。流入元1の検査。
    "同定あり愛称なし": {
        "scenes": ["u030"],
        "subst": [("シンちゃん", "少年Aちゃん"), ("バカシンジ", "バカ少年A"), ("シンジ", "少年A")],
        "keep": [],
    },
    # 型2の追い込み。作品の同定を消し、愛称だけ残す。流入元3の検査。
    "同定なし愛称あり": {
        "scenes": ["u030"],
        "subst": [
            ("ヱヴァンゲリヲン新劇場版：破", "本作品"),
            ("式波・アスカ・ラングレー", "対象人物"),
            ("バカシンジ", "バカ少年A"), ("碇司令", "最高責任者"),
            ("エヴァンゲリヲン", "機体"), ("ヱヴァンゲリヲン", "機体"),
            ("アスカ", "対象人物"), ("式波", "対象人物"),
            ("シンジ", "少年A"), ("綾波", "少女B"), ("ミサト", "上官C"),
            ("ヒカリ", "同級生D"), ("加持", "成人E"),
            ("初号機", "機体1"), ("2号機", "機体2"), ("0号機", "機体0"), ("3号機", "機体3"),
            ("エヴァ", "機体"), ("ヱヴァ", "機体"), ("使徒", "敵"),
        ],
        "keep": ["シンちゃん"],
    },
    "letters": {
        "scenes": ["u011", "u019", "u048"],
        "subst": [
            ("ヱヴァンゲリヲン新劇場版：破", "本作品"),
            ("式波・アスカ・ラングレー", "対象人物"),
            ("バカシンジ", "バカ少年A"),
            ("碇司令", "最高責任者"),
            ("エヴァンゲリヲン", "機体"), ("ヱヴァンゲリヲン", "機体"),
            ("アスカ", "対象人物"), ("式波", "対象人物"),
            ("シンちゃん", "少年Aちゃん"),
            ("シンジ", "少年A"), ("綾波", "少女B"), ("ミサト", "上官C"),
            ("ヒカリ", "同級生D"), ("加持", "成人E"),
            ("ケンスケ", "同級生K"), ("トウジ", "同級生T"),
            ("シゲル", "職員S"), ("マコト", "職員N"),
            ("2号機", "機体a"), ("0号機", "機体b"), ("初号機", "機体c"), ("3号機", "機体d"),
            ("エヴァ", "機体"), ("ヱヴァ", "機体"),
            ("使徒", "敵"), ("ネルフ", "組織"), ("プラグスーツ", "搭乗服"),
            ("ATフィールド", "防壁"),
        ],
        "keep": [],
    },
}


def cmd_probe(args):
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = PROBES[args.name]
    sp_orig = (S3 / "runs" / BASE_RUN / BASE_GEN / "03_chara_prompt.md").read_text(encoding="utf-8")
    instr_orig = strip_comment((PROMPTS / "gen_instruction.md").read_text(encoding="utf-8"))

    def sub(t):
        for a, b in cfg["subst"]:
            t = t.replace(a, b)
        return t

    sets = [u for u in test_sets() if u["id"] in cfg["scenes"]]
    out = []
    for u in sets:
        v = dict(u)
        v["context"] = [{"speaker": sub(c["speaker"]), "text": sub(c["text"])} for c in u["context"]]
        v["gold"] = sub(u["gold"])
        out.append(v)
    sp, instr = sub(sp_orig), sub(instr_orig)
    paste = f"{sp}\n\n---\n{instr}\n\n# 場面\n{sets_block(out)}"
    (OUT / f"_paste.probe-{args.name}.txt").write_text(paste, encoding="utf-8")
    (OUT / f"gold.probe-{args.name}.tsv").write_text(
        "\n".join(["id\tgold"] + [f"{u['id']}\t{u['gold'].replace(chr(10), ' ')}" for u in out]) + "\n",
        encoding="utf-8")
    print(f"的を絞った条件: {args.name}")
    print(f"  場面: {', '.join(cfg['scenes'])}")
    print(f"  残した語: {', '.join(cfg['keep']) or 'なし'}  → 貼り付けでの件数 "
          f"{', '.join(f'{w}={paste.count(w)}' for w in cfg['keep']) or '-'}")
    left = sorted({t for t in SOURCE_TERMS if t in paste and t not in cfg["keep"]})
    print(f"  残った原作語: {', '.join(left) if left else 'なし'}")
    print(f"  {len(paste)}字 → _paste.probe-{args.name}.txt")


def main():
    ap = argparse.ArgumentParser(description="匿名化の統制。査読 R2-3 への対応")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="貼り付け文面を作る")
    b.add_argument("--scheme", choices=("words", "symbols"), default="symbols",
                   help="symbols=§0 の亀甲記号 / words=9月15日の語による初回版")
    b.add_argument("--arm", choices=("anon", "orig"), default="anon",
                   help="anon=固有名を伏せる / orig=固有名あり。どちらもバッチは同じ組み方")
    b.add_argument("--size", type=int, default=3, help="1バッチの場面数")
    b.set_defaults(func=cmd_build)
    r = sub.add_parser("record", help="返答を取り込む")
    r.add_argument("--reply", required=True, nargs="+")
    r.add_argument("--arm", choices=("anon", "orig"), required=True)
    r.add_argument("--scheme", choices=("words", "symbols"), default="symbols")
    r.set_defaults(func=cmd_record)
    pr = sub.add_parser("probe", help="流入元を切り分ける条件を作る")
    pr.add_argument("name", choices=tuple(PROBES))
    pr.set_defaults(func=cmd_probe)
    sub.add_parser("measure", help="2つを測る").set_defaults(func=cmd_measure)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
