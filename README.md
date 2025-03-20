# Logqwest - LLM駆動型 放置型テキストゲーム コンテンツ自動生成ツール

Logqwestは、大規模言語モデル（LLM）を活用した放置型テキストゲームです。このリポジトリは、Logqwestのゲームコンテンツ（冒険シナリオ、エリア情報、ログデータなど）をLLMによって自動生成するツールを提供します。GeminiとGroqのLLMに対応し、StreamlitによるGUIを通じて、生成されたコンテンツの閲覧、管理、編集が可能です。

## 特徴

- **自動コンテンツ生成**: LLMを活用し、エリア、冒険、ログ、位置情報などのゲームコンテンツを自動生成します。
- **LLMの選択**: GeminiとGroqのLLMをサポートし、コマンドライン引数で簡単に切り替え可能です。
- **GUI**: Streamlitによる直感的で使いやすいGUIを提供し、生成されたコンテンツの確認や管理を容易にします。
- **カスタマイズ**: テンプレートや設定ファイルを編集することで、生成されるコンテンツのスタイルや内容をカスタマイズできます。
- **データ管理**: 生成されたデータはCSVファイルとして保存され、容易にアクセスや編集が可能です。
- **ゲーム体験**: 生成されたデータを利用して、簡単なゲームプレイを体験できます。

## 構成

```
src/
├── core/           # LLMクライアント、コンテンツ生成、検証の抽象化とインターフェース
├── generators/     # 各種コンテンツ生成モジュール（エリア、冒険、ログ、位置情報）
├── checkers/      # 生成されたコンテンツの検証モジュール
├── utils/         # ユーティリティ関数とヘルパー
├── ui/            # Streamlitインターフェースコンポーネント
├── generate.py     # コマンドラインからのコンテンツ生成スクリプト
├── app.py          # 生成されたデータを利用してゲームを体験
└── viewer.py       # 生成されたコンテンツの確認や管理を行うGUI
```

## 必要な環境

- Python 3.9+
- Gemini APIキー または Groq APIキー

## セットアップ

1. 依存関係のインストール:

   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

2. APIキーの設定:

   Gemini APIキーまたはGroq APIキーを環境変数に設定します。

   ```bash
   export GEMINI_API_KEY=your_gemini_api_key
   export GROQ_API_KEY=your_groq_api_key
   ```

## 使い方

### Webインターフェース

- `app.py`: 生成されたデータを利用してゲームを体験できます。

   ```bash
   streamlit run src/app.py
   ```

- `viewer.py`: 生成されたコンテンツの確認や管理を行うGUIを提供します。

   ```bash
   streamlit run src/viewer.py
   ```

### コマンドライン

コマンドラインからコンテンツを生成します:

```bash
python src/generate.py area              # 新しいエリアを生成
python src/generate.py adventure        # 新しい冒険を生成
python src/generate.py log             # 冒険ログを生成
python src/generate.py location        # 位置情報を生成
```

## 開発

- `--debug` フラグでデバッグモードを有効にします。
- `--client [gemini|groq]` でLLMプロバイダを選択します。
- `--model model_name` でモデルを指定します。
