import locale
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import streamlit as st
import graphviz

from common import get_adventure_path, get_outcome_emoji, load_usage_data
from adventure import run_adventure_streaming, ADVENTURE_COST


# ロケール設定
locale.setlocale(locale.LC_TIME, 'ja_JP.UTF-8')

# Streamlitページ設定
st.set_page_config(
    page_title="Logqwest",
    page_icon="💎",
    layout="wide",
)
DEFAULT_LOCATION_EMOJI = "👤"


def generate_map(location_history, current_location):
    """location履歴から地図を生成する"""
    g = graphviz.Graph(
        graph_attr={'rankdir': 'BT', 'ratio': 'fill'},
    )
    node_ids = {}
    node_counter = 0

    # location履歴からノードを作成
    for loc in location_history:
        if loc not in node_ids:
            node_ids[loc] = f"n{node_counter}"
            node_counter += 1

    # ノードの描画 (現在地を強調)
    for loc, nid in node_ids.items():
        if loc == current_location:
            g.node(nid, label=f"{DEFAULT_LOCATION_EMOJI}{loc}")
        else:
            g.node(nid, label=loc)

    # ユニークなエッジを作成 (重複を排除)
    edges = set()
    for i in range(len(location_history) - 1):
        src, dst = location_history[i], location_history[i+1]
        if src in node_ids and dst in node_ids:
            # エッジの順序を考慮しない (A-B と B-A を同じエッジとみなす場合)
            sorted_edge = tuple(sorted((node_ids[src], node_ids[dst])))
            if sorted_edge not in edges:
                edges.add(sorted_edge)

    # エッジの描画
    for src_id, dst_id in edges:
        g.edge(src_id, dst_id, arrowhead="none")

    return g

def _process_adventure_log(adventure_log_content: str, start_time: datetime, adventurer_name: str) -> str:
    """冒険ログの内容を処理して、タイムスタンプ付きのログ行リスト（HTML形式）を返す"""
    log_lines_html = []
    for i, line in enumerate(adventure_log_content.splitlines()):
        if line.strip():
            current_time = start_time + timedelta(minutes=i * 2.5)
            time_str = current_time.strftime("%H:%M")
            # 冒険者名の補完
            line_with_name = line.replace("{name}", adventurer_name)
            time_html = f"<span style='color: gray; font-size:0.9em; margin-right:8px;'>{time_str}</span>"
            text_html = f"<span style='font-size:1em;'>{line_with_name}</span><br>"
            log_lines_html.append(time_html + text_html)
    return "".join(log_lines_html) # HTML文字列を結合して返す


