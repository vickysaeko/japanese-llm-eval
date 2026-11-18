"""CLI: python -m llm_eval run | score | report"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime


def _default_out_dir() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return os.path.join("outputs", f"run-{stamp}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llm_eval",
        description="日本語LLM評価ツール（プロトタイプ）: プロンプト → 出力取得 → 採点 → レポート",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("run", help="各モデルでプロンプトを実行し、results.json を保存する")
    pr.add_argument("--models", default="mock", help="カンマ区切り。例: mock,claude,openai,gemini（既定: mock）")
    pr.add_argument("--prompts", default="prompts/sample.json", help="プロンプトJSON（既定: prompts/sample.json）")
    pr.add_argument("--out", default=None, help="出力先ディレクトリ（既定: outputs/run-YYYYMMDD-HHMMSS/）")

    ps = sub.add_parser("score", help="保存済み出力を採点する")
    ps.add_argument("--input", default=None, help="results.json のパス（既定: 最新の outputs/*/results.json）")
    ps.add_argument("--out", default=None, help="scores.json のパス（既定: <inputと同じディレクトリ>/scores.json）")
    ps.add_argument("--judge", default="none", choices=["none", "claude", "openai", "gemini"],
                    help="LLM-as-judge に使うモデル（既定: none = ヒューリスティック + 手動テンプレート）")
    ps.add_argument("--aggregate", default=None, help="人間が埋めた scoring_template.csv のパス。指定時は集計モードになる")
    ps.add_argument("--rubric", default=None, help="rubric.yaml のパス（既定: ./rubric.yaml）")

    prp = sub.add_parser("report", help="scores.json から Markdown レポートを生成する")
    prp.add_argument("--scores", default=None, help="scores.json のパス（既定: 最新の outputs/*/scores.json）")
    prp.add_argument("--results", default=None, help="results.json のパス（既定: scores.json と同じディレクトリ）")
    prp.add_argument("--out", default=None, help="レポートの出力先（既定: reports/report-YYYYMMDD-HHMMSS.md）")
    prp.add_argument("--rubric", default=None, help="rubric.yaml のパス")
    return p


def _find_latest(pattern: str) -> str | None:
    """outputs/ 配下で最新の pattern ファイルを探す。"""
    candidates: list[tuple[float, str]] = []
    for root, _dirs, files in os.walk("outputs"):
        if pattern in files:
            path = os.path.join(root, pattern)
            candidates.append((os.path.getmtime(path), path))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "run":
        from .runner import run_evaluation

        models = [m.strip() for m in args.models.split(",") if m.strip()]
        out_dir = args.out or _default_out_dir()
        try:
            run_evaluation(models, args.prompts, out_dir)
        except Exception as exc:
            print(f"エラー: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.command == "score":
        from .scorer import aggregate_manual, score_results

        if args.aggregate:
            input_path = args.input or _find_latest("results.json")
            if input_path is None:
                print("エラー: results.json が見つかりません。--input を指定してください。", file=sys.stderr)
                return 1
            out_path = args.out or os.path.join(os.path.dirname(input_path), "scores.json")
            try:
                aggregate_manual(args.aggregate, input_path, out_path)
            except Exception as exc:
                print(f"エラー: {exc}", file=sys.stderr)
                return 1
            return 0

        input_path = args.input or _find_latest("results.json")
        if input_path is None:
            print("エラー: results.json が見つかりません。先に `python -m llm_eval run` を実行してください。", file=sys.stderr)
            return 1
        out_path = args.out or os.path.join(os.path.dirname(input_path), "scores.json")
        try:
            score_results(input_path, out_path, judge=args.judge, rubric_path=args.rubric)
        except Exception as exc:
            print(f"エラー: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.command == "report":
        from .reporter import generate_report

        scores_path = args.scores
        results_path = args.results
        if scores_path is None:
            scores_path = _find_latest("scores.json")
            if scores_path is None:
                print("エラー: scores.json が見つかりません。先に `python -m llm_eval score` を実行してください。", file=sys.stderr)
                return 1
            results_path = results_path or os.path.join(os.path.dirname(scores_path), "results.json")
        try:
            generate_report(scores_path, results_path, out_path=args.out, rubric_path=args.rubric)
        except Exception as exc:
            print(f"エラー: {exc}", file=sys.stderr)
            return 1
        return 0

    return 1
