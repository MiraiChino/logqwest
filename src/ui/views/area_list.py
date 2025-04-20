import streamlit as st
import pandas as pd

from ..views.base import BaseView

class AreaListView(BaseView):
    def __init__(self, file_handler, progress_tracker):
        super().__init__(file_handler, progress_tracker)

    def render(self, areas_df):
        st.title("📖全エリア一覧")

        total_areas = len(areas_df)
        completed_areas = sum(1 for area in areas_df["エリア名"] 
                            if self.progress_tracker.is_area_complete(area))
        if total_areas == 0:
            st.write("エリアデータが存在しません。")
            return

        self.render_progress_bar(
            completed_areas / total_areas,
            f"エリアデータ存在数: {completed_areas} / {total_areas}"
        )

        self._render_check_area_section(len(areas_df))

        filtered_df = self._filter_areas(areas_df)
        self._render_area_table(filtered_df)

    def _filter_areas(self, df):
        keyword = st.text_input("エリア名フィルタ", "", 
                               placeholder="エリア名でフィルタ",
                               label_visibility="collapsed")
        if keyword:
            return df[df["エリア名"].str.contains(keyword, case=False)]
        return df

    def _render_area_table(self, df: pd.DataFrame) -> str:
        df_clickable = self._make_areas_clickable(df)
        df_clickable = self.make_groups(df_clickable, "エリア", ["エリア名", "次のエリア", "前のエリア"])
        self._display_dataframe_grouped(df_clickable, start_idx=1)

    def _render_check_area_section(self, total: int):
        check_df = self.load_all_areas_check_csv()
        if check_df is not None:
            with st.expander(f"チェック: エリア({len(check_df)}/{total})"):
                clickable_df = self._make_areas_clickable(check_df)
                selected_df = self._display_dataframe_with_checkbox_grouped(check_df, clickable_df, start_idx=1)
                self._handle_deletion_areas(selected_df)