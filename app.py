import locale
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import streamlit as st

from adventure import DATA_DIR, load_usage_data, run_adventure_streaming, ADVENTURE_COST


# localeモジュールで時間のロケールを'ja_JP.UTF-8'に変更する
locale.setlocale(locale.LC_TIME, 'ja_JP.UTF-8')

st.set_page_config(
    page_title="Logqwest",
    page_icon="💎",
    layout="wide",
)

def display_past_adventure(entry):
    """過去の冒険詳細を表示"""

    # スタイルの適用
    st.markdown(
        """
        <style>
        [data-testid="stMetricValue"] { font-size: 150%; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 冒険記録ファイルの読み込み
    adventure_file = DATA_DIR / entry["area"] / f"{entry['filename']}.txt"
    if not adventure_file.exists():
        st.error("冒険記録ファイルが見つかりません")
        return

    try:
        with adventure_file.open("r", encoding="utf-8") as f:
            scenario_content = f.read()
    except Exception as e:
        st.error(f"ファイル読み込みエラー: {str(e)}")
        return

    # 開始時刻のパース
    start_time = datetime.fromisoformat(entry["timestamp"])

    # シナリオの有効な行数を数えて終了時刻を計算
    num_lines = sum(1 for line in scenario_content.splitlines() if line.strip())
    end_time = start_time + timedelta(minutes=(num_lines - 1) * 2.5)

    # 冒険期間の表示形式を決定（同日なら時間だけ、日をまたぐなら日付も表示）
    if start_time.date() == end_time.date():
        duration_str = f"{start_time.strftime('%m/%d(%a) %H:%M')} ~ {end_time.strftime('%H:%M')}"
    else:
        duration_str = f"{start_time.strftime('%m/%d(%a) %H:%M')} ~ {end_time.strftime('%m/%d(%a) %H:%M')}"
    st.metric("冒険期間", duration_str)

    # 他の基本情報の表示
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("結果", f"{get_outcome_emoji(entry['outcome'])} {entry['outcome']}")
    col2.metric("報酬", f"¥{entry['prize']}")
    col3.metric("冒険者", entry["adventurer"])
    col4.metric("エリア", entry["area"])

    # 冒険ログの表示
    st.markdown("#### 冒険ログ")
    # 冒険者名の補完
    scenario_content = scenario_content.replace("{name}", entry["adventurer"])

    log_lines = []
    for i, line in enumerate(scenario_content.splitlines()):
        if line.strip():
            current_time = start_time + timedelta(minutes=i * 2.5)
            time_str = current_time.strftime("%H:%M")
            log_lines.append(f"{time_str} {line}")

    st.text("\n".join(log_lines))

def get_outcome_emoji(outcome: str) -> str:
    """結果に応じて絵文字を返す"""
    outcome_emojis = {
        "大成功": "💎",
        "成功": "🎁",
        "失敗": "❌",
    }
    return outcome_emojis.get(outcome, "")


def show_adventure_history_sidebar(adventure_history):
    """サイドバーに冒険履歴を表示し、選択された冒険を返す"""
    st.subheader("最近の冒険")
    selected_entry = None
    for entry in reversed(adventure_history[-10:]):
        outcome_emoji = get_outcome_emoji(entry["outcome"])
        caption_text = (
            f"{entry['timestamp'][:10]} "
            f"{outcome_emoji} "
            f"{entry['adventurer']} - "
            f"{entry['area']}"
        )

        # クエリパラメータを設定してリンクを作成 (target="_self" を追加)
        query_params = {
            "timestamp": entry["timestamp"],
            "adventurer": entry["adventurer"],
        }
        st.caption(
            f'<a href="?{urlencode(query_params)}" target="_self">{caption_text}</a>',
            unsafe_allow_html=True,
        )
    return selected_entry


def show_home(adventure_history):
    """ホーム画面を表示"""
    st.title("💎 Logqwest")
    if st.button("冒険者を雇う（¥100出資）"):
        st.session_state.running_adventure = True
    if st.session_state.get("running_adventure", False):
        message_container = st.empty()
        summary_container = st.empty()

        accumulated_messages = ""

        # 冒険開始前のメッセージを表示
        initial_message = (
            "<span style='color: #888; font-style: italic;'>冒険者を探しています...</span><br>"
        )
        accumulated_messages += initial_message
        message_container.markdown(accumulated_messages, unsafe_allow_html=True)
        time.sleep(1)  # 演出用の待機時間

        for event in run_adventure_streaming():
            if event["type"] == "error":
                st.error(event["error"])
                break
            elif event["type"] == "hiring":  # 新しいイベントタイプ
                hiring_html = (
                    f"<span style='color: #2ecc71;'>✦ {event['text']} ✦</span><br>"
                )
                accumulated_messages += hiring_html
                message_container.markdown(accumulated_messages, unsafe_allow_html=True)
                time.sleep(1)  # 演出用の待機時間
            elif event["type"] == "message":
                time_html = f"<span style='color: gray; font-size:0.9em; margin-right:8px;'>{event['time']}</span>"
                text_html = f"<span style='font-size:1em;'>{event['text']}</span><br>"
                accumulated_messages += time_html + text_html
                message_container.markdown(accumulated_messages, unsafe_allow_html=True)
            elif event["type"] == "summary":
                summary_container.markdown(f"### 冒険結果\n{event['text']}")
            time.sleep(0.1)
        st.session_state.running_adventure = False # 冒険終了後に False に戻す


def main():
    """メイン関数： Streamlit アプリケーションの実行ロジックを記述"""

    # ユーザーデータの読み込み
    usage_data = load_usage_data()
    adventure_history = usage_data.get("adventure_history", [])

    # クエリパラメータから選択された冒険履歴を取得
    selected_entry = None
    if "timestamp" in st.query_params and "adventurer" in st.query_params:
        timestamp = st.query_params["timestamp"]
        adventurer = st.query_params["adventurer"]
        selected_entry = next(
            (
                e
                for e in adventure_history
                if e["timestamp"] == timestamp and e["adventurer"] == adventurer
            ),
            None,
        )

    with st.sidebar:
        if st.button("ホーム"):
            st.query_params.clear() # ホームボタンで query_params をクリア
            st.rerun()

        # 合計収支の計算
        # 冒険履歴から prize を集計し、合計収支を計算
        total_balance = sum(entry.get("prize", 0) - ADVENTURE_COST for entry in adventure_history)
        st.metric("💰所持金", f"¥{total_balance}")

        show_adventure_history_sidebar(adventure_history)

    # メインコンテンツ
    if selected_entry:
        display_past_adventure(selected_entry)
    elif not st.session_state.get("running_adventure", False):
        show_home(adventure_history)


if __name__ == "__main__":
    main()