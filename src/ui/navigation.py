import streamlit as st
from typing import List

class SidebarNavigation:
    def __init__(self, file_handler, progress_tracker):
        self.file_handler = file_handler
        self.progress_tracker = progress_tracker

    def render(self, area_names: List[str]):
        with st.sidebar:
            self._render_refresh_button()
            self._render_area_list_link()
            self._render_area_filter(area_names)

    def _render_refresh_button(self):
        if st.button("🔄 データ更新"):
            st.cache_data.clear()
            st.rerun()

    def _render_area_list_link(self):
        st.caption(
            '<a href="?area=エリア一覧" target="_self">📖全エリア一覧</a>', 
            unsafe_allow_html=True
        )

    def _render_area_filter(self, area_names: List[str]):
        filter_keyword = st.text_input(
            "🔎 エリア名でフィルタ", "", 
            placeholder="エリア名で検索", 
            label_visibility="collapsed"
        )
        
        filtered_areas = self._filter_areas(area_names, filter_keyword)
        sorted_areas = sorted(filtered_areas)

        for area in sorted_areas:
            label = self._generate_area_label(area)
            if self.file_handler.area_exists(area):
                st.caption(
                    f'<a href="?area={area}" target="_self">{label}</a>',
                    unsafe_allow_html=True
                )
            else:
                st.caption(area)

    def _filter_areas(self, area_names: List[str], keyword: str) -> List[str]:
        if not keyword:
            return area_names
        return [area for area in area_names 
                if keyword.lower() in area.lower()]

    def _generate_area_label(self, area: str) -> str:
        if self.progress_tracker.is_area_complete(area):
            if self.progress_tracker.is_area_all_checked(area):
                return f"✅{area}"
            return f"🚧{area}"
        return area
