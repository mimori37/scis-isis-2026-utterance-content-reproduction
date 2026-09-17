"""設定・パス解決の共通モジュール。"""
from __future__ import annotations

import datetime
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

# プロジェクトルート（このファイルの 1つ上の親）
ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")


@dataclass
class Config:
    raw: dict

    @property
    def character(self) -> str:
        return self.raw["character"]

    @property
    def provider(self) -> str:
        return self.raw.get("provider", "openai")

    @property
    def provider_profile(self) -> dict:
        try:
            return self.raw["providers"][self.provider]
        except KeyError:
            raise SystemExit(f"providers に '{self.provider}' の定義がありません（config.yaml）")

    def model(self, kind: str) -> str:
        return self.provider_profile["models"][kind]

    @property
    def base_url(self) -> str | None:
        return self.provider_profile.get("base_url")

    @property
    def api_key(self) -> str:
        env = self.provider_profile.get("api_key_env", "OPENAI_API_KEY")
        key = os.environ.get(env)
        if not key:
            raise SystemExit(
                f"APIキーが未設定です: 環境変数 {env} を設定してください"
                f"（provider='{self.provider}'。.env か環境変数で指定）")
        return key

    @property
    def params(self) -> dict:
        """global params に provider 個別 params を上書きマージ。"""
        merged = dict(self.raw.get("params") or {})
        merged.update(self.provider_profile.get("params") or {})
        return merged

    @property
    def rating_values(self) -> list[str]:
        return self.raw.get("eval", {}).get("rating_values", ["◯", "△", "×"])

    @property
    def user_turns_file(self) -> Path:
        return ROOT / self.raw["dialogue"]["user_turns_file"]

    @property
    def source_dir(self) -> Path:
        return ROOT / "common" / "source" / self.character


def load_config(path: str | os.PathLike | None = None,
                provider: str | None = None) -> Config:
    path = Path(path) if path else (ROOT / "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if provider:                       # Makefile/CLI からの provider 上書き
        raw["provider"] = provider
    return Config(raw=raw)


# ---- 実験ディレクトリ内のファイル名（工程の入出力契約）----
# 各 expN/ 配下で、この命名でファイルを受け渡す。
FILES = {
    "analysis_prompt": "00_analysis_prompt.md",   # 入: 分析プロンプト
    "analysis_sheet":  "01_analysis_sheet.tsv",    # 出: 分析シート（シーン単位 TSV）
    "design_prompt":   "02_design_prompt.md",      # 入: 設計プロンプト
    "chara_prompt":    "03_chara_prompt.md",       # 出: キャラ付けプロンプト
    "dialogue_md":     "04_dialogue.md",           # 出: 会話ログ（可読）
    "dialogue_json":   "04_dialogue.json",         # 出: 会話ログ（構造化）
    "eval_sheet":      "05_eval_sheet.csv",        # 入出: 生成発話＋ユーザー評価（人手入力）
    "feedback_log":    "06_feedback_log.md",       # 出: フィードバックログ（次フェーズへ）
    "next_analysis_prompt": "07_next_analysis_prompt.md",  # 出: 次フェーズ用 修正版 分析プロンプト
    "next_design_prompt":   "08_next_design_prompt.md",    # 出: 次フェーズ用 修正版 設計プロンプト
}


# ---- タイムスタンプ（実験バッチ）と実験番号の解決 ----
# 構成: experiments/<expN>/<timestamp>/<各ファイル>
# タイムスタンプ = 1 回の実験バッチを exp 跨ぎで束ねる識別子。
# 1 バッチは exp1 から始まるので、バッチ一覧 = exp1 配下のタイムスタンプ一覧。
EXPERIMENTS = ROOT / "experiments"
_TS_RE = re.compile(r"\d{8}-\d{6}(?:-\d+)?")
_EXP_RE = re.compile(r"exp\d+")


def exp_index(exp: str) -> int:
    """'exp3' -> 3"""
    return int("".join(c for c in exp if c.isdigit()))


def new_timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def exp_dir(ts: str, exp: str) -> Path:
    return EXPERIMENTS / exp / ts


def exp_file(ts: str, exp: str, key: str) -> Path:
    return exp_dir(ts, exp) / FILES[key]


def new_batch() -> str:
    """常に新しいタイムスタンプ（実験バッチ）を作成して返す（exp1 init 用）。"""
    ts = new_timestamp()
    base = EXPERIMENTS / "exp1"
    if (base / ts).exists():           # 同秒衝突の保険
        ts = ts + "-1"
    (base / ts).mkdir(parents=True, exist_ok=True)
    return ts


def list_timestamps() -> list[str]:
    """バッチ一覧（= exp1 配下のタイムスタンプ）。"""
    d = EXPERIMENTS / "exp1"
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir()
                  if p.is_dir() and _TS_RE.fullmatch(p.name))


def list_exps(ts: str) -> list[str]:
    """その ts（バッチ）が存在する expN を集める。"""
    if not EXPERIMENTS.exists():
        return []
    return sorted((p.name for p in EXPERIMENTS.iterdir()
                   if p.is_dir() and _EXP_RE.fullmatch(p.name) and (p / ts).exists()),
                  key=exp_index)


def resolve_timestamp(ts: str | None, *, create: bool = False) -> str:
    """ts 指定があればそれを、なければ最新のタイムスタンプを返す。

    create=True かつ ts 未指定なら新規タイムスタンプを作成する。
    """
    if ts:
        if create:
            (EXPERIMENTS / "exp1" / ts).mkdir(parents=True, exist_ok=True)
        elif not list_exps(ts):
            raise SystemExit(f"指定タイムスタンプが存在しません: {ts}")
        return ts
    existing = list_timestamps()
    if existing:
        return existing[-1]
    if create:
        return new_batch()
    raise SystemExit("実験タイムスタンプが存在しません。先に `make init EXP=exp1` を実行してください。")


def resolve_exp(ts: str, exp: str | None) -> str:
    """exp 指定があればそれを、なければ ts 内の最新（最大番号）の exp を返す。"""
    if exp:
        return exp
    exps = list_exps(ts)
    if not exps:
        raise SystemExit(f"{ts} に exp ディレクトリがありません。先に init してください。")
    return exps[-1]
