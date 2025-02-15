import locale
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import streamlit as st

from adventure import DATA_DIR, load_usage_data, run_adventure_streaming, ADVENTURE_COST


# ロケール設定
locale.setlocale(locale.LC_TIME, 'ja_JP.UTF-8')

# Streamlitページ設定
st.set_page_config(
    page_title="Logqwest",
    page_icon="💎",
    layout="wide",
)

def get_outcome_emoji(outcome: str) -> str:
    """結果に応じて絵文字を返す"""
    outcome_emojis = {
        "大成功": "💎",
        "成功": "🎁",
        "失敗": "❌",
    }
    return outcome_emojis.get(outcome, "")

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

    adventure_file = DATA_DIR / entry["area"] / f"{entry['filename']}.txt"
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
    for entry in adventure_history[-10:]:
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

    if 'run_button' in st.session_state and st.session_state.run_button == True:
        st.session_state.running_adventure = True
    else:
        st.session_state.running_adventure = False

    if st.button("冒険者を雇う（¥100出資）", disabled=st.session_state.running_adventure, key="run_button"):
        message_container = st.empty()
        summary_container = st.empty()
        accumulated_messages = ""

        # 冒険開始前のメッセージ
        initial_message_html = "<span style='color: #888; font-style: italic;'>冒険者を探しています...</span><br>"
        accumulated_messages += initial_message_html
        message_container.markdown(accumulated_messages, unsafe_allow_html=True)
        time.sleep(3)

        for event in run_adventure_streaming():
            if event["type"] == "error":
                st.error(event["error"])
                break
            elif event["type"] == "hiring":
                hiring_message_html = f"<span style='color: #2ecc71;'>✦ 冒険者『{event['adventurer']}』を雇用しました。 ✦</span><br>"
                accumulated_messages += hiring_message_html
            elif event["type"] == "message":
                time_html = f"<span style='color: gray; font-size:0.9em; margin-right:8px;'>{event['time']}</span>"
                text_html = f"<span style='font-size:1em;'>{event['text']}</span><br>"
                accumulated_messages += time_html + text_html
            elif event["type"] == "summary":
                summary_container.markdown(f"### 冒険結果\n{event['text']}")
            message_container.markdown(accumulated_messages, unsafe_allow_html=True) # イベントごとに message_container を更新
            time.sleep(0.1)
        st.session_state.running_adventure = False


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