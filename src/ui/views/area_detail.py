import streamlit as st

from ..views.base import BaseView

class AreaDetailView(BaseView):
    def render(self, area_name: str, areas_df):
        st.title(f"{area_name} のデータ")
        
        self.area_name = area_name
        adventures_df = self.load_area_csv(area_name)
        if adventures_df is not None:
            self._render_progress(adventures_df)
            self._render_area_info(areas_df, area_name)
            self._render_adventures_by_result(adventures_df, area_name)
            self._render_check_sections(area_name, len(adventures_df))

    def _render_progress(self, df):
        total = len(df)
        completed = sum(1 for adv in df["冒険名"] 
                       if self.progress_tracker.is_adventure_complete(self.area_name, adv))
        self.render_progress_bar(
            completed / total,
            f"冒険データ存在数: {completed} / {total}"
        )

    def _render_area_info(self, areas_df, area_name):
        area_info = areas_df[areas_df["エリア名"] == area_name]
        if not area_info.empty:
            with st.expander("エリア情報", expanded=True):
                st.markdown(self._make_dataframe_as_html(area_info), 
                          unsafe_allow_html=True)

    def _render_adventures_by_result(self, df, area_name):
        for result in ["失敗", "成功", "大成功"]:
            result_df = df[df["結果"] == result]
            completed = sum(1 for adv in result_df["冒険名"] 
                          if self.progress_tracker.is_adventure_complete(self.area_name, adv))
            
            with st.expander(f"冒険結果: {result} ({completed}/{len(result_df)})"):
                if not result_df.empty:
                    clickable_df = self._make_adventures_clickable(result_df, area_name)
                    st.markdown(self._make_dataframe_as_html(clickable_df), 
                              unsafe_allow_html=True)

    def _render_check_sections(self, area_name: str, total_adventures: int):
        self._render_check_adventure_section(area_name, total_adventures)
        self._render_check_log_section(area_name, total_adventures)
        self._render_check_location_section(area_name, total_adventures)

    def _render_check_adventure_section(self, area_name: str, total: int):
        check_df = self.load_check_csv(area_name, "adv")
        if check_df is not None:
            with st.expander(f"チェック: 冒険サマリー({len(check_df)}/{total})"):
                clickable_df = self._make_adventures_clickable(check_df, area_name)
                selected_df = self._display_dataframe_with_checkbox(check_df, clickable_df)
                self._handle_deletion(selected_df, area_name, "adventures")

    def _render_check_log_section(self, area_name: str, total: int):
        check_df = self.load_check_csv(area_name, "log")
        if check_df is not None:
            with st.expander(f"チェック: 冒険ログ({len(check_df)}/{total})"):
                clickable_df = self._make_adventures_clickable(check_df, area_name)
                selected_df = self._display_dataframe_with_checkbox(check_df, clickable_df)
                self._handle_deletion(selected_df, area_name, "logs")

    def _render_check_location_section(self, area_name: str, total: int):
        check_df = self.load_check_csv(area_name, "loc")
        if check_df is not None:
            with st.expander(f"チェック: 位置情報({len(check_df)}/{total})"):
                clickable_df = self._make_adventures_clickable(check_df, area_name)
                selected_df = self._display_dataframe_with_checkbox(check_df, clickable_df)
                self._handle_deletion(selected_df, area_name, "locations")