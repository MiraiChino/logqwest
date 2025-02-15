from pathlib import Path
import streamlit as st
import pandas as pd

# --------------------------------------------------
# 定数＆ユーティリティ関数
# --------------------------------------------------
DATA_DIR = Path("data")

def get_area_csv_path(area: str) -> Path:
    """指定されたエリア名のCSVファイルパスを返す。"""
    return DATA_DIR / f"{area}.csv"

def get_adventure_path(area: str, adv: str) -> Path:
    """指定されたエリア内の冒険テキストファイルのパスを返す。"""
    return DATA_DIR / area / f"{adv}.txt"

def load_csv(csv_path: Path) -> pd.DataFrame:
    """
    CSVファイルを読み込みDataFrameを返す。  
    ファイルが存在しない場合は None を返す。
    """
    return pd.read_csv(csv_path) if csv_path.exists() else None

def render_df(df: pd.DataFrame) -> str:
    """
    DataFrameをHTMLテーブルに変換する。  
    すべてのセルの縦位置を上揃えにするスタイルを適用する。
    """
    return df.style.set_properties(**{'vertical-align': 'top'}).to_html(escape=False, index=False)

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
    df_area = load_csv(csv_path)
    if df_area is None or "冒険名" not in df_area.columns:
        return False
    total_adv = len(df_area)
    if total_adv == 0:
        return False
    complete_adv = sum(1 for adv in df_area["冒険名"] if is_adventure_complete(area, adv))
    return total_adv == complete_adv

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
    「エリア一覧」と各エリアのボタンを表示し、  
    ①エリアCSVが存在する場合はボタン化、  
    ②全冒険詳細ファイルが揃っている（is_area_complete==True）ならラベルの先頭に✅を付与する。
    """
    st.sidebar.title("ナビゲーション")

    st.sidebar.subheader("全体ページ")
    if st.sidebar.button("エリア一覧"):
        set_current_area("エリア一覧")

    st.sidebar.subheader("各エリア")
    for area in area_names:
        csv_path = get_area_csv_path(area)
        if csv_path.exists():
            label = f"✅{area}" if is_area_complete(area) else area
            if st.sidebar.button(label):
                set_current_area(area)
        else:
            st.sidebar.write(area)

# --------------------------------------------------
# ページ表示用関数
# --------------------------------------------------
def display_area_list(df_areas: pd.DataFrame):
    """
    「エリア一覧」ページを表示する。  
    各エリア名は、CSVが存在する場合はリンク化され、すべての冒険詳細ファイルが揃っている場合は先頭に✅が付く。  
    また、ページ上部にエリアデータの存在率をプログレスバーで表示する。
    """
    st.title("エリア一覧")

    total_areas = len(df_areas)
    complete_areas = sum(1 for area in df_areas["エリア名"] if is_area_complete(area))
    ratio = complete_areas / total_areas if total_areas > 0 else 0
    show_progress(ratio, f"エリアデータ存在数: {complete_areas} / {total_areas}")

    df_clickable = df_areas.copy()
    df_clickable["エリア名"] = df_clickable["エリア名"].apply(
        lambda x: (f'<a href="?area={x}" target="_self">{"✅" + x if is_area_complete(x) else x}</a>')
        if get_area_csv_path(x).exists() else x
    )
    st.markdown(render_df(df_clickable), unsafe_allow_html=True)

def display_adventure_detail(selected_area: str, selected_adv: str):
    """
    冒険詳細ページを表示する。  
    エリアCSVから該当の冒険情報行を抽出し、  
    対応するテキストファイルの内容も表示する。  
    「戻る」ボタンでエリアページへ遷移する。
    """
    st.title(f"{selected_area} - {selected_adv} 詳細")

    csv_path = get_area_csv_path(selected_area)
    df_area = load_csv(csv_path)
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
    その下に該当エリア内の冒険一覧と、データの存在率を示すプログレスバーを表示する。  
    冒険テキストファイルが存在し、かつ160行以上ある場合はリンクに✅を付与する。
    """
    st.title(f"{selected_area} のデータ")

    # エリア情報の表示
    area_info = df_areas[df_areas["エリア名"] == selected_area]
    if not area_info.empty:
        st.subheader("エリア情報")
        st.markdown(render_df(area_info), unsafe_allow_html=True)
    else:
        st.write("エリア情報が存在しません。")

    # 冒険一覧の表示
    csv_path = get_area_csv_path(selected_area)
    df_adv = load_csv(csv_path)
    if df_adv is not None:
        if "冒険名" in df_adv.columns:
            total_adv = len(df_adv)
            complete_adv = sum(1 for adv in df_adv["冒険名"] if is_adventure_complete(selected_area, adv))
            ratio = complete_adv / total_adv if total_adv > 0 else 0
            show_progress(ratio, f"冒険データ存在数: {complete_adv} / {total_adv}")

            df_clickable_adv = df_adv.copy()
            df_clickable_adv["冒険名"] = df_clickable_adv["冒険名"].apply(
                lambda adv: f'<a href="?area={selected_area}&adv={adv}" target="_self">{"✅" + adv if is_adventure_complete(selected_area, adv) else adv}</a>'
            )
            st.markdown(render_df(df_clickable_adv), unsafe_allow_html=True)
        else:
            st.markdown(render_df(df_adv), unsafe_allow_html=True)
    else:
        st.write("エリアのデータが見つかりません。")

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
    df_areas = load_csv(DATA_DIR / "areas.csv")
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