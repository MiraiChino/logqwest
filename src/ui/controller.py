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

    def run(self):
        self.initialize()
        areas_df = self.load_areas_csv()
    
        if areas_df is None:
            st.error("エリア一覧データが見つかりません。")
            return

        area_names = areas_df["エリア名"].tolist()
        self.navigation.render(area_names)
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
