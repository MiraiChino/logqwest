import streamlit as st
import re

from ..views.base import BaseView

class AreaDetailView(BaseView):
    def render(self, area_name: str, areas_df):
        st.title(f"{area_name} のデータ")
        
        self.area_name = area_name
        adventures_df = self.load_area_csv(area_name)
        if adventures_df is not None:
            self._render_progress(adventures_df)
            self._render_area_info(areas_df, area_name)
            self._render_adventures_grouped_by_name(area_name, adventures_df)

    def _render_progress(self, df):
        total = len(df)
        completed = sum(1 for adv in df["冒険名"] 
                       if self.progress_tracker.is_adventure_complete(self.area_name, adv))
        if total == 0:
            st.warning("冒険データが存在しません。")
            return
        self.render_progress_bar(
            completed / total,
            f"冒険データ存在数: {completed} / {total}"
        )

    def _render_area_info(self, areas_df, area_name):
        area_df = areas_df[areas_df["エリア名"] == area_name]
        if not area_df.empty:
            with st.expander("エリア情報", expanded=True):
                clickable_area_df = self._make_areas_clickable(area_df)
                clickable_area_df = self.make_groups(clickable_area_df, "エリア", ["エリア名", "次のエリア", "前のエリア"])
                self._display_dataframe_grouped(clickable_area_df, start_idx=1)

    def _render_adventures_by_result(self, df, area_name):
        for result in ["失敗", "成功", "大成功"]:
            result_df = df[df["結果"] == result]
            completed = sum(1 for adv in result_df["冒険名"] 
                          if self.progress_tracker.is_adventure_complete(self.area_name, adv))
            
            with st.expander(f"冒険結果: {result} ({completed}/{len(result_df)})"):
                if not result_df.empty:
                    clickable_df = self._make_adventures_clickable(result_df, area_name)
                    self._display_dataframe(clickable_df)

    def _render_check_sections(self, area_name: str, total_adventures: int):
        self._render_check_adventure_section(area_name, total_adventures)
        self._render_check_log_section(area_name, total_adventures)
        self._render_check_location_section(area_name, total_adventures)

    def _render_check_adventure_section(self, area_name: str, total: int):
        check_df = self.load_check_csv(area_name, "adv")
        if check_df is not None:
            with st.expander(f"チェック: 冒険サマリー({len(check_df)}/{total})"):
                clickable_df = self._make_adventures_clickable(check_df, area_name)
                selected_df = self._display_dataframe_with_checkbox_grouped(check_df, clickable_df)
                
                self._handle_deletion(selected_df, area_name, "adventures")

    def _render_check_log_section(self, area_name: str, total: int):
        check_df = self.load_check_csv(area_name, "log")
        if check_df is not None:
            with st.expander(f"チェック: 冒険ログ({len(check_df)}/{total})"):
                clickable_df = self._make_adventures_clickable(check_df, area_name)
                selected_df = self._display_dataframe_with_checkbox_grouped(check_df, clickable_df)
                self._handle_deletion(selected_df, area_name, "logs")

    def _render_check_location_section(self, area_name: str, total: int):
        check_df = self.load_check_csv(area_name, "loc")
        if check_df is not None:
            with st.expander(f"チェック: 位置情報({len(check_df)}/{total})"):
                clickable_df = self._make_adventures_clickable(check_df, area_name)
                selected_df = self._display_dataframe_with_checkbox_grouped(check_df, clickable_df)
                self._handle_deletion(selected_df, area_name, "locations")

    def _render_adventures_grouped_by_name(self, area_name: str, adventures_df):
        unique_adventure_names = adventures_df["冒険名"].unique()
        check_adv_df = self.load_check_csv(area_name, "adv")
        check_log_df = self.load_check_csv(area_name, "log")
        check_loc_df = self.load_check_csv(area_name, "loc")

        for adventure_name in unique_adventure_names:
            label = self._get_adventure_label(area_name, adventure_name)
            with st.expander(f"{label}{adventure_name}", expanded=False): # 初期状態は閉じたexpander
                adventure_summary_df = adventures_df[adventures_df["冒険名"] == adventure_name].copy()
                if not adventure_summary_df.empty:
                    item_name = adventure_summary_df.get("アイテム", adventure_summary_df.get("items", "")).astype(str)
                    item_name = item_name.replace({"None": "", "nan": ""}).fillna("")
                    chapter_cols = [c for c in adventure_summary_df.columns if re.match(r"^\d+章$", str(c))]
                    last_col = None
                    for c in reversed(chapter_cols):
                        col = adventure_summary_df[c].astype(str).replace({"nan": ""}).fillna("")
                        if col.str.strip().ne("").any():
                            last_col = c
                            break
                    for c in chapter_cols:
                        adventure_summary_df[c] = adventure_summary_df[c].astype(str).replace({"nan": ""}).fillna("")
                    if last_col and last_col == (chapter_cols[-1] if chapter_cols else None):
                        suffix = item_name.apply(lambda x: f"｜{x}" if isinstance(x, str) and x.strip() else "")
                        adventure_summary_df[last_col] = adventure_summary_df[last_col].astype(str).fillna("") + suffix
                    clickable_adv_df = self._make_adventures_clickable(adventure_summary_df, area_name)
                    clickable_adv_df = self.make_groups(clickable_adv_df, "冒険", ["冒険名", "次の冒険", "前の冒険"])
                    self._display_dataframe_grouped(clickable_adv_df, start_idx=1)

                # Check: 冒険サマリー
                st.markdown("##### チェック: 冒険サマリー")
                if check_adv_df is not None:
                    adventure_check_adv_df = check_adv_df[check_adv_df["冒険名"] == adventure_name]
                    if not adventure_check_adv_df.empty:
                        clickable_adv_df = self._make_adventures_clickable(adventure_check_adv_df, area_name)
                        selected_adv_df = self._display_dataframe_with_checkbox_grouped(adventure_check_adv_df, clickable_adv_df)
                        self._handle_deletion(selected_adv_df, area_name, "adventures")

                # Check: 冒険ログ
                st.markdown("##### チェック: 冒険ログ")
                if check_log_df is not None:
                    adventure_check_log_df = check_log_df[check_log_df["冒険名"] == adventure_name]
                    if not adventure_check_log_df.empty:
                        clickable_log_df = self._make_adventures_clickable(adventure_check_log_df, area_name)
                        selected_log_df = self._display_dataframe_with_checkbox(adventure_check_log_df, clickable_log_df)
                        self._handle_deletion(selected_log_df, area_name, "logs")

                # Check: 位置情報
                st.markdown("##### チェック: 位置情報")
                if check_loc_df is not None:
                    adventure_check_loc_df = check_loc_df[check_loc_df["冒険名"] == adventure_name]
                    if not adventure_check_loc_df.empty:
                        clickable_loc_df = self._make_adventures_clickable(adventure_check_loc_df, area_name)
                        selected_loc_df = self._display_dataframe_with_checkbox(adventure_check_loc_df, clickable_loc_df)
                        self._handle_deletion(selected_loc_df, area_name, "locations")