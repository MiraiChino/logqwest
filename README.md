# Logqwest

## ローカル起動手順（E2E最小）

### Backend
1) 依存インストール
```
cd backend
pip install -r requirements.txt
```
2) 起動
```
uvicorn app.main:app --reload
```

### Flutter (Web)
1) 依存取得
```
cd app_flutter
flutter pub get
```
2) 実行（Chrome）
```
flutter run -d chrome
```

### 動作確認チェック
- ホームで所持金(WEN)が表示される
- 「冒険者を雇う」押下でSSEログが流れる
- 冒険結果が表示され、所持金が更新される
- 詳細画面でログ/マップのプレースホルダが表示される

## 仕様
- API: docs/api.md
- アプリ構成: app_flutter/docs/architecture.md
