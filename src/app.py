import locale
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import streamlit as st
import graphviz

from src.utils.file_handler import FileHandler, FileStructure
from src.utils.config import ConfigManager
from adventure import run_adventure_streaming, ADVENTURE_COST, INTERVAL_MINUTES, LONG_INTERVAL_MINUTES
from pathlib import Path

config_manager = ConfigManager(Path("prompt/config.json"))
file_structure = FileStructure(
    data_dir=config_manager.paths.data_dir,
    check_result_dir=config_manager.paths.check_result_dir,
    prompt_dir=config_manager.paths.prompt_dir
)
file_handler = FileHandler(file_structure)


# ロケール設定
locale.setlocale(locale.LC_TIME, 'ja_JP.UTF-8')

# Streamlitページ設定
st.set_page_config(
    page_title="Logqwest",
    page_icon="💎",
    layout="wide",
)
DEFAULT_LOCATION_EMOJI = "👤"


def get_result_emoji(result: str) -> str:
    """結果に応じて絵文字を返す"""
    result_emojis = {
        "大成功": "💎",
        "成功": "🎁",
        "失敗": "❌",
    }
    return result_emojis.get(result, "")

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

    # ノードの描画
    for loc, nid in node_ids.items():
        if current_location and loc == current_location:
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
            if sorted_edge not in edges and src != dst:
                edges.add(sorted_edge)

    # エッジの描画
    for src_id, dst_id in edges:
        g.edge(src_id, dst_id, arrowhead="none")

    return g

def _process_adventure_log(adventure_log_content: str, location_history: list, start_time: datetime, adventurer_name: str, terms_dict: dict, precursor: str = None) -> str:
    """冒険ログの内容を処理して、タイムスタンプ付きのログ行リスト（HTML形式）を返す"""
    log_lines_html = []
    last_loc = None
    current_time = start_time
    time_increment = timedelta(minutes=INTERVAL_MINUTES)
    long_time_increment = timedelta(minutes=LONG_INTERVAL_MINUTES)

    # 入力が空の場合のガード
    if not adventure_log_content or not location_history:
        return ""

    lines = adventure_log_content.splitlines()

    # ログ行数と場所履歴の数が一致しない場合の考慮 (zipは短い方に合わせる)
    if len(lines) != len(location_history):
        raise ValueError(f"ログ行数{len(lines)}と場所履歴の数{len(location_history)}が一致しません。")

    for i, (line, loc) in enumerate(zip(lines, location_history)):
        if line.strip():  # 空行は無視
            # 1. このステップで加算する時間を決定
            increment_this_step = timedelta(0)  # 最初の行は時間経過なし
            if i > 0:  # 2行目以降
                is_location_change = (loc != last_loc)
                increment_this_step = long_time_increment if is_location_change else time_increment

            # 2. 時間を加算
            current_time += increment_this_step

            # 3. 時刻文字列をフォーマット
            time_str = current_time.strftime("%H:%M")

            # 4. ログ行のテキストを置換・準備
            line_with_name = line.replace("{name}", adventurer_name)
            if precursor:
                line_with_name = line_with_name.replace("{precursor}", precursor)
            
            # 用語をハイライト
            highlighted_line = file_handler._make_terms_clickable(line_with_name, terms_dict)

            # 5. HTMLを生成してリストに追加
            time_html = f"<span style='color: gray; font-size:0.9em; margin-right:8px;'>{time_str}</span>"
            text_html = f"<span style='font-size:1em;'>{highlighted_line}</span><br>"
            log_lines_html.append(time_html + text_html)

            # 6. 次のループのために現在の場所を記録
            last_loc = loc

    return "".join(log_lines_html) # HTML文字列を結合して返す

def count_changes(seq):
    return sum(a != b for a, b in zip(seq, seq[1:]))

def display_past_adventure(entry, terms_dict):
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

    adventure_file = file_handler.get_adventure_path(entry['area'], entry['adventure'])
    if not adventure_file.exists():
        st.error("冒険記録ファイルが見つかりません")
        return

    try:
        with adventure_file.open("r", encoding="utf-8") as f:
            adventure_log_content = f.read()
        location_history_path = file_handler.get_location_path(entry['area'], entry['adventure'])
        if location_history_path.exists():
            with location_history_path.open("r", encoding="utf-8") as f:
                location_history = [loc.strip() for loc in f.readlines() if loc.strip()]
    except Exception as e:
        st.error(f"ファイル読み込みエラー: {str(e)}")
        return

    start_time = datetime.fromisoformat(entry["timestamp"])

    # 冒険期間の表示形式
    num_lines = sum(1 for line in adventure_log_content.splitlines() if line.strip())
    duration_minutes = (num_lines - 1) * INTERVAL_MINUTES
    if location_history:
        duration_minutes += count_changes(location_history) * (LONG_INTERVAL_MINUTES - INTERVAL_MINUTES)
    end_time = start_time + timedelta(minutes=duration_minutes)
    if start_time.date() == end_time.date():
        duration_str = f"{start_time.strftime('%m/%d(%a) %H:%M')} ~ {end_time.strftime('%H:%M')}"
    else:
        duration_str = f"{start_time.strftime('%m/%d(%a) %H:%M')} ~ {end_time.strftime('%m/%d(%a) %H:%M')}"
    st.metric("冒険期間", duration_str)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("結果", f"{get_result_emoji(entry['result'])} {entry['result']}")
    col2.metric("冒険者", entry["adventurer"])
    col3.metric("エリア", entry["area"])

    if entry.get("items"):
        st.markdown("#### 獲得アイテム")
        for item in entry["items"]:
            st.write(f"- {item['name']} x {item['quantity']} (価値: ¥{item['value']})")

    # カラムレイアウトを作成
    left_column, right_column = st.columns([3, 1])

    # 右側のカラムにマップを表示
    with right_column:
        map_container = st.empty() # マップ表示用のコンテナ

    with left_column:
        st.markdown("#### 冒険ログ")
        log_html = _process_adventure_log(adventure_log_content, location_history, start_time, entry["adventurer"], terms_dict, entry["precursor"]) # HTML文字列を取得
        st.write(log_html, unsafe_allow_html=True) # write で HTML を表示

    # マップを表示
    if location_history:
        adv_map = generate_map(location_history, None) # current_location は None
        if adv_map:
            with right_column:
                map_container.graphviz_chart(adv_map)


