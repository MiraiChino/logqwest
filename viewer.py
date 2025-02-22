import streamlit as st
import pandas as pd
from urllib.parse import urlencode
from pathlib import Path
from typing import Optional, List

from common import DATA_DIR, get_area_csv_path, get_adventure_path, get_check_results_csv_path, load_csv, delete_adventures
from config import LOGCHECK_HEADERS

# --------------------------------------------------
# 設定
# --------------------------------------------------
AREAS_CSV_FILENAME = "areas.csv"
ADVENTURE_DETAIL_LINE_THRESHOLD = 160  # 冒険詳細ファイルの完了行数閾値
CHECK_MARK = "✅"
SUCCESS_EMOJI = "❗"

# --------------------------------------------------
# ヘルパー関数（データ処理）
# --------------------------------------------------
@st.cache_data
def cached_load_csv(csv_path: Path) -> Optional[pd.DataFrame]:
    """CSVファイルを読み込む。キャッシュを利用。"""
    return load_csv(csv_path)

def save_csv(df: pd.DataFrame, csv_path: Path):
    """CSVファイルを保存する。"""
    try:
        df.to_csv(csv_path, encoding="utf-8", index=False)
    except Exception as e:
        st.error(f"CSVファイルの保存に失敗しました: {csv_path} - {e}")

def filter_dataframe(df: pd.DataFrame, keyword: str, column_name: str) -> pd.DataFrame:
    """データフレームを指定されたキーワードでフィルタリングする。"""
    if not keyword:
        return df
    return df[df[column_name].str.contains(keyword, case=False, na=False)].copy()

