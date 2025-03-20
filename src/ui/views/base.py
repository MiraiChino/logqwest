import streamlit as st
import pandas as pd

class BaseView:
    def __init__(self, file_handler, progress_tracker):
        self.file_handler = file_handler
        self.progress_tracker = progress_tracker

    def _make_areas_clickable(self, df):
        df_clickable = df.copy()
        df_clickable["エリア名"] = df_clickable["エリア名"].apply(
            lambda area: f'<a href="?area={area}" target="_self">'
                        f'{self._get_area_label(area)}</a>'
        )
        return df_clickable

    def _make_adventures_clickable(self, df, area_name: str):
        df_clickable = df.copy()
        df_clickable["冒険名"] = df_clickable["冒険名"].apply(
            lambda adv: f'<a href="?area={area_name}&adv={adv}" target="_self">'
                       f'{self._get_adventure_label(area_name, adv)}</a>'
        )
        return df_clickable

    def _get_area_label(self, area: str) -> str:
        if self.progress_tracker.is_area_complete(area):
            if self.progress_tracker.is_area_all_checked(area):
                return f"✅{area}"
            return f"🚧{area}"
        return area

    def _get_adventure_label(self, area_name: str, adventure_name: str) -> str:
        return (f"✅{adventure_name}" 
                if self.progress_tracker.is_adventure_complete(area_name, adventure_name) 
                else adventure_name)
    
    def _display_dataframe_with_checkbox(self, df: pd.DataFrame, df_clickable: pd.DataFrame) -> pd.DataFrame:
        header_cols = st.columns([0.5] + [1] * len(df_clickable.columns))
        with header_cols[0]:
            st.write("**選択**")
        for col, header in zip(header_cols[1:], df_clickable.columns):
            with col:
                st.write(f"**{header}**")

        selected_indices = []
        for idx, row in df_clickable.iterrows():
            row_cols = st.columns([0.5] + [1] * len(row))
            checkbox_key = f"checkbox_{row.iloc[1]}_{idx}_{st.session_state.get('delete_counter', 0)}"
            
            with row_cols[0]:
                if st.checkbox("選択", key=checkbox_key, label_visibility="collapsed"):
                    selected_indices.append(idx)
            
            with row_cols[1]:
                st.html(row.iloc[0])

            for value, col in zip(row.iloc[2:], row_cols[2:]):
                with col:
                    st.write(value)
                    
        return df.loc[selected_indices] if selected_indices else pd.DataFrame()

    def _handle_deletion(self, selected_df, area_name: str, delete_type: str):
        if selected_df.empty:
            st.write("ℹ️ 削除するには行を選択してください。")
        else:
            st.dataframe(selected_df["冒険名"], hide_index=True)
            if st.button("🔥 選択行を削除", key=f"delete_{delete_type}_{area_name}"):
                adventures_to_delete = selected_df["冒険名"].tolist()
                delete_messages = self.file_handler.delete_content(area_name, adventures_to_delete, delete_type)
                for message in delete_messages:
                    st.write(message)
                st.session_state.delete_counter = st.session_state.get("delete_counter", 0) + 1
                st.cache_data.clear()

    def _handle_deletion_areas(self, selected_df):
        if selected_df.empty:
            st.write("ℹ️ 削除するには行を選択してください。")
        else:
            st.dataframe(selected_df["エリア名"], hide_index=True)
            if st.button("🔥 選択行を削除", key="delete_areas"):
                areas_to_delete = selected_df["エリア名"].tolist()
                delete_messages = self.file_handler.delete_content("", areas_to_delete, "areas")
                for message in delete_messages:
                    st.write(message)
                st.session_state.delete_counter = st.session_state.get("delete_counter", 0) + 1
                st.cache_data.clear()

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

    def _make_dataframe_as_html(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to HTML with custom styling"""
        return df.style.hide(axis="index").set_properties(
            **{'vertical-align': 'top'}
        ).to_html(escape=False, index=False)

    @st.cache_data(max_entries=10)
    def load_area_csv(_self, area_name: str):
        return _self.file_handler.load_area_csv(area_name)
        
    @st.cache_data(max_entries=10)
    def load_check_csv(_self, area_name: str, check_type: str):
        return _self.file_handler.load_check_csv(area_name, check_type)

    @st.cache_data(max_entries=10)
    def load_all_areas_check_csv(_self):
        return _self.file_handler.load_all_areas_check_csv()

    @st.cache_data(max_entries=10)
    def read_text(_self, file_path: str):
        if file_path.exists():
            content = _self.file_handler.read_text(file_path)
            return content
        else:
            return ""