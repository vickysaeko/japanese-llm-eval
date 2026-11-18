"""run: プロンプト集 → 各モデルの出力取得 → results.json に保存。"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime

from .providers import ProviderError, get_provider


def load_prompts(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        prompts = data.get("prompts", [])
    elif isinstance(data, list):
        prompts = data
    else:
        raise ValueError("プロンプトファイルの形式が不正です。JSONのリスト、または {'prompts': [...]} を使ってください。")
    for p in prompts:
        if "id" not in p or "prompt" not in p:
            raise ValueError(f"プロンプトに id / prompt が必要です: {p}")
        p.setdefault("category", "general")
    return prompts


def run_evaluation(models: list[str], prompts_path: str, out_dir: str) -> str:
    """各モデル × 各プロンプトを実行し、results.json を out_dir に保存してパスを返す。"""
    prompts = load_prompts(prompts_path)
    os.makedirs(out_dir, exist_ok=True)

    run_id = os.path.basename(os.path.normpath(out_dir)) or datetime.now().strftime("run-%Y%m%d-%H%M%S")
    results: list[dict] = []
    used_models: list[str] = []

    for model_name in models:
        try:
            provider = get_provider(model_name)
        except ProviderError as exc:
            print(f"[skip] {model_name}: {exc}")
            continue
        used_models.append(provider.name)
        for item in prompts:
            start = time.time()
            output = ""
            error = None
            try:
                output = provider.generate(item["prompt"], prompt_id=item["id"], category=item.get("category", ""))
            except Exception as exc:  # 1問の失敗で全体を止めない
                error = str(exc)
                print(f"[error] {provider.name} / {item['id']}: {error}")
            latency_ms = int((time.time() - start) * 1000)
            results.append(
                {
                    "prompt_id": item["id"],
                    "category": item.get("category", "general"),
                    "title": item.get("title", ""),
                    "prompt": item["prompt"],
                    "model": provider.name,
                    "output": output,
                    "latency_ms": latency_ms,
                    "error": error,
                }
            )
            print(f"[{provider.name}] {item['id']} ({latency_ms}ms){' ERROR' if error else ''}")

    if not used_models:
        raise ProviderError("実行できるモデルがありませんでした。--models mock を試すか、APIキーを環境変数で設定してください。")

    payload = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "prompts_file": prompts_path,
        "models": used_models,
        "results": results,
    }
    out_path = os.path.join(out_dir, "results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"保存しました: {out_path}（{len(results)}件）")
    return out_path
