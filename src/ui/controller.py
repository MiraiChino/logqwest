import streamlit as st
from typing import Optional

from src.ui.views import AreaListView, AreaDetailView, AdventureDetailView
from src.ui.navigation import SidebarNavigation

class UIController:
    def __init__(self, file_handler, progress_tracker):
        self.file_handler = file_handler
        self.progress_tracker = progress_tracker
        self.navigation = SidebarNavigation(file_handler, progress_tracker)
        
        self.views = {
            'area_list': AreaListView(file_handler, progress_tracker),
            'area_detail': AreaDetailView(file_handler, progress_tracker),
            'adventure_detail': AdventureDetailView(file_handler, progress_tracker)
        }

    def initialize(self):
        st.set_page_config(
            page_title="冒険データ",
            page_icon="📖",
            layout="wide",
        )

    @st.cache_data(max_entries=10)
    def load_areas_csv(_self):
        return _self.file_handler.load_areas_csv()

    @st.cache_data(max_entries=10)
    def load_all_lv_area_dict(_self):
        return _self.file_handler.load_all_lv_area_dict()

    def run(self):
        self.initialize()

        terms_dict = self.file_handler.get_all_terms_and_descriptions()
        query_params = st.query_params

        if "term" in query_params:
            term = query_params["term"]
            if term in terms_dict:
                with st.dialog(f"用語説明: {term}"):
                    st.markdown(terms_dict[term])
                    if st.button("閉じる"):
                        # 'term' パラメータのみを削除し、他のクエリパラメータは維持する
                        new_params = {k: v for k, v in query_params.items() if k != 'term'}
                        st.query_params.clear()
                        st.query_params.update(**new_params)
                        st.rerun()

        areas_df = self.load_areas_csv()
        all_lv_area_dict = self.load_all_lv_area_dict()
    
        if areas_df is None:
            st.error("エリア一覧データが見つかりません。")
            return

        lv_area_names = {lv: lv_df["エリア名"].to_list() for lv, lv_df in all_lv_area_dict.items()}
        self.navigation.render(lv_area_names)
        self._render_view(st.query_params.get("area", "エリア一覧"),
                        st.query_params.get("adv", None),
                        areas_df)

    def _render_view(self, area: str, adventure: Optional[str], areas_df):
        if adventure:
            self.views['adventure_detail'].render(area, adventure)
        elif area == "エリア一覧":
            self.views['area_list'].render(areas_df)
        else:
            self.views['area_detail'].render(area, areas_df)
