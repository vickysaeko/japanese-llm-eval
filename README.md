# 日本語LLM評価ツール（プロトタイプ）

日本語のLLM出力を、独自ルーブリックで評価するための小さなCLIツールです。
プロンプト集 → 複数モデルの出力取得 → 採点 → レポート出力、という流れを
標準ライブラリ中心のPythonで実現しています。

> **目的：** 「日本語AIの品質評価」を専門領域として確立するための、
> 公開可能な評価ツールの試作版（v0.1.0）。実務の品質判断の経験を、
> 再現可能な形にすることを目指しています。

## できること

- サンプルプロンプト（翻訳・要約・対話・校正・敬語・ビジネス要約）で複数モデルを比較
- 独自ルーブリック（5観点×5段階）で採点
- LLM-as-judge または人間レビュー用の手動採点シート
- Markdownレポートの自動生成（平均点・ランキング・プロンプト別表・出力例）

## 使い方（最短デモ：APIキー不要）

```bash
cd llm-eval-prototype
python3 -m llm_eval run --models mock --prompts prompts/sample.json
# → outputs/run-YYYYMMDD-HHMMSS/results.json ができる

python3 -m llm_eval score
# → 同じディレクトリに scores.json と scoring_template.csv ができる

python3 -m llm_eval report
# → reports/report-YYYYMMDD-HHMMSS.md ができる
```

`--out` で出力先を明示することもできます：

```bash
python3 -m llm_eval run --models mock,claude --prompts prompts/sample.json --out outputs/run-20261118-120000
python3 -m llm_eval score --input outputs/run-20261118-120000/results.json --out outputs/run-20261118-120000/scores.json
python3 -m llm_eval report --scores outputs/run-20261118-120000/scores.json --results outputs/run-20261118-120000/results.json --out reports/report-20261118-120000.md
```

## セットアップ

```bash
python3 --version  # 3.11 以上
pip install -r requirements.txt  # requests のみ。Mockだけなら不要
cp .env.example .env  # 実モデルを使う場合のみ。キーは絶対にコミットしないこと
```

### 実モデルを使う場合（任意）

APIキーは環境変数からのみ読みます。コードやファイルに直書きしないでください。

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AIza..."
python3 -m llm_eval run --models mock,claude,openai,gemini
```

キーがないモデルはスキップされ、明確なメッセージが出ます。
モデル名は環境変数で変えられます：`ANTHROPIC_MODEL` / `OPENAI_MODEL` / `GOOGLE_MODEL`。

## Claude Code での使い方

このリポジトリをClaude Codeで開いて、次のように指示できます：

```text
llm-eval-prototype の README を読んで、Mockで run → score → report を実行し、
レポートを確認して。エラーがあれば直して。
```

```text
rubric.yaml の「文化的適切さ・敬語」の5段階の説明を、ビジネスメールの場面に
合わせて具体化して。tests はないので、Mockで end-to-end が通ることを確認して。
```

```text
prompts/sample.json に、プレスリリースの要約プロンプトを2問追加して。
カテゴリは business_summarization にして。
```

開発時の注意：
- 新しいプロバイダーを追加するときは `llm_eval/providers.py` の `BaseProvider` を継承し、
  `PROVIDER_CLASSES` に登録してください。キーは必ず環境変数から読むこと。
- ルーブリックを変えたときは `rubric.yaml` と `llm_eval/rubric.py` の
  `DEFAULT_RUBRIC` の両方を更新してください（PyYAMLがない環境でも動くため）。

## 採点の仕組み

### ルーブリック（`rubric.yaml`）

5観点、各1〜5点。1=不十分、3=実用レベル、5=優秀。

1. 正確性・事実性
2. 流暢さ・自然さ
3. 文法・表記
4. 文化的適切さ・敬語
5. 指示遵守

各レベルの日本語の説明は `rubric.yaml` を見てください。

### 採点モード

| モード | コマンド | 備考 |
| --- | --- | --- |
| ヒューリスティック（既定） | `python -m llm_eval score` | 空出力・短さを検出する暫定値。正式評価ではない |
| LLM-as-judge | `python -m llm_eval score --judge claude` | ルーブリックを引用した日本語判定プロンプトで採点。キーが必要 |
| 手動レビュー | テンプレートCSVを埋めて集計 | `scoring_template.csv` を埋め、次で集計 |

```bash
# 手動集計
python3 -m llm_eval score --aggregate outputs/run-XXX/scoring_template.csv \
  --input outputs/run-XXX/results.json \
  --out outputs/run-XXX/scores.json
```

## ディレクトリ構成

```text
llm-eval-prototype/
├── README.md
├── requirements.txt
├── rubric.yaml              # 独自ルーブリック（5観点×5段階）
├── .env.example             # APIキーのサンプル（実際のキーは書かない）
├── .gitignore
├── prompts/
│   └── sample.json          # サンプルプロンプト7問
├── llm_eval/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py               # run / score / report
│   ├── providers.py         # Mock / Claude / OpenAI / Gemini
│   ├── rubric.py            # ルーブリック読み込み
│   ├── runner.py            # 出力取得
│   ├── scorer.py            # ヒューリスティック / LLM-as-judge / 手動集計
│   └── reporter.py          # Markdownレポート生成
├── outputs/                 # 生成物（gitignore対象）
└── reports/                 # レポート出力先
```

## 注意点・TODO（GitHub公開に向けて）

- [ ] 実モデルキーでの動作確認（Claude / OpenAI / Gemini）
- [ ] プロンプトの拡充（カテゴリごとに5〜10問、難易度付き）
- [ ] LLM-as-judge のキャリブレーション（人間レビューとの一致率の測定）
- [ ] ルーブリックの妥当性検証（複数レビュアーでの一致率）
- [ ] テストの追加（`pytest`、Mockを使った end-to-end）
- [ ] CI（GitHub Actions での Mock パイプライン実行）
- [ ] ライセンス・CONTRIBUTING の追加

---

## English Summary

A small Python CLI prototype for evaluating Japanese LLM outputs with an
original 5-dimension rubric (accuracy, fluency, grammar, cultural
appropriateness / keigo, instruction following; 1–5 each).

```bash
python3 -m llm_eval run --models mock --prompts prompts/sample.json
python3 -m llm_eval score
python3 -m llm_eval report
```

Providers are pluggable (`llm_eval/providers.py`). Mock works without keys.
Real providers (Claude / OpenAI / Gemini) read keys only from environment
variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`).
Scoring supports heuristic defaults, LLM-as-judge (`--judge claude`),
and a human-fillable CSV template with aggregation.
