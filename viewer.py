import streamlit as st
import pandas as pd
from urllib.parse import urlencode

from common import DATA_DIR, get_area_csv_path, get_adventure_path, get_check_results_csv_path, load_csv, delete_adventures

# --------------------------------------------------
# キャッシュ関数
# --------------------------------------------------
@st.cache_data
def cached_load_csv(csv_path):
    """
    load_csv 関数をキャッシュする。
    """
    return load_csv(csv_path)

# --------------------------------------------------
# チェック処理・クエリパラメータ更新関数
# --------------------------------------------------
def is_adventure_complete(area: str, adv: str) -> bool:
    """
    冒険詳細ファイルが存在し、その中身が160行以上ある場合にTrueを返す。
    """
    path = get_adventure_path(area, adv)
    if not path.exists():
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return len(lines) >= 160
    except Exception:
        return False

def is_area_complete(area: str) -> bool:
    """
    エリアCSVファイルが存在し、かつそのCSV内のすべての冒険詳細ファイルが
    存在し内容が160行以上の場合に True を返す。
    存在しない、または冒険データが不足している場合は False を返す。
    """
    csv_path = get_area_csv_path(area)
    if not csv_path.exists():
        return False
    check_csv_path = get_check_results_csv_path(area)
    if not check_csv_path.exists():
        return False
    df_area = cached_load_csv(csv_path)
    df_checkarea = cached_load_csv(check_csv_path)
    if df_area is None or "冒険名" not in df_area.columns:
        return False
    if df_checkarea is None or "冒険名" not in df_area.columns:
        return False
    total_adv = len(df_area)
    if total_adv == 0:
        return False
    complete_adv = sum(1 for adv in df_area["冒険名"] if is_adventure_complete(area, adv))
    check_adv = sum(1 for adv in df_checkarea["冒険名"])
    return total_adv == complete_adv == check_adv

def update_query_params(area: str, adv: str = ""):
    """
    クエリパラメータにキー "area" と "adv" をセットする。
    これによりURLを更新する。
    """
    st.query_params["area"] = area
    st.query_params["adv"] = adv

def set_current_area(area: str):
    """
    セッションステートの現在のエリア（ページ）を設定し、クエリパラメータも更新する。
    """
    st.session_state.current_area = area
    update_query_params(area, adv="")

# --------------------------------------------------
# 表示系ヘルパー関数
# --------------------------------------------------
def render_df(df: pd.DataFrame) -> str:
    """
    DataFrameをHTMLテーブルに変換する。
    すべてのセルの縦位置を上揃えにするスタイルを適用する。
    """
    return df.style.hide().set_properties(**{'vertical-align': 'top'}).to_html(escape=False, index=False)

