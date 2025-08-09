import streamlit as st
from typing import Optional

from src.ui.views import AreaListView, AreaDetailView, AdventureDetailView
from src.ui.navigation import SidebarNavigation

class UIController:
    def __init__(self, file_handler, progress_tracker):
        self.file_handler = file_handler
        self.progress_tracker = progress_tracker
        self.navigation = SidebarNavigation(file_handler, progress_tracker)
        self.terms_dict = self.file_handler.get_all_terms_and_descriptions()
        
        self.views = {
            'area_list': AreaListView(file_handler, progress_tracker, terms_dict=self.terms_dict),
            'area_detail': AreaDetailView(file_handler, progress_tracker, terms_dict=self.terms_dict),
            'adventure_detail': AdventureDetailView(file_handler, progress_tracker, terms_dict=self.terms_dict)
        }

    def initialize(self):
        st.set_page_config(
            page_title="冒険データ",
            page_icon="📖",
            layout="wide",
        )
        self._inject_tooltip_css()

    def _inject_tooltip_css(self):
        st.markdown("""
            <style>
            .tooltip-span {
                position: relative;
                text-decoration: underline;
                cursor: help;
            }
            .tooltip-span:hover::after {
                content: attr(data-tooltip);
                position: absolute;
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                background-color: #333;
                color: #fff;
                padding: 5px 10px;
                border-radius: 5px;
                white-space: normal; /* 通常の改行ルールに戻す */
                z-index: 10;
                width: auto; /* コンテンツの幅に合わせる */
                max-width: 450px; /* 最大幅を調整 */
                text-align: left; /* テキストを左揃えに */
                right: auto; /* 右端に固定されないようにする */
            }
            </style>
        """, unsafe_allow_html=True)

    @st.cache_data(max_entries=10)
    def load_areas_csv(_self):
        return _self.file_handler.load_areas_csv()

    @st.cache_data(max_entries=10)
    def load_all_lv_area_dict(_self):
        return _self.file_handler.load_all_lv_area_dict()

    def run(self):
        self.initialize()

        query_params = st.query_params

        if "term" in query_params:
            term = query_params["term"]
            if term in self.terms_dict:
                with st.dialog(f"用語説明: {term}"):
                    st.markdown(self.terms_dict[term])
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
