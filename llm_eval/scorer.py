"""score: 保存済み出力の採点。

既定は (b) 手動採点テンプレート + ルールベースのヒューリスティック。
  - scores.json をヒューリスティックで生成（Mockのみでも動作）
  - scoring_template.csv / scoring_template.md を生成し、人間が埋められるようにする
  - 人間が埋めたCSVを --aggregate で集計し、scores.json にできる

(a) LLM-as-judge:
  --judge claude|openai|gemini を指定し、対応するAPIキーがあれば、
  ルーブリックを引用した日本語の判定プロンプトで採点する。
  キーがなければヒューリスティックにフォールバックする。
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re

from .providers import ProviderError, get_provider
from .rubric import DIMENSION_IDS, format_rubric_for_judge, load_rubric

JUDGE_PROMPT_TEMPLATE = """あなたは日本語の品質評価者です。次のルーブリックで、モデルの出力を採点してください。

# ルーブリック
{rubric}

# 採点対象
プロンプト:
{prompt}

モデルの出力:
{output}

# 出力形式
JSONだけを出力してください。余計な説明は不要です。
{{
  "accuracy": 1,
  "fluency": 1,
  "grammar": 1,
  "cultural": 1,
  "instruction": 1,
  "notes": "短い根拠を日本語で1〜2文"
}}
各スコアは 1〜5 の整数です。迷ったときは低いほうを選んでください。
"""


def heuristic_score(output: str, prompt_id: str = "", model: str = "") -> tuple[dict, str]:
    """ルールベースの暫定採点。空出力・極端に短い出力を検出し、他は決定的に 3〜4 を付ける。

    注意: これはプレースホルダー。正式な評価は人間レビューか LLM-as-judge を使うこと。
    """
    text = (output or "").strip()
    if not text:
        return {d: 1 for d in DIMENSION_IDS}, "出力が空です（ヒューリスティック）"
    if len(text) < 10:
        return {d: 2 for d in DIMENSION_IDS}, "出力が極端に短いです（ヒューリスティック）"
    # 決定的に 3〜4 を振る（出力内容のハッシュから）
    seed = int(hashlib.sha256(f"{prompt_id}:{model}:{text[:80]}".encode()).hexdigest()[:4], 16)
    scores: dict[str, int] = {}
    for i, dim in enumerate(DIMENSION_IDS):
        scores[dim] = 4 if (seed + i * 7) % 3 != 0 else 3
    # 敬語カテゴリは文化的適切さを少し厳しめに見る、という意図を注記に残す
    return scores, "ヒューリスティックによる暫定スコアです。人間レビューで確認してください。"


def _parse_judge_json(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    scores: dict[str, int] = {}
    for dim in DIMENSION_IDS:
        try:
            v = int(data.get(dim, 3))
        except Exception:
            v = 3
        scores[dim] = max(1, min(5, v))
    return {"scores": scores, "notes": str(data.get("notes", ""))}


def llm_judge_score(prompt: str, output: str, judge_name: str, rubric: dict) -> tuple[dict, str] | None:
    """LLM-as-judge。キーがない・失敗した場合は None を返す。"""
    try:
        judge = get_provider(judge_name)
    except ProviderError as exc:
        print(f"[judge] {judge_name} を使えません: {exc} → ヒューリスティックにフォールバックします。")
        return None
    judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
        rubric=format_rubric_for_judge(rubric), prompt=prompt, output=output
    )
    try:
        raw = judge.generate(judge_prompt, prompt_id="judge")
    except Exception as exc:
        print(f"[judge] 判定に失敗しました: {exc} → ヒューリスティックにフォールバックします。")
        return None
    parsed = _parse_judge_json(raw)
    if parsed is None:
        print("[judge] 判定結果のJSON解析に失敗しました → ヒューリスティックにフォールバックします。")
        return None
    return parsed["scores"], f"LLM-as-judge（{judge_name}）: {parsed['notes']}"


def write_template(results: list[dict], out_dir: str) -> tuple[str, str]:
    """人間が埋める採点テンプレート（CSV + Markdown）を生成する。"""
    csv_path = os.path.join(out_dir, "scoring_template.csv")
    md_path = os.path.join(out_dir, "scoring_template.md")
    header = ["prompt_id", "category", "model"] + [f"{d}_1_5" for d in DIMENSION_IDS] + ["notes"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in results:
            w.writerow([r["prompt_id"], r["category"], r["model"]] + [""] * len(DIMENSION_IDS) + [""])
    lines = ["# 手動採点シート", "", "1〜5で埋めてください。空欄のままでは集計されません。", ""]
    lines.append("| prompt_id | category | model | " + " | ".join(DIMENSION_IDS) + " | notes |")
    lines.append("| --- | --- | --- | " + " | ".join(["---"] * len(DIMENSION_IDS)) + " | --- |")
    for r in results:
        lines.append(f"| {r['prompt_id']} | {r['category']} | {r['model']} | " + " | ".join([""] * len(DIMENSION_IDS)) + " |  |")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return csv_path, md_path


def score_results(
    results_path: str,
    out_path: str,
    judge: str = "none",
    rubric_path: str | None = None,
) -> str:
    """results.json を採点し、scores.json を保存する。テンプレートも同ディレクトリに生成する。"""
    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results", [])
    rubric = load_rubric(rubric_path)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)

    scored: list[dict] = []
    for r in results:
        if r.get("error") or not (r.get("output") or "").strip():
            scores = {d: 1 for d in DIMENSION_IDS}
            notes = f"出力なし / エラー: {r.get('error') or '空出力'}"
            method = "heuristic"
        elif judge and judge != "none":
            judged = llm_judge_score(r["prompt"], r["output"], judge, rubric)
            if judged is not None:
                scores, notes = judged
                method = f"llm_judge:{judge}"
            else:
                scores, notes = heuristic_score(r["output"], r["prompt_id"], r["model"])
                method = "heuristic"
        else:
            scores, notes = heuristic_score(r["output"], r["prompt_id"], r["model"])
            method = "heuristic"
        overall = round(sum(scores.values()) / len(scores), 2) if scores else 0.0
        scored.append(
            {
                "prompt_id": r["prompt_id"],
                "category": r["category"],
                "model": r["model"],
                "scores": scores,
                "overall": overall,
                "notes": notes,
                "method": method,
            }
        )

    payload = {
        "run_id": data.get("run_id"),
        "created_at": data.get("created_at"),
        "judge": judge,
        "rubric": rubric.get("name", "日本語LLM評価ルーブリック v1"),
        "scores": scored,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    csv_path, md_path = write_template(results, out_dir)
    print(f"保存しました: {out_path}（{len(scored)}件）")
    print(f"手動採点テンプレート: {csv_path}")
    print(f"手動採点テンプレート(Markdown): {md_path}")
    print("人間がCSVを埋めたら `python -m llm_eval score --aggregate <埋めたCSV> --input <results.json> --out <scores.json>` で集計できます。")
    return out_path


def aggregate_manual(csv_path: str, results_path: str, out_path: str) -> str:
    """人間が埋めたCSVを集計し、scores.json を作る。空欄の行はスキップする。"""
    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)
    results = {(r["prompt_id"], r["model"]): r for r in data.get("results", [])}
    scored: list[dict] = []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row.get("prompt_id", ""), row.get("model", ""))
            if key not in results:
                continue
            try:
                scores = {d: int(row[f"{d}_1_5"]) for d in DIMENSION_IDS}
            except Exception:
                continue  # 空欄・不正値はスキップ
            if any(v < 1 or v > 5 for v in scores.values()):
                continue
            overall = round(sum(scores.values()) / len(scores), 2)
            scored.append(
                {
                    "prompt_id": key[0],
                    "category": results[key]["category"],
                    "model": key[1],
                    "scores": scores,
                    "overall": overall,
                    "notes": row.get("notes", ""),
                    "method": "manual",
                }
            )
    payload = {
        "run_id": data.get("run_id"),
        "created_at": data.get("created_at"),
        "judge": "manual",
        "rubric": "日本語LLM評価ルーブリック v1",
        "scores": scored,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"集計しました: {out_path}（{len(scored)}件）")
    return out_path
