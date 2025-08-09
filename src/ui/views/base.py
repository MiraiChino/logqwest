import streamlit as st
import pandas as pd

class BaseView:
    def __init__(self, file_handler, progress_tracker):
        self.file_handler = file_handler
        self.progress_tracker = progress_tracker

    def _make_areas_clickable(self, df):
        df_clickable = df.copy()
        if "エリア名" in df_clickable.columns:
            df_clickable["エリア名"] = df_clickable["エリア名"].apply(
                lambda area: f'<a href="?area={area}" target="_self">'
                            f'{self._get_area_label(area)}{area}</a>'
            )
        if "前のエリア" in df_clickable.columns:
            df_clickable["前のエリア"] = df_clickable["前のエリア"].apply(
                lambda area: f'<a href="?area={area}" target="_self">'
                            f'{self._get_area_label(area)}{area}</a>' if area != "なし" else area
            )
        if "次のエリア" in df_clickable.columns:
            df_clickable["次のエリア"] = df_clickable["次のエリア"].apply(
                lambda area: f'<a href="?area={area}" target="_self">'
                            f'{self._get_area_label(area)}{area}</a>' if area != "なし" else area
            )
        return df_clickable

    def _make_adventures_clickable(self, df, area_name: str):
        df_clickable = df.copy()
        if "冒険名" in df_clickable.columns:
            df_clickable["冒険名"] = df_clickable["冒険名"].apply(
                lambda adv: f'<a href="?area={area_name}&adv={adv}" target="_self">'
                        f'{self._get_adventure_label(area_name, adv)}{adv}</a>'
            )
        if "前の冒険" in df_clickable.columns:
            prev_adventure = df_clickable["前の冒険"].to_list()[0]
            if prev_adventure != "なし":
                prev_area_name = prev_adventure.split('_')[1]
                df_clickable["前の冒険"] = df_clickable["前の冒険"].apply(
                    lambda adv: f'<a href="?area={prev_area_name}&adv={adv}" target="_self">'
                            f'{self._get_adventure_label(prev_area_name, adv)}{adv}</a>'
                )
        if "次の冒険" in df_clickable.columns:
            prev_adventure = df_clickable["次の冒険"].to_list()[0]
            if prev_adventure != "なし":
                prev_area_name = prev_adventure.split('_')[1]
                df_clickable["次の冒険"] = df_clickable["次の冒険"].apply(
                    lambda adv: f'<a href="?area={prev_area_name}&adv={adv}" target="_self">'
                            f'{self._get_adventure_label(prev_area_name, adv)}{adv}</a>'
                )
        return df_clickable

    def _get_area_label(self, area: str) -> str:
        if self.progress_tracker.is_area_complete(area):
            if self.progress_tracker.is_area_all_checked(area):
                return "✅"
            return "🚧"
        return ""

    def _get_adventure_label(self, area_name: str, adventure_name: str) -> str:
        if self.progress_tracker.is_adventure_complete(area_name, adventure_name):
            if self.progress_tracker.is_adventure_all_checked(area_name, adventure_name):
                return "✅"
            return "🚧"
        return ""
    
    def render_format_cell_content(self, value):
        if isinstance(value, str):


            if ';' in value:
                formatted_text = ""
                for element in value.split(';'):
                    if ':' in element:
                        key, val = element.split(':', 1)
                        formatted_text += f"**{key}**: {val}  \n"
                    else:
                        formatted_text += f"{element}  \n"
                return st.markdown(formatted_text)
            elif ':' in value:
                key, val = value.split(':', 1)
                return st.markdown(f"**{key}**: {val}")
        return st.html(value)

    def display_dataframe(self, df: pd.DataFrame,
                        df_clickable: pd.DataFrame = None,
                        display_checkbox: bool = False, 
                        group_columns: bool = False, 
                        start_content_col_idx: int = 1) -> pd.DataFrame:
        if df_clickable is None:
            df_clickable = df
        selected_indices = []
        header_columns_config = [0.5] if display_checkbox else []

        if group_columns:
            grouped_headers = {}
            for key in df.columns:
                if isinstance(key, str) and " - " in key:
                    parent_header = key.split(" - ", 1)[0]
                    grouped_headers.setdefault(parent_header, True)
                else:
                    grouped_headers[key] = True
            header_columns_config += [1] * len(grouped_headers)
            header_cols = st.columns(header_columns_config)

            col_idx = 0
            if display_checkbox:
                with header_cols[col_idx]:
                    st.write("**選択**")
                col_idx += 1

            header_keys = list(grouped_headers.keys())
            for i in range(len(header_keys)):
                header = header_keys[i]
                with header_cols[col_idx]:
                    st.write(f"**{header}**")
                col_idx += 1
        else:
            header_columns_config += [1] * len(df.columns)
            header_cols = st.columns(header_columns_config)

            col_idx = 0
            if display_checkbox:
                with header_cols[col_idx]:
                    st.write("**選択**")
                col_idx += 1
            for header in df.columns:
                with header_cols[col_idx]:
                    st.write(f"**{header}**")
                col_idx += 1

        for idx, row in df_clickable.iterrows():
            row_columns_config = [0.5] if display_checkbox else []
            if group_columns:
                grouped_row = {}
                for key, value in row.items():
                    if isinstance(key, str) and " - " in key:
                        parent, child = key.split(" - ", 1)
                        grouped_row.setdefault(parent, {})[child] = value
                    else:
                        grouped_row[key] = value
                row_columns_config += [1] * len(grouped_row)
            else:
                row_columns_config += [1] * len(row)
            row_cols = st.columns(row_columns_config)
            row_col_idx = 0

            if display_checkbox:
                checkbox_key_suffix = st.session_state.get('delete_counter', 0)
                checkbox_key = f"checkbox_{row.values[1]}_{idx}_{checkbox_key_suffix}"
                with row_cols[row_col_idx]:
                    if st.checkbox("選択", key=checkbox_key, label_visibility="collapsed"):
                        selected_indices.append(idx)
                row_col_idx += 1

            if group_columns:
                grouped_row = {}
                for key, value in row.items():
                    if isinstance(key, str) and " - " in key:
                        parent, child = key.split(" - ", 1)
                        grouped_row.setdefault(parent, {})[child] = value
                    else:
                        grouped_row[key] = value

                for group_name, group_content in grouped_row.items():
                    with row_cols[row_col_idx]:
                        if isinstance(group_content, dict):
                            for k, v in group_content.items():
                                st.markdown(f"**{k}**:")
                                st.html(v)
                        else:
                            self.render_format_cell_content(group_content)
                    row_col_idx += 1
            else:
                for i in range(len(row)):
                    with row_cols[row_col_idx]:
                        if i < start_content_col_idx:
                            st.html(row.iloc[i])
                        else:
                            self.render_format_cell_content(row.iloc[i])
                        row_col_idx += 1

        return df.loc[selected_indices] if display_checkbox and selected_indices else pd.DataFrame()

    def _display_dataframe_with_checkbox_grouped(self, df: pd.DataFrame, df_clickable: pd.DataFrame, start_idx: int = 2) -> pd.DataFrame:
        return self.display_dataframe(df, df_clickable, display_checkbox=True, group_columns=True, start_content_col_idx=start_idx)

    def _display_dataframe_with_checkbox(self, df: pd.DataFrame, df_clickable: pd.DataFrame, start_idx: int = 2) -> pd.DataFrame:
        return self.display_dataframe(df, df_clickable, display_checkbox=True, group_columns=False, start_content_col_idx=start_idx)

    def _display_dataframe(self, df: pd.DataFrame, start_idx: int = 1):
        return self.display_dataframe(df, display_checkbox=False, group_columns=False, start_content_col_idx=start_idx)

    def _display_dataframe_grouped(self, df: pd.DataFrame, start_idx: int = 1):
        return self.display_dataframe(df, display_checkbox=False, group_columns=True, start_content_col_idx=start_idx)

    def make_groups(self, df: pd.DataFrame, title: str, columns):
        new_cols = []
        for column in columns:
            new_col = f"{title} - {column}"
            df[new_col] = df[column]
            new_cols.append(new_col)
        df = df.drop(columns=columns)
        df = df[new_cols + [col for col in df.columns if col not in new_cols]]
        return df

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