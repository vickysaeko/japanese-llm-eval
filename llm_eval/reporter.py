"""report: scores.json + results.json から Markdown レポートを生成する。"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime

from .rubric import DIMENSION_IDS, load_rubric


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _find_latest_scores(outputs_dir: str = "outputs") -> tuple[str, str] | None:
    """outputs/ 配下で最新の scores.json と対応する results.json を探す。"""
    candidates: list[tuple[float, str]] = []
    for root, _dirs, files in os.walk(outputs_dir):
        if "scores.json" in files:
            p = os.path.join(root, "scores.json")
            candidates.append((os.path.getmtime(p), p))
    if not candidates:
        return None
    candidates.sort()
    scores_path = candidates[-1][1]
    results_path = os.path.join(os.path.dirname(scores_path), "results.json")
    return scores_path, results_path


def generate_report(
    scores_path: str | None,
    results_path: str | None,
    out_path: str | None = None,
    rubric_path: str | None = None,
) -> str:
    if scores_path is None or results_path is None:
        found = _find_latest_scores()
        if found is None:
            raise FileNotFoundError("scores.json が見つかりません。先に `python -m llm_eval run` と `python -m llm_eval score` を実行してください。")
        scores_path, results_path = found
    with open(scores_path, encoding="utf-8") as f:
        scores_data = json.load(f)
    with open(results_path, encoding="utf-8") as f:
        results_data = json.load(f)

    rubric = load_rubric(rubric_path)
    dim_names = {d["id"]: d["name"] for d in rubric.get("dimensions", [])}
    scores = scores_data.get("scores", [])
    results = {(r["prompt_id"], r["model"]): r for r in results_data.get("results", [])}

    # モデルごとの平均
    by_model: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    overall_by_model: dict[str, list[float]] = defaultdict(list)
    for s in scores:
        for dim in DIMENSION_IDS:
            by_model[s["model"]][dim].append(float(s["scores"].get(dim, 0)))
        overall_by_model[s["model"]].append(float(s.get("overall", 0)))

    ranking = sorted(
        ((m, _avg(v)) for m, v in overall_by_model.items()),
        key=lambda x: x[1],
        reverse=True,
    )

    if out_path is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = os.path.join("reports", f"report-{stamp}.md")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    lines: list[str] = []
    lines.append("# 日本語LLM評価レポート")
    lines.append("")
    lines.append(f"- 作成日時: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- 実行ID: {scores_data.get('run_id', '-')}")
    lines.append(f"- 採点方法: {scores_data.get('judge', '-')}（heuristic は暫定値です。人間レビューでの確認を推奨します）")
    lines.append(f"- ルーブリック: {scores_data.get('rubric', '-')}")
    lines.append(f"- 対象モデル: {', '.join(sorted(overall_by_model))}")
    lines.append(f"- 対象プロンプト数: {len({s['prompt_id'] for s in scores})}")
    lines.append("")
    lines.append("## 総合ランキング")
    lines.append("")
    lines.append("| 順位 | モデル | 総合平均（5点満点） |")
    lines.append("| --- | --- | --- |")
    for i, (model, avg) in enumerate(ranking, 1):
        lines.append(f"| {i} | {model} | {avg:.2f} |")
    lines.append("")
    lines.append("## モデル別・観点別平均")
    lines.append("")
    header = "| モデル | " + " | ".join(dim_names.get(d, d) for d in DIMENSION_IDS) + " | 総合 |"
    lines.append(header)
    lines.append("| --- | " + " | ".join(["---"] * len(DIMENSION_IDS)) + " | --- |")
    for model, avg in ranking:
        cells = [f"{_avg(by_model[model][d]):.2f}" for d in DIMENSION_IDS]
        lines.append(f"| {model} | " + " | ".join(cells) + f" | {avg:.2f} |")
    lines.append("")
    lines.append("## プロンプト別スコア")
    lines.append("")
    lines.append("| prompt_id | カテゴリ | モデル | 総合 | 正確性 | 流暢さ | 文法 | 文化・敬語 | 指示遵守 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for s in sorted(scores, key=lambda x: (x["prompt_id"], x["model"])):
        sc = s["scores"]
        lines.append(
            f"| {s['prompt_id']} | {s['category']} | {s['model']} | {s.get('overall', 0):.2f} | "
            f"{sc.get('accuracy', '-')} | {sc.get('fluency', '-')} | {sc.get('grammar', '-')} | "
            f"{sc.get('cultural', '-')} | {sc.get('instruction', '-')} |"
        )
    lines.append("")
    lines.append("## 出力例（2〜3件）")
    lines.append("")
    examples = scores[:3]
    for s in examples:
        r = results.get((s["prompt_id"], s["model"]))
        output = (r or {}).get("output", "") if r else ""
        excerpt = output[:300].replace("\n", " ")
        lines.append(f"### {s['prompt_id']} / {s['model']} — 総合 {s.get('overall', 0):.2f}")
        lines.append("")
        lines.append(f"- カテゴリ: {s['category']}")
        lines.append(f"- スコア: {s['scores']}")
        lines.append(f"- 備考: {s.get('notes', '')}")
        lines.append("")
        lines.append(f"> {excerpt}")
        lines.append("")
    lines.append("## 注意点")
    lines.append("")
    lines.append("- ヒューリスティックによるスコアは暫定値です。正式な評価には人間レビューか LLM-as-judge を使ってください。")
    lines.append("- Mock の出力はテスト用の疑似出力であり、実際のモデルの性能を示しません。")
    lines.append("- サンプル数が少ないため、平均値は参考値です。プロンプトを増やして再実行してください。")
    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"保存しました: {out_path}")
    return out_path