def show_adventure_history_sidebar(adventure_history):
    """サイドバーに冒険履歴を表示し、選択された冒険を返す"""
    st.subheader("最近の冒険")
    for entry in adventure_history:
        result_emoji = get_result_emoji(entry["result"])
        caption_text = (
            f"{datetime.fromisoformat(entry['timestamp']).strftime('%m/%d')} "
            f"{result_emoji} "
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


def show_home(adventure_history, terms_dict):
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
        
        accumulated_messages = []

        if 'adventurer' not in st.session_state:
            st.session_state.adventurer = ""

        return_button_container = st.empty() # 戻るボタン用のコンテナ
        summary_container = st.empty() # 冒険サマリー用のコンテナ
        message_container = st.empty() # メッセージコンテナ
        message_container.write("".join(accumulated_messages), unsafe_allow_html=True)
        if st.button(f"冒険者を雇う（¥{ADVENTURE_COST}の出資）", disabled=st.session_state.running_adventure, key="run_button"):
            st.session_state.location_history = []
            st.session_state.adventurer = ""
            accumulated_messages = []
            summary_container.empty() # コンテナを空にする
            return_button_container.empty() # 戻るボタンコンテナを空にする

            # 冒険開始前のメッセージ
            initial_message_html = "<span style='color: #888; font-style: italic;'>冒険者を探しています...</span><br>"
            accumulated_messages.insert(0, initial_message_html) # リストの先頭に追加
            message_container.write("".join(accumulated_messages), unsafe_allow_html=True)
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
                    highlighted_text = file_handler._make_terms_clickable(event['text'], terms_dict)
                    text_html = f"<span style='font-size:1em;'>{highlighted_text}</span><br>"
                    message_html = time_html + text_html
                    accumulated_messages.insert(0, message_html)
                    
                    current_location = event.get("location", "")
                    if current_location and (not st.session_state.location_history or st.session_state.location_history[-1] != current_location): # location が存在し、履歴にない or 最新の場所と異なる場合のみ追加
                        st.session_state.location_history.append(current_location)

                    # 地図を更新 (右側のカラムの map_container を使用)
                    adv_map = generate_map(st.session_state.location_history, current_location)
                    if adv_map: # adv_map が None でない場合のみ表示
                        with right_column: # マップ表示を右側のカラムに限定
                            map_container.graphviz_chart(adv_map)

                elif event["type"] == "summary":
                    summary_container.markdown(f"### 冒険結果\n{event['text']}")
                    if "items" in event and event.get("result") != "失敗":
                        st.markdown("#### 獲得アイテム")
                        for name in event["items"]:
                            st.write(f"- {name}")
                            file_handler.add_item_to_inventory(name, event.get("result", "成功"), config_manager.item_value_table)
                    file_handler.update_balance(-ADVENTURE_COST) # 冒険費用を差し引く
                message_container.write("".join(accumulated_messages), unsafe_allow_html=True) # イベントごとに message_container を更新
                time.sleep(0.1)
            if return_button_container.button("戻る", key="return_button"):
                st.session_state.location_history = []
                st.session_state.adventurer = ""
                st.rerun()


def main():
    """メイン関数： Streamlitアプリケーションの実行ロジック"""
    # カスタムツールチップ用のCSS
    st.markdown("""
    <style>
    .tooltip-span {
        position: relative;
    }
    .tooltip-span:hover::after {
        content: attr(data-tooltip);
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        padding: 8px 12px;
        border-radius: 6px;
        background-color: #333;
        color: #fff;
        font-size: 0.9em;
        white-space: pre-wrap; /* 改行を許可し、長いテキストを折り返す */
        z-index: 1000;
        width: max-content; /* コンテンツの幅に合わせる */
        max-width: 300px; /* 最大幅を指定 */
        text-align: left; /* テキストを左揃えに */
    }
    </style>
    """, unsafe_allow_html=True)
    usage_data = file_handler.load_usage_data()
    adventure_history = usage_data.get("adventure_history", [])
    st.session_state.running_adventure = False
    st.cache_data.clear() # キャッシュをクリア

    terms_dict = file_handler.get_all_terms_and_descriptions()
    

    selected_entry = None
    if "timestamp" in st.query_params and "adventurer" in st.query_params:
        timestamp = st.query_params["timestamp"]
        adventurer = st.query_params["adventurer"]
        selected_entry = next(
            (e for e in adventure_history
             if e["timestamp"] == timestamp and e["adventurer"] == adventurer),
            None,
        )

    with st.sidebar:
        if st.button("ホーム"):
            st.query_params.clear()
            # セッションステートをクリア
            if 'location_history' in st.session_state:
                st.session_state.location_history = []
            if 'adventurer' in st.session_state:
                st.session_state.adventurer = ""
            st.rerun()

        current_balance = file_handler.load_usage_data().get("balance", 0)
        st.metric("💰所持金", f"¥{current_balance}")
        show_adventure_history_sidebar(adventure_history)

    if selected_entry:
        display_past_adventure(selected_entry, terms_dict)
    else:
        show_home(adventure_history, terms_dict)


if __name__ == "__main__":
    main()