def display_past_adventure(entry):
    """過去の冒険詳細を表示"""

    # スタイル適用 (CSSを関数内で定義)
    st.markdown(
        """
        <style>
        [data-testid="stMetricValue"] { font-size: 150%; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    adventure_file = get_adventure_path(area=entry['area'], adv=entry['filename'])
    if not adventure_file.exists():
        st.error("冒険記録ファイルが見つかりません")
        return

    try:
        with adventure_file.open("r", encoding="utf-8") as f:
            adventure_log_content = f.read()
    except Exception as e:
        st.error(f"ファイル読み込みエラー: {str(e)}")
        return

    start_time = datetime.fromisoformat(entry["timestamp"])

    # 冒険期間の表示形式
    num_lines = sum(1 for line in adventure_log_content.splitlines() if line.strip())
    duration_minutes = (num_lines - 1) * 2.5
    end_time = start_time + timedelta(minutes=duration_minutes)
    if start_time.date() == end_time.date():
        duration_str = f"{start_time.strftime('%m/%d(%a) %H:%M')} ~ {end_time.strftime('%H:%M')}"
    else:
        duration_str = f"{start_time.strftime('%m/%d(%a) %H:%M')} ~ {end_time.strftime('%m/%d(%a) %H:%M')}"
    st.metric("冒険期間", duration_str)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("結果", f"{get_outcome_emoji(entry['outcome'])} {entry['outcome']}")
    col2.metric("報酬", f"¥{entry['prize']}")
    col3.metric("冒険者", entry["adventurer"])
    col4.metric("エリア", entry["area"])

    st.markdown("#### 冒険ログ")
    log_html = _process_adventure_log(adventure_log_content, start_time, entry["adventurer"]) # HTML文字列を取得
    st.markdown(log_html, unsafe_allow_html=True) # markdown で HTML を表示


def show_adventure_history_sidebar(adventure_history):
    """サイドバーに冒険履歴を表示し、選択された冒険を返す"""
    st.subheader("最近の冒険")
    for entry in adventure_history:
        outcome_emoji = get_outcome_emoji(entry["outcome"])
        caption_text = (
            f"{datetime.fromisoformat(entry['timestamp']).strftime('%m/%d')} "
            f"{outcome_emoji} "
            f"{entry['adventurer']} - "
            f"{entry['area']}"
        )
        query_params = {
            "timestamp": entry["timestamp"],
            "adventurer": entry["adventurer"],
        }
        link_url = f"?{urlencode(query_params)}"
        st.caption(
            f'<a href="{link_url}" target="_self">{caption_text}</a>',
            unsafe_allow_html=True,
        )


def show_home(adventure_history):
    """ホーム画面を表示"""
    st.title("💎 Logqwest")

    # カラムレイアウトを作成
    left_column, right_column = st.columns([3, 1])

    # 右側のカラムにマップを表示
    with right_column:
        adventurer_name_container = st.empty() # 冒険者名表示用のコンテナ
        map_container = st.empty() # マップ表示用のコンテナ

    # 左側のカラムにテキストログなどを表示
    with left_column:
        if 'run_button' in st.session_state and st.session_state.run_button:
            st.session_state.running_adventure = True
        else:
            st.session_state.running_adventure = False

        if 'location_history' not in st.session_state:
            st.session_state.location_history = []

        if 'adventurer' not in st.session_state:
            st.session_state.adventurer = ""

        return_button_container = st.empty() # 戻るボタン用のコンテナ
        summary_container = st.empty() # 冒険サマリー用のコンテナ
        message_container = st.empty() # メッセージコンテナ
        if st.button(f"冒険者を雇う（¥{ADVENTURE_COST}の出資）", disabled=st.session_state.running_adventure, key="run_button"):
            st.session_state.location_history = []
            st.session_state.adventurer = ""
            accumulated_messages = []
            summary_container.empty() # コンテナを空にする
            return_button_container.empty() # 戻るボタンコンテナを空にする

            # 冒険開始前のメッセージ
            initial_message_html = "<span style='color: #888; font-style: italic;'>冒険者を探しています...</span><br>"
            accumulated_messages.insert(0, initial_message_html) # リストの先頭に追加
            message_container.markdown("".join(accumulated_messages), unsafe_allow_html=True)
            time.sleep(3)

            for event in run_adventure_streaming():
                if event["type"] == "error":
                    message_container.error(event["error"])
                    break
                elif event["type"] == "hiring":
                    hiring_message_html = f"<span style='color: #2ecc71;'>✦ 冒険者『{event['adventurer']}』を旅立たせました。 ✦</span><br>"
                    accumulated_messages.insert(0, hiring_message_html)
                    st.session_state.adventurer = event['adventurer'] # 冒険者名をセッションステートに保存
                    with right_column: # 右カラムのコンテナを使用
                        adventurer_name_container.markdown(f"{st.session_state.adventurer}の現在地") # 冒険者名を表示
                elif event["type"] == "message":
                    time_html = f"<span style='color: gray; font-size:0.9em; margin-right:8px;'>{event['time']}</span>"
                    text_html = f"<span style='font-size:1em;'>{event['text']}</span><br>"
                    message_html = time_html + text_html
                    accumulated_messages.insert(0, message_html)

                    current_location = event.get("location", "")
                    if current_location and (not st.session_state.location_history or st.session_state.location_history[-1] != current_location): # location が存在し、履歴にない or 最新の場所と異なる場合のみ追加
                        st.session_state.location_history.append(current_location)

                    # 地図を更新 (右側のカラムの map_container を使用)
                    map = generate_map(st.session_state.location_history, current_location)
                    if map: # map が None でない場合のみ表示
                        with right_column: # マップ表示を右側のカラムに限定
                            map_container.graphviz_chart(map)

                elif event["type"] == "summary":
                    summary_container.markdown(f"### 冒険結果\n{event['text']}")
                message_container.markdown("".join(accumulated_messages), unsafe_allow_html=True) # イベントごとに message_container を更新
                time.sleep(0.1)
            if return_button_container.button("戻る", key="return_button"):
                st.session_state.location_history = []
                st.session_state.adventurer = ""
                st.rerun()


def main():
    """メイン関数： Streamlitアプリケーションの実行ロジック"""
    usage_data = load_usage_data()
    adventure_history = usage_data.get("adventure_history", [])
    st.session_state.running_adventure = False

    selected_entry = None
    query_params = st.query_params
    if "timestamp" in query_params and "adventurer" in query_params:
        timestamp = query_params["timestamp"]
        adventurer = query_params["adventurer"]
        selected_entry = next(
            (e for e in adventure_history
             if e["timestamp"] == timestamp and e["adventurer"] == adventurer),
            None,
        )

    with st.sidebar:
        if st.button("ホーム"):
            st.query_params.clear()
            st.rerun()

        total_balance = sum(entry.get("prize", 0) - ADVENTURE_COST for entry in adventure_history)
        st.metric("💰所持金", f"¥{total_balance}")
        show_adventure_history_sidebar(adventure_history)

    if selected_entry:
        display_past_adventure(selected_entry)
    else:
        show_home(adventure_history)


if __name__ == "__main__":
    main()