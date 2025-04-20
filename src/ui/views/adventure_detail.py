import streamlit as st

from ..views.base import BaseView

class AdventureDetailView(BaseView):
    def render(self, area_name: str, adventure_name: str):
        st.title(f"{area_name} - {adventure_name} 詳細")

        adventures_df = self.load_area_csv(area_name)
        is_rendered_adv = self._render_row(adventures_df, adventure_name, "冒険サマリー", area_name)

        log_check_df = self.load_check_csv(area_name, "log")
        is_rendered_logcheck = self._render_row(log_check_df, adventure_name, "ログチェック")

        location_check_df = self.load_check_csv(area_name, "loc")
        is_rendered_loccheck = self._render_row(location_check_df, adventure_name, "位置情報チェック")
        
        if not is_rendered_adv and not is_rendered_logcheck and not is_rendered_loccheck:
            st.warning("エリアのデータが存在しません。")

        self._render_adventure_content(area_name, adventure_name)

        if st.button("戻る"):
            st.query_params.update({"area": area_name, "adv": ""})
            st.rerun()

    def _render_row(self, df, adventure_name: str, info_title: str, area_name: str = None) -> bool:
        if df is not None:
            adventure_row = df[df["冒険名"] == adventure_name]
            if not adventure_row.empty:
                st.markdown(f"**{info_title}**")
                if area_name:
                    clickable_adv_row = self._make_adventures_clickable(adventure_row, area_name)
                    clickable_adv_row = self.make_groups(clickable_adv_row, "冒険", ["冒険名", "次の冒険", "前の冒険"])
                    self._display_dataframe_grouped(clickable_adv_row, start_idx=1)
                else:
                    self._display_dataframe(adventure_row)
                return True
            else:
                st.warning(f"{adventure_name}の{info_title}は見つかりません。")
        return False


    def _render_adventure_content(self, area_name: str, adventure_name: str):
        st.markdown("**冒険詳細 (テキストファイル)**")
        adventure_path = self.file_handler.get_adventure_path(area_name, adventure_name)
        location_path = self.file_handler.get_location_path(area_name, adventure_name)

        content = self.read_text(adventure_path)
        location = self.read_text(location_path)

        if content and location:
            numbered_content = self._create_numbered_content(content, location)
            st.text(numbered_content)
        elif content and not location:
            st.warning(f"{adventure_name}の位置情報が存在しません。")
            numbered_content = self._create_numbered_content(content)
            st.text(numbered_content)
        else:
            st.warning(f"{adventure_name}の冒険テキストが存在しません。")

    def _create_numbered_content(self, content: str, location: str = None) -> str:
        if location is None:
            return "\n".join(
                f"{i+1}. {line}" 
                for i, line in enumerate(content.splitlines())
            )
        else:
            return "\n".join(
                f"{i+1}. [{loc}] {line}" 
                for i, (line, loc) in enumerate(zip(
                    content.splitlines(), 
                    location.splitlines()
                ))
            )
