"""Rubric loading.
rubric.yaml is the human-readable definition.
If PyYAML is available it is read, otherwise DEFAULT_RUBRIC is used.
"""
from __future__ import annotations

import os

DEFAULT_RUBRIC = {
    "version": "1.0",
    "name": "Japanese LLM evaluation rubric v1",
    "dimensions": [
        {
            "id": "accuracy",
            "name": "正確性・事実性",
            "description": "内容が正しく、事実の誤り・捏造・重要な欠落がないか",
            "levels": {
                1: "事実誤りや捏造が多く、内容として使えない",
                2: "重要な誤りが複数あり、信頼できない",
                3: "大筋は正しいが、細部の誤りや欠落がある",
                4: "ほぼ正確で、軽微な曖昧さしかない",
                5: "正確で、根拠・条件まで適切に示されている",
            },
        },
        {
            "id": "fluency",
            "name": "流暢さ・自然さ",
            "description": "日本語として自然で、読みやすく、翻訳調・不自然な表現がないか",
            "levels": {
                1: "不自然で読みにくく、意味が取りにくい",
                2: "ところどころ不自然で、読み手に負担がかかる",
                3: "概ね自然だが、やや硬い・翻訳調の箇所がある",
                4: "自然で読みやすい。ほぼ違和感がない",
                5: "非常に自然で、母語話者が書いたように滑らか",
            },
        },
        {
            "id": "grammar",
            "name": "文法・表記",
            "description": "文法・助詞・表記ゆれ・誤字脱字・句読点が適切か",
            "levels": {
                1: "文法ミス・誤字が多く、意味が損なわれる",
                2: "目立つミスが複数ある",
                3: "軽微なミスが数か所あるが、意味は通じる",
                4: "ほぼミスがなく、表記も統一されている",
                5: "ミスがなく、表記・スタイルも統一されている",
            },
        },
        {
            "id": "cultural",
            "name": "文化的適切さ・敬語",
            "description": "敬語・丁寧さ・相手への配慮・文化的文脈が場面に合っているか",
            "levels": {
                1: "敬語・丁寧さが場面に合わず、失礼または不適切",
                2: "敬語の誤用や配慮不足が目立つ",
                3: "概ね適切だが、場面に合わない表現が一部ある",
                4: "場面に合った敬語・配慮ができている",
                5: "場面・相手・関係性を踏まえた、きめ細かい配慮ができている",
            },
        },
        {
            "id": "instruction",
            "name": "指示遵守",
            "description": "プロンプトの指示（形式・長さ・条件・出力形式）を守っているか",
            "levels": {
                1: "指示を守っておらず、求める出力になっていない",
                2: "指示の一部しか守れていない",
                3: "大筋の指示は守れているが、細部で外れている",
                4: "指示をほぼ守れており、形式・条件も合っている",
                5: "指示を完全に守り、求める形式・条件をすべて満たしている",
            },
        },
    ],
}

DIMENSION_IDS = [d["id"] for d in DEFAULT_RUBRIC["dimensions"]]


def load_rubric(path=None):
    """Read rubric.yaml if PyYAML is available, else return DEFAULT_RUBRIC."""
    if path is None:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, "rubric.yaml")
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and "dimensions" in data:
            return data
    except ImportError:
        pass
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return DEFAULT_RUBRIC


def format_rubric_for_judge(rubric):
    """Format the rubric as Japanese text for an LLM-as-judge prompt."""
    lines = []
    for dim in rubric.get("dimensions", DEFAULT_RUBRIC["dimensions"]):
        lines.append("[" + dim["name"] + "]" + dim.get("description", ""))
        levels = dim.get("levels", {})
        for level in (1, 2, 3, 4, 5):
            text = levels.get(level) or levels.get(str(level)) or ""
            lines.append(f"  {level}: {text}")
    return "\n".join(lines)
