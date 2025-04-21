import streamlit as st
from typing import List, Dict

class SidebarNavigation:
    def __init__(self, file_handler, progress_tracker):
        self.file_handler = file_handler
        self.progress_tracker = progress_tracker

    def render(self, lv_area_names: Dict):
        with st.sidebar:
            self._render_refresh_button()
            self._render_area_list_link()
            self._render_area_filter(lv_area_names)

    def _render_refresh_button(self):
        if st.button("🔄 データ更新"):
            st.cache_data.clear()
            st.rerun()

    def _render_area_list_link(self):
        st.caption(
            '<a href="?area=エリア一覧" target="_self">📖全エリア一覧</a>', 
            unsafe_allow_html=True
        )

    def _render_area_filter(self, lv_area_names: Dict):
        filter_keyword = st.text_input(
            "🔎 エリア名でフィルタ", "", 
            placeholder="エリア名で検索", 
            label_visibility="collapsed"
        )
        
        filtered_areas = self._filter_areas(lv_area_names, filter_keyword)

        for lv, area_names in filtered_areas.items():
            completed_areas = [area for area in area_names if self.progress_tracker.is_area_complete(area) and self.progress_tracker.is_area_all_checked(area)]
            with st.expander(f"{lv} ({len(completed_areas)}/{len(area_names)})", expanded=True):
                for area in sorted(area_names):
                    label = self._generate_area_label(area)
                    if self.file_handler.area_exists(area):
                        st.caption(
                            f'<a href="?area={area}" target="_self">{label}</a>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.caption(area)

    def _filter_areas(self, lv_area_names: Dict, keyword: str) -> Dict:
        if not keyword:
            return lv_area_names
        filtered_areas = {}
        for lv, area_names in lv_area_names.items():
            filtered_areas[lv] = [area for area in area_names if keyword.lower() in area.lower()]
        return filtered_areas

    def _generate_area_label(self, area: str) -> str:
        if self.progress_tracker.is_area_complete(area):
            if self.progress_tracker.is_area_all_checked(area):
                return f"✅{area}"
            return f"🚧{area}"
        return area
