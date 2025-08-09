# Logqwest - LLM駆動型 放置型テキストゲーム コンテンツ自動生成ツール

Logqwestは、大規模言語モデル（LLM）を活用した放置型テキストゲームです。このリポジトリは、Logqwestのゲームコンテンツ（冒険シナリオ、エリア情報、ログデータなど）をLLMによって自動生成するツールを提供します。StreamlitによるGUIを通じて、生成されたコンテンツの閲覧、管理、編集が可能です。

## 特徴

- **自動コンテンツ生成**: LLMを活用し、エリア、冒険、ログ、位置情報などのゲームコンテンツを自動生成します。
- **LLMの選択**: GeminiとOpenRouterのLLMをサポートし、コマンドライン引数で簡単に切り替え可能です。
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
- Gemini APIキー または OpenRouter APIキー

## セットアップ

1. 依存関係のインストール:

   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

2. APIキーの設定:

   Gemini APIキーまたはOpenRouter APIキーを環境変数に設定します。

   ```bash
   export GEMINI_API_KEY=your_gemini_api_key
   export OPENROUTER_API_KEY=your_openrouter_api_key
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

## アーキテクチャ

### 全体構造
次の5つの主要なレイヤーで構成されています：

1. **CLIエントリーポイント** (`src/generate.py`)
   - コマンドライン引数の解析
   - 設定読み込みとロギング初期化
   - LLMクライアント生成とコマンドハンドラ設定

2. **コマンドハンドラ** (`src/utils/commands.py`)
   - コンテンツ生成と検証の調整
   - リトライ処理による堅牢なエラーハンドリング
   - ファイル操作・進捗管理・CSV操作を各ユーティリティに委譲

3. **コンテンツ処理レイヤー**
   - **ジェネレータ群** (`src/generators/`)
     - エリア/冒険/ログ/位置情報のLLM生成処理
   - **チェッカー群** (`src/checkers/`)
     - 生成されたコンテンツの品質検証機能

4. **ユーティリティレイヤー** (`src/utils/`)
   - 設定管理：パスやテンプレートの構成情報を管理
   - データ処理：CSVファイルの読み書きとソート機能
   - ログ処理：GENERATE/SUCCESS等のカスタムログレベル
   - 進捗管理：ファイル構成から各コンテンツの完了率を算出
   - ファイル操作：データフォルダ/チェック結果/user_data/history.jsonのCRUD操作
   - リトライ処理：指数バックオフとAPIレート制限の特別処理

5. **Streamlit UI** (`src/app.py`と`src/ui/`)
   - エントリーポイント：app.pyでクエリパラメータ(area/adv等)を解析
   - UI制御：UIControllerでビューのルーティングとナビゲーション
   - ビュー構成：エリア一覧/詳細と冒険詳細を各ビューで表示
   - サイドバー：history.jsonデータで冒険履歴へのリンクナビゲーション

### データフロー
1. CLIまたはUIからコマンドハンドラに処理要求
2. ジェネレータがLLMにプロンプト送信しコンテンツ生成
3. チェッカーが生成内容の品質検証とチェック結果保存
4. FileHandler経由でCSV/TXTファイルにデータ永続化
5. ProgressTrackerでファイル構成を解析して進捗管理
6. Loggerでプロセス状況をログ出力
7. UIではクエリパラメータに基づき必要なデータを読み込み表示

### エラーハンドリング
RetryDecoratorで全ジェネレータ/チェッカー処理をラップし、RateLimitExeededやRetryLimitExeeded等の例外発生時はLoggerで状況を記録。さらに自動再試行または適切な待機処理を実施することで堅牢な動作を保証しています。
- `--model model_name` でモデルを指定します。