def render_df_with_checkbox(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrameの各行の先頭にStreamlitのチェックボックスを追加して表示し、
    選択された行のみを返す関数です。
    """
    st.session_state.selected_indices = []
    
    st.markdown("### データテーブル")
    # ヘッダーを表示（チェックボックス列は「選択」）
    header_cols = st.columns([0.5] + [1] * len(df.columns))
    with header_cols[0]:
        st.write("選択")
    for col, header in zip(header_cols[1:], df.columns):
        with col:
            st.write(header)
    
    # 各行を表示（チェックボックスとデータ列）
    for idx, row in df.iterrows():
        row_cols = st.columns([0.5] + [1] * len(row))
        with row_cols[0]:
            # 各行に対してチェックボックスを表示。チェックされたらその行番号を記録。
            if st.checkbox("check", key=f"checkbox_{idx}", label_visibility="collapsed"):
                st.session_state.selected_indices.append(idx)
        for value, col in zip(row, row_cols[1:]):
            with col:
                st.write(value)
    
    # 選択された行のみを抽出して返す
    return df.loc[st.session_state.selected_indices]

def show_progress(ratio: float, label: str):
    """
    プログレスバーとそのラベルを表示する。
    ratioが 1.0（100%）の場合は、プログレスバーの色を緑色に変更する。
    """
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

def sidebar_navigation(area_names: list):
    """
    サイドバーにナビゲーションを構築する。
    「エリア一覧」と各エリアのキャプションリンクを表示。
    エリア名は名前順にソートし、フィルタ機能も追加。
    """
    with st.sidebar:
        query_params = {"area": "エリア一覧"}
        link_url = f"?{urlencode(query_params)}"
        if st.button("🔄 更新"):
            st.cache_data.clear()
            st.rerun() # rerunして最新データを読み込み直す
        st.caption(
            f'<a href="{link_url}" target="_self">📖全エリア一覧</a>',
            unsafe_allow_html=True,
        )

        # **エリア名フィルタ**
        filter_keyword = st.text_input("🔎", "", placeholder="🔎", label_visibility="collapsed")
        filtered_area_names = filter_dataframe(
            pd.DataFrame({"エリア名": area_names}), filter_keyword, "エリア名"
        )["エリア名"].tolist()

        # **エリア名を名前順にソート**
        sorted_area_names = sorted(filtered_area_names)

        for area in sorted_area_names: # ソート済みのエリア名を使用
            csv_path = get_area_csv_path(area)
            if csv_path.exists():
                label = f"✅{area}" if is_area_complete(area) else area
                query_params = {"area": area}
                link_url = f"?{urlencode(query_params)}"
                st.caption(
                    f'<a href="{link_url}" target="_self">{label}</a>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption(area) # CSVが存在しない場合はリンクなしで表示

# --------------------------------------------------
# データフレーム操作関数
# --------------------------------------------------
def filter_dataframe(df: pd.DataFrame, filter_keyword: str, column_name: str) -> pd.DataFrame:
    """
    データフレームを指定されたキーワードでフィルタリングする。
    """
    if not filter_keyword:
        return df
    return df[df[column_name].str.contains(filter_keyword, case=False, na=False)].copy()

def paginate_dataframe(df: pd.DataFrame, items_per_page: int, page_num: int) -> pd.DataFrame: # display_area_pageでページネーションを廃止したので削除
    """
    データフレームをページネーションする。
    """
    start_index = (page_num - 1) * items_per_page
    end_index = start_index + items_per_page
    return df.iloc[start_index:end_index].copy()

# --------------------------------------------------
# ページ表示用関数
# --------------------------------------------------
def display_area_list(df_areas: pd.DataFrame):
    """
    「エリア一覧」ページを表示する。
    各エリア名は、CSVが存在する場合はリンク化され、すべての冒険詳細ファイルが揃っている場合は先頭に✅が付く。
    また、ページ上部にエリアデータの存在率をプログレスバーで表示する。
    ページネーション機能とフィルタ機能を追加。
    """
    st.title("📖全エリア一覧")

    total_areas = len(df_areas)
    complete_areas = sum(1 for area in df_areas["エリア名"] if is_area_complete(area))
    ratio = complete_areas / total_areas if total_areas > 0 else 0
    show_progress(ratio, f"エリアデータ存在数: {complete_areas} / {total_areas}")
    df_areas_sorted = df_areas.sort_values(by="エリア名").reset_index(drop=True)

    # **フィルタリング**
    filter_keyword = st.text_input("エリア名でフィルタ (部分一致)", "", placeholder="🔎", label_visibility="collapsed")
    df_areas_filtered = filter_dataframe(df_areas_sorted, filter_keyword, "エリア名")

    # **ページネーション**
    items_per_page = 10
    if "area_list_page_num" not in st.session_state:
        st.session_state.area_list_page_num = 1
    page_num = st.session_state.area_list_page_num
    df_paged_areas = paginate_dataframe(df_areas_filtered, items_per_page, page_num)
    num_pages = (len(df_areas_filtered) + items_per_page - 1) // items_per_page

    df_clickable = df_paged_areas.copy()
    df_clickable["エリア名"] = df_clickable["エリア名"].apply(
        lambda x: (f'<a href="?area={x}" target="_self">{"✅" + x if is_area_complete(x) else x}</a>')
        if get_area_csv_path(x).exists() else x
    )
    st.markdown(render_df(df_clickable), unsafe_allow_html=True)

    # ページネーション UI
    col_prev, col_page_num, col_next = st.columns([1, 1, 1])
    with col_prev:
        if page_num > 1:
            if st.button("前へ", key="area_list_prev"):
                st.session_state.area_list_page_num -= 1
                st.rerun()
        else:
            st.button("前へ", disabled=True)
    with col_page_num:
        st.write(f"ページ {page_num} / {num_pages}")
    with col_next:
        if page_num < num_pages:
            if st.button("次へ", key="area_list_next"):
                st.session_state.area_list_page_num += 1
                st.rerun()
        else:
            st.button("次へ", disabled=True)

def display_adventure_detail(selected_area: str, selected_adv: str):
    """
    冒険詳細ページを表示する。
    エリアCSVから該当の冒険情報行を抽出し、
    対応するテキストファイルの内容も表示する。
    「戻る」ボタンでエリアページへ遷移する。
    """
    st.title(f"{selected_area} - {selected_adv} 詳細")

    csv_path = get_area_csv_path(selected_area)
    df_area = cached_load_csv(csv_path)
    if df_area is not None:
        adv_row = df_area[df_area["冒険名"] == selected_adv]
        if not adv_row.empty:
            st.markdown("**冒険情報**")
            st.markdown(render_df(adv_row), unsafe_allow_html=True)
        else:
            st.write("該当の冒険情報は見つかりません。")
    else:
        st.write("エリアのデータが存在しません。")

    st.markdown("**冒険詳細 (テキストファイル)**")
    adventure_file_path = get_adventure_path(selected_area, selected_adv)
    if adventure_file_path.exists():
        with open(adventure_file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 行ごとに分割し、行番号を付与
        numbered_content = "\n".join(f"{i+1}. {line}" for i, line in enumerate(content.splitlines()))
        st.text(numbered_content)
    else:
        st.write("該当の冒険データが存在しません。")

    if st.button("戻る"):
        set_current_area(selected_area)
        st.rerun()

def display_area_page(selected_area: str, df_areas: pd.DataFrame):
    """
    各エリアページを表示する。
    ページ冒頭にエリア一覧（areas.csv）の対象エリア情報を表示し、
    その下に該当エリア内の冒険一覧を「失敗」「成功」「大成功」のExpanderで表示する。
    Expanderラベルに冒険結果ごとの完了数を表示。
    ページネーションは廃止。
    """
    st.title(f"{selected_area} のデータ")

    # 冒険一覧の表示
    csv_path = get_area_csv_path(selected_area)
    df_adv_original = cached_load_csv(csv_path)
    if df_adv_original is not None and "冒険名" in df_adv_original.columns and "結果" in df_adv_original.columns:
        total_adv = len(df_adv_original)
        complete_adv_total = sum(1 for adv in df_adv_original["冒険名"] if is_adventure_complete(selected_area, adv)) # 全冒険の完了数
        ratio = complete_adv_total / total_adv if total_adv > 0 else 0
        show_progress(ratio, f"冒険データ存在数: {complete_adv_total} / {total_adv}") # 全体のプログレスバー表示

        # エリア情報の表示
        area_info = df_areas[df_areas["エリア名"] == selected_area]
        if not area_info.empty:
            with st.expander("エリア情報", expanded=True):
                st.markdown(render_df(area_info), unsafe_allow_html=True)
        else:
            st.write("エリア情報が存在しません。")

        # 冒険結果の種類を取得
        results = ["失敗", "成功", "大成功"]

        for result in results:
            df_result = df_adv_original[df_adv_original["結果"] == result] # 結果でフィルタリング
            complete_adv_result = sum(1 for adv in df_result["冒険名"] if is_adventure_complete(selected_area, adv)) # 結果ごとの完了数
            with st.expander(f"冒険結果: {result} ({complete_adv_result}/{len(df_result)})"):
                if not df_result.empty: # 結果に該当するデータが存在する場合のみ表示
                    df_clickable_adv = df_result.copy()
                    df_clickable_adv["冒険名"] = df_clickable_adv["冒険名"].apply(
                        lambda adv: f'<a href="?area={selected_area}&adv={adv}" target="_self">{"✅" + adv if is_adventure_complete(selected_area, adv) else adv}</a>'
                    )
                    st.markdown(render_df(df_clickable_adv), unsafe_allow_html=True)
                else:
                    st.write("該当する冒険はありません。") # データがない場合のメッセージ

        display_check_results(selected_area, len(df_adv_original))

    elif df_adv_original is not None:
        st.markdown(render_df(df_adv_original), unsafe_allow_html=True)
    else:
        st.write("エリアのデータが見つかりません。")

def display_check_results(area: str, len_results: int):
    """
    指定されたエリアのチェック結果CSVファイルを読み込み、
    評価項目とその理由をStreamlitでDataFrameとして表示する。
    行選択と削除機能を追加。
    """
    check_results_csv_path = get_check_results_csv_path(area)
    df_check_results_original = cached_load_csv(check_results_csv_path)

    if df_check_results_original is not None:
        with st.expander(f"チェック結果: ({len(df_check_results_original)}/{len_results})", expanded=True):

            # HTMLテーブル表示 
            selected_df = render_df_with_checkbox(df_check_results_original)
            if selected_df.empty:
                st.write("ℹ️ 削除するには行を選択してください。")
            else:
                if st.button("🔥 選択行を削除", key=f"delete_check_results_{area}"):
                    advs_to_delete = selected_df["冒険名"].values.tolist()
                    st.write(selected_df["冒険名"])
                    for text in delete_adventures(area, advs_to_delete):
                        st.write(text)

                    st.cache_data.clear()
                    st.rerun() # rerunして最新データを読み込み直す
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

    # セッションステートの初期設定（初回アクセス時は「エリア一覧」に設定）
    if "current_area" not in st.session_state:
        st.session_state.current_area = "エリア一覧"

    # クエリパラメータから現在のエリアを取得（存在する場合）
    query_params = st.query_params
    if "area" in query_params and query_params["area"]:
        st.session_state.current_area = query_params["area"]

    # エリア一覧CSVの読み込み
    df_areas = cached_load_csv(DATA_DIR / "areas.csv")
    if df_areas is None:
        st.error("エリア一覧データが見つかりません。")
        return
    area_names = df_areas["エリア名"].tolist()

    sidebar_navigation(area_names)

    current_area = st.session_state.current_area
    # ページの表示分岐
    if current_area == "エリア一覧":
        display_area_list(df_areas)
    else:
        if "adv" in query_params and query_params["adv"]:
            selected_adv = query_params["adv"]
            display_adventure_detail(current_area, selected_adv)
        else:
            display_area_page(current_area, df_areas)

if __name__ == "__main__":
    main()