from pathlib import Path
from typing import List, Dict, Optional
import csv

class CSVHandler:
    def __init__(self):
        self.current_path = None

    def write_headers(self, file_path: Path, headers: List[str]):
        self.current_path = file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def read_rows(self, file_path: Path) -> List[Dict]:
        self.current_path = file_path
        if not file_path.exists():
            return []
            
        with file_path.open('r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            return [row for row in reader]
    
    def read_adventures(self, file_path: Path):
        self.current_path = file_path
        if not file_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        for row in self.read_rows(file_path):
            adventure_name = row["冒険名"]
            prev_adventure = row["前の冒険"]
            next_adventure = row["次の冒険"]
            result = row["結果"]
            chapters = list(row.values())[4:] # 冒険名,前冒険,後冒険,結果を飛ばす
            yield adventure_name, prev_adventure, next_adventure, result, chapters

    def write_row(self, file_path: Path, row: List[str], headers: List[str] = None):
        self.current_path = file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_exists = file_path.exists()
        with file_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if not file_exists and headers:
                writer.writerow(headers)
            writer.writerow(row)

    def sort_by_result(self, file_path: Path):
        self.current_path = file_path
        rows = self.read_rows(file_path)
        sorted_rows = sorted(
            rows,
            key=lambda x: (
                {'失敗': 0, '成功': 1, '大成功': 2}.get(x.get('結果', ''), 3),
                int(x.get('番号', 0))
            )
        )
        self._write_sorted_rows(sorted_rows)

    def _write_sorted_rows(self, rows: List[Dict]) -> None:
        if not rows:
            return
            
        headers = list(rows[0].keys())
        with self.current_path.open('w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    def _write_all_rows(self, file_path: Path, rows: List[Dict], headers: Optional[List[str]] = None) -> None:
        """指定された行リストをCSVファイルに上書きします。ヘッダーも書き込みます。"""
        self.current_path = file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if not headers and rows:
            headers = list(rows[0].keys())
        elif not headers and not rows:
            # ヘッダーもなく、データもない場合はファイルを空にする
            file_path.open('w').close()
            return
        elif not rows:
             # データはなくヘッダーはある場合、ヘッダーのみ書き込む
             self.write_headers(file_path, headers)
             return

        # この時点で headers は必ず存在するはず
        if not headers:
             # 万が一 headers が None のままここに来た場合のフォールバック
             print(f"エラー: ヘッダーが決定できませんでした。ファイル '{file_path}' への書き込みを中止します。")
             return

        try:
            with file_path.open('w', encoding='utf-8', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)
        except Exception as e:
            print(f"ファイル書き込み中にエラーが発生しました ({file_path}): {e}")
            # 必要であればここで例外を再発生させる
            # raise e

    def update_col2_if_col1_equals_value(
        self,
        file_path: Path,
        col1_name: str,
        target_value: str,
        col2_name: str,
        new_value: str
    ):
        """
        CSVファイルを読み込み、指定された列1の値がtarget_valueと一致する場合、
        その行の列2の値をnew_valueに更新して上書き保存します。
        """
        rows = self.read_rows(file_path)
        if not rows:
            # ファイルが空、または読み込みに失敗した場合(read_rowsが[]を返す)
            # この時点ではヘッダーが不明なため、列名チェックはできない
            # 更新対象もないので、処理を終了
            print(f"ファイル '{file_path}' が空か、読み込めませんでした。更新は行われません。")
            return

        # ヘッダーを取得 (rowsが空でないことは保証されている)
        original_headers = list(rows[0].keys())

        # --- 列名の存在チェック ---
        missing_cols = []
        if col1_name not in original_headers:
            missing_cols.append(col1_name)
        if col2_name not in original_headers:
            missing_cols.append(col2_name)

        if missing_cols:
            # --- 指定された列名が存在しない場合は ValueError を raise ---
            raise ValueError(f"指定された列名が見つかりません: {missing_cols}. 利用可能なヘッダー: {original_headers}")

        # --- 行の更新処理 ---
        updated = False
        updated_rows = []
        for i, row in enumerate(rows):
            if isinstance(row, dict):
                current_value_col1 = row.get(col1_name) # getで安全にアクセス
                if current_value_col1 == target_value:
                    row[col2_name] = new_value
                    updated = True
                updated_rows.append(row)
            else:
                # 通常発生しないはずだが念のため
                print(f"警告: 行 {i+1} は予期される辞書形式ではありません: {row}")
                updated_rows.append(row) # スキップせず元の行を追加

        # --- 書き込み処理 ---
        if updated:
            try:
                # _write_all_rows は内部で書き込みエラーをprintするが、
                # 必要ならここで再度 try-except し、例外を上に投げることもできる
                self._write_all_rows(file_path, updated_rows, headers=original_headers)
            except Exception as e:
                # _write_all_rows 内でのエラーをここでキャッチして再raiseするなど
                print(f"ファイル書き込み処理中に予期せぬエラーが発生しました: {e}")
                raise # エラーを呼び出し元に伝える
        else:
            print(f"'{col1_name}' が '{target_value}' である行は見つかりませんでした。ファイル '{file_path}' は変更されていません。")