# --------------------------------------------------
# チェック処理関数
# --------------------------------------------------
def is_adventure_complete(area: str, adventure_name: str) -> bool:
    """冒険詳細ファイルが存在し、内容が指定行数以上の場合にTrueを返す。"""
    adventure_path = get_adventure_path(area, adventure_name)
    if not adventure_path.exists():
        return False
    try:
        with open(adventure_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return len(lines) >= ADVENTURE_DETAIL_LINE_THRESHOLD
    except Exception:
        return False

def is_area_complete(area: str) -> bool:
    """
    エリア内の全ての冒険が完了し、かつチェック結果CSVの行数も一致するか判定する。
    完了とは、冒険詳細ファイルが存在し、内容が指定行数以上であること。
    """
    area_csv_path = get_area_csv_path(area)
    df_area = cached_load_csv(area_csv_path)
    check_results_csv_path = get_check_results_csv_path(area)
    df_check_results = cached_load_csv(check_results_csv_path)

    if (df_area is None or "冒険名" not in df_area.columns or df_area.empty):
        return False

    total_adventures = len(df_area)
    completed_adventures_count = sum(1 for adv in df_area["冒険名"] if is_adventure_complete(area, adv))
    checked_adventures_count = len(df_check_results) if df_check_results is not None else 0 # チェック結果CSVがない場合は0

    return total_adventures == completed_adventures_count == checked_adventures_count

def is_area_all_checked(area: str) -> bool:
    """
    エリアの check_results_csv のチェック内容が全て✅で始まっているか確認する。
    冒険の完了状態やチェック結果CSVの行数は見ない。
    """
    check_results_csv_path = get_check_results_csv_path(area)
    df_check_results = cached_load_csv(check_results_csv_path)

    if df_check_results is None or df_check_results.empty:
        return False

    check_columns = LOGCHECK_HEADERS[2:-1] # 'ログ', '成否' 列をチェック
    for _, row in df_check_results.iterrows():
        for col in check_columns:
            if not isinstance(row[col], str) or not row[col].startswith(CHECK_MARK):
                return False

    return True # 全ての項目が✅で始まっていればTrueを返す

# --------------------------------------------------
# ラベル生成関数
# --------------------------------------------------
def generate_area_label(area: str) -> str:
    """エリアの状態に基づいたラベルを生成する。"""
    if is_area_complete(area):
        if is_area_all_checked(area):
            return f"{CHECK_MARK}{area}"
        else:
            return f"{SUCCESS_EMOJI}{area}"
    else:
        return area

# --------------------------------------------------
# 表示系ヘルパー関数
# --------------------------------------------------
def render_dataframe_as_html(df: pd.DataFrame) -> str:
    """DataFrameをHTMLテーブルに変換する。"""
    return df.style.hide(axis="index").set_properties(**{'vertical-align': 'top'}).to_html(escape=False, index=False)

def display_dataframe_with_checkbox(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrameに行選択チェックボックスを表示し、選択された行を返す。"""
    st.markdown("### データテーブル")
    header_cols = st.columns([0.5] + [1] * len(df.columns))
    with header_cols[0]:
        st.write("選択")
    for col, header in zip(header_cols[1:], df.columns):
        with col:
            st.write(header)

    selected_indices = []
    for idx, row in df.iterrows():
        row_cols = st.columns([0.5] + [1] * len(row))
        with row_cols[0]:
            if st.checkbox("選択", key=f"checkbox_{idx}", label_visibility="collapsed"):
                selected_indices.append(idx)
        for value, col in zip(row, row_cols[1:]):
            with col:
                st.write(value)
    return df.loc[selected_indices] if selected_indices else pd.DataFrame() # 選択行がない場合、空のDataFrameを返す

def display_progress_bar(ratio: float, label: str):
    """プログレスバーとラベルを表示する。完了時には色を変更。"""
    if ratio == 1.0:
        st.markdown(
            """
            <style>
            .stProgress > div > div > div > div {
                background-color: #03C03C;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
    st.write(label)
    st.progress(ratio)

# --------------------------------------------------
# ナビゲーション関数
# --------------------------------------------------
def update_query_params(area: str = "", adventure: str = ""):
    """クエリパラメータを更新する。"""
    params = {}
    if area:
        params["area"] = area
    if adventure:
        params["adv"] = adventure
    st.query_params.update(params)

def set_current_area(area: str):
    """セッションステートとクエリパラメータを更新し、現在のエリアを設定する。"""
    st.session_state.current_area = area
    update_query_params(area=area)

def sidebar_navigation(area_names: List[str]):
    """サイドバーナビゲーションを構築する。"""
    with st.sidebar:
        if st.button("🔄 データ更新"):
            st.cache_data.clear()
            st.rerun()

        st.caption('<a href="?area=エリア一覧" target="_self">📖全エリア一覧</a>', unsafe_allow_html=True)

        filter_keyword = st.text_input("🔎 エリア名でフィルタ", "", placeholder="エリア名で検索", label_visibility="collapsed")
        filtered_area_names = filter_dataframe(
            pd.DataFrame({"エリア名": area_names}), filter_keyword, "エリア名"
        )["エリア名"].tolist()
        sorted_area_names = sorted(filtered_area_names)

        for area in sorted_area_names:
            area_csv_path = get_area_csv_path(area)
            label = generate_area_label(area)
            if area_csv_path.exists():
                st.caption(f'<a href="?area={area}" target="_self">{label}</a>', unsafe_allow_html=True)
            else:
                st.caption(area)

# --------------------------------------------------
# ページ表示関数
# --------------------------------------------------
def display_area_list_page(df_areas: pd.DataFrame):
    """「エリア一覧」ページを表示する。"""
    st.title("📖全エリア一覧")

    total_areas = len(df_areas)
    completed_areas_count = sum(1 for area in df_areas["エリア名"] if is_area_complete(area))
    ratio = completed_areas_count / total_areas if total_areas > 0 else 0
    display_progress_bar(ratio, f"エリアデータ存在数: {completed_areas_count} / {total_areas}")

    df_areas_sorted = df_areas.sort_values(by="エリア名").reset_index(drop=True)
    filter_keyword = st.text_input("エリア名フィルタ", "", placeholder="エリア名でフィルタ", label_visibility="collapsed")
    df_areas_filtered = filter_dataframe(df_areas_sorted, filter_keyword, "エリア名")

    df_clickable = df_areas_filtered.copy()
    df_clickable["エリア名"] = df_clickable["エリア名"].apply(
        lambda area: (f'<a href="?area={area}" target="_self">{generate_area_label(area)}</a>')
        if get_area_csv_path(area).exists() else area
    )
    st.markdown(render_dataframe_as_html(df_clickable), unsafe_allow_html=True)


def display_adventure_detail_page(selected_area: str, selected_adventure: str):
    """冒険詳細ページを表示する。"""
    st.title(f"{selected_area} - {selected_adventure} 詳細")

    area_csv_path = get_area_csv_path(selected_area)
    df_area = cached_load_csv(area_csv_path)

    if df_area is not None:
        adventure_row = df_area[df_area["冒険名"] == selected_adventure]
        if not adventure_row.empty:
            st.markdown("**冒険情報**")
            st.markdown(render_dataframe_as_html(adventure_row), unsafe_allow_html=True)
        else:
            st.write("該当の冒険情報は見つかりません。")
    else:
        st.write("エリアのデータが存在しません。")

    st.markdown("**冒険詳細 (テキストファイル)**")
    adventure_file_path = get_adventure_path(selected_area, selected_adventure)
    if adventure_file_path.exists():
        try:
            with open(adventure_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            numbered_content = "\n".join(f"{i+1}. {line}" for i, line in enumerate(content.splitlines()))
            st.text(numbered_content)
        except Exception as e:
            st.error(f"冒険詳細ファイルの読み込みに失敗しました: {adventure_file_path} - {e}")

    else:
        st.write("該当の冒険データが存在しません。")

    if st.button("戻る"):
        set_current_area(selected_area)
        st.rerun()


def display_area_page(selected_area: str, df_areas: pd.DataFrame):
    """エリアページを表示する。"""
    st.title(f"{selected_area} のデータ")

    area_csv_path = get_area_csv_path(selected_area)
    df_adventures_original = cached_load_csv(area_csv_path)

    if df_adventures_original is not None and "冒険名" in df_adventures_original.columns and "結果" in df_adventures_original.columns:
        total_adventures = len(df_adventures_original)
        completed_adventures_total = sum(1 for adv in df_adventures_original["冒険名"] if is_adventure_complete(selected_area, adv))
        ratio = completed_adventures_total / total_adventures if total_adventures > 0 else 0
        display_progress_bar(ratio, f"冒険データ存在数: {completed_adventures_total} / {total_adventures}")

        area_info = df_areas[df_areas["エリア名"] == selected_area]
        if not area_info.empty:
            with st.expander("エリア情報", expanded=True):
                st.markdown(render_dataframe_as_html(area_info), unsafe_allow_html=True)
        else:
            st.write("エリア情報が存在しません。")

        adventure_results = ["失敗", "成功", "大成功"]
        for result in adventure_results:
            df_result = df_adventures_original[df_adventures_original["結果"] == result]
            completed_adventures_result = sum(1 for adv in df_result["冒険名"] if is_adventure_complete(selected_area, adv))
            with st.expander(f"冒険結果: {result} ({completed_adventures_result}/{len(df_result)})"):
                if not df_result.empty:
                    df_clickable_adv = df_result.copy()
                    df_clickable_adv["冒険名"] = df_clickable_adv["冒険名"].apply(
                        lambda adv: f'<a href="?area={selected_area}&adv={adv}" target="_self">{CHECK_MARK + adv if is_adventure_complete(selected_area, adv) else adv}</a>'
                    )
                    st.markdown(render_dataframe_as_html(df_clickable_adv), unsafe_allow_html=True)
                else:
                    st.write("該当する冒険はありません。")

        display_check_results_section(selected_area, len(df_adventures_original))

    elif df_adventures_original is not None:
        st.markdown(render_dataframe_as_html(df_adventures_original), unsafe_allow_html=True)
    else:
        st.write("エリアのデータが見つかりません。")


def display_check_results_section(area: str, total_results_count: int):
    """チェック結果セクションを表示し、削除機能を提供する。"""
    check_results_csv_path = get_check_results_csv_path(area)
    df_check_results_original = cached_load_csv(check_results_csv_path)

    if df_check_results_original is not None:
        with st.expander(f"チェック結果: ({len(df_check_results_original)}/{total_results_count})", expanded=True):
            selected_df = display_dataframe_with_checkbox(df_check_results_original)
            if selected_df.empty:
                st.write("ℹ️ 削除するには行を選択してください。")
            else:
                if st.button("🔥 選択行を削除", key=f"delete_check_results_{area}"):
                    adventures_to_delete = selected_df["冒険名"].tolist()
                    delete_messages = delete_adventures(area, adventures_to_delete)
                    for message in delete_messages:
                        st.write(message)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.write(selected_df["冒険名"])
    else:
        st.write(f"チェック結果ファイルが見つかりません: {check_results_csv_path}")


# --------------------------------------------------
# メイン処理
# --------------------------------------------------
def main():
    st.set_page_config(
        page_title="Data Viewer",
        page_icon="📖",
        layout="wide",
    )

    if "current_area" not in st.session_state:
        st.session_state.current_area = "エリア一覧"

    query_params = st.query_params
    selected_area = query_params.get("area", st.session_state.current_area)
    selected_adventure = query_params.get("adv", "")
    st.session_state.current_area = selected_area # クエリパラメータでエリアが指定されていなくても、セッションステートを更新

    df_areas = cached_load_csv(DATA_DIR / AREAS_CSV_FILENAME) # areas.csv は DATA_DIR 直下に配置
    if df_areas is None:
        st.error("エリア一覧データが見つかりません。")
        return
    area_names = df_areas["エリア名"].tolist()

    sidebar_navigation(area_names)

    if selected_area == "エリア一覧":
        display_area_list_page(df_areas)
    elif selected_adventure:
        display_adventure_detail_page(selected_area, selected_adventure)
    else:
        display_area_page(selected_area, df_areas)


if __name__ == "__main__":
    main()