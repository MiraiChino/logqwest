from dataclasses import dataclass
from typing import Optional
import streamlit as st

@dataclass
class ViewState:
    current_area: Optional[str]
    current_adventure: Optional[str]
    filter_keyword: str = ""

class BaseView:
    def __init__(self, file_handler, progress_tracker):
        self.file_handler = file_handler
        self.progress_tracker = progress_tracker

    def render_progress_bar(self, ratio: float, label: str):
        if ratio == 1.0:
            st.markdown(
                """
                <style>
                .stProgress > div > div > div > div {
                    background-color: #03C03C;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
        st.write(label)
        st.progress(ratio)
