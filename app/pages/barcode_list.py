import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidgetItem, QHeaderView,
    QHBoxLayout, QMessageBox, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics
from datetime import datetime

# Local Imports
from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.standard_button import StandardButton
from components.sort_by_widget import SortByWidget
from components.generic_form_modal import GenericFormModal
from pages.barcode_editor import BarcodeEditorPage

# Repository
from server.repositories.mbarcd_repo import (
    fetch_all_mbarcd,
    fetch_mbarcd_by_pk,
    create_mbarcd,
    update_mbarcd,
    delete_mbarcd,
)

def _fetch_sticker_data() -> dict:
    try:
        from server.db import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT msstnm, msheig, mswidt, mspixh, mspixw
                  FROM barcodesap.mstckr
                 WHERE msdlfg <> '1'
                 ORDER BY msstnm
                """
            )
            result = {}
            for msstnm, msheig, mswidt, mspixh, mspixw in cur.fetchall():
                result[str(msstnm).strip()] = {
                    "h_in": float(msheig) if msheig is not None else 0.0,
                    "w_in": float(mswidt) if mswidt is not None else 0.0,
                    "h_px": int(mspixh)   if mspixh is not None else 0,
                    "w_px": int(mspixw)   if mspixw is not None else 0,
                }
            return result
        finally:
            conn.close()
    except Exception as e:
        print(f"[_fetch_sticker_data] {e}")
        return {}

# --- Design Tokens ---
COLORS = {
    "bg_main": "#F8FAFC",
    "link": "#6366F1",
    "status_green_bg": "#DCFCE7",
    "status_green_text": "#166534",
    "status_gray_bg": "#F1F5F9",
    "status_gray_text": "#475569",
    "border": "#E2E8F0"
}

VIEW_DETAIL_FIELDS = [
    ("Code",           0),
    ("Name",           1),
    ("Sticker Size",   2),
    ("Status",         3),
    ("Added By",       4),
    ("Added At",       5),
    ("Changed By",     6),
    ("Changed At",     7),
    ("Changed No",     8),
    ("Last Print By",  9),
    ("Last Print At", 10),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_date(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _dict_to_row(d: dict) -> tuple:
    sticker_size = d.get("sticker_name") or f"{d.get('h_in', '')} X {d.get('w_in', '')}"
    status = "DISPLAY" if d.get("dp_fg") == 1 else "NOT DISPLAY"

    changed_no = d.get("changed_no", 0) or 0
    has_been_edited = int(changed_no) > 0

    return (
        d.get("pk", ""),
        d.get("name", ""),
        sticker_size,
        status,
        d.get("added_by", "-"),
        _fmt_date(d.get("added_at")),
        d.get("changed_by", "-") if has_been_edited else "-",
        _fmt_date(d.get("changed_at")) if has_been_edited else "-",
        str(changed_no) if has_been_edited else "-",
        d.get("printed_by") or "-",
        _fmt_date(d.get("printed_at")),
    )


class BarcodeListPage(QWidget):
    _VIEW_LIST   = 0
    _VIEW_EDITOR = 1

    def __init__(self):
        super().__init__()
        self.all_data = []
        self.all_dicts = {}
        self.filtered_data = []
        self.current_page = 0
        self.page_size = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type = "CODE"
        self._last_search_text = ""
        self._sort_fields = []
        self._sort_directions = {}
        self.selected_row_data = None
        self.selected_row_dict = None
        self.current_user = "YOSAFAT.YACOB"

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._stack = QStackedWidget()
        root_layout.addWidget(self._stack)

        self._list_page = QWidget()
        self._stack.addWidget(self._list_page)
        self._editor_page = None

        self.init_ui()
        self._stack.setCurrentIndex(self._VIEW_LIST)
        self._ensure_layout_columns()
        self.load_data()

    # ------------------------------------------------------------------
    # Internal navigation
    # ------------------------------------------------------------------

    def _get_editor_page(self) -> BarcodeEditorPage:
        if self._editor_page is None:
            self._editor_page = BarcodeEditorPage()
            self._editor_page.design_saved.connect(self._on_editor_save)
            self._editor_page.back_btn.clicked.connect(self._show_list)
            self._stack.addWidget(self._editor_page)
        return self._editor_page

    def _show_list(self):
        self._stack.setCurrentIndex(self._VIEW_LIST)

    def _show_editor(self):
        if self._editor_page is not None:
            self._stack.setCurrentIndex(self._VIEW_EDITOR)

    def _ensure_layout_columns(self):
        conn = self._get_db_connection()
        if conn is None:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                ALTER TABLE barcodesap.mbarcd
                    ADD COLUMN IF NOT EXISTS mbusrm text,
                    ADD COLUMN IF NOT EXISTS mbitrm text
                """
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[_ensure_layout_columns] {e}")
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Editor save handler
    # ------------------------------------------------------------------

    def _on_editor_save(self, payload: dict):
        """
        Called when the editor emits design_saved.
        payload contains: pk, name, dp_fg, usrm, itrm,
                          sticker_name, w_px, h_px, h_in, w_in
        """
        pending = getattr(self, "_pending_new_design", None)

        if pending:
            # ── New design: validate pk then insert ────────────────────
            pk_from_editor = (payload.get("pk") or "").strip()
            if not pk_from_editor:
                QMessageBox.warning(
                    self, "Code Required",
                    "Please enter a Code in the General tab before saving."
                )
                return
            if not (payload.get("name") or "").strip():
                QMessageBox.warning(
                    self, "Name Required",
                    "Please enter a Name in the General tab before saving."
                )
                return
            if fetch_mbarcd_by_pk(pk_from_editor) is not None:
                QMessageBox.warning(
                    self, "Duplicate Code",
                    f"A barcode design with code '{pk_from_editor}' already exists."
                    "Please choose a different code."
                )
                return

            # Merge editor values into pending
            pending["pk"]           = pk_from_editor
            pending["sticker_name"] = payload.get("sticker_name") or pending.get("sticker_name")
            pending["w_px"]         = payload.get("w_px") or pending.get("w_px", 600)
            pending["h_px"]         = payload.get("h_px") or pending.get("h_px", 400)
            pending["w_in"]         = payload.get("w_in") or pending.get("w_in", 0.0)
            pending["h_in"]         = payload.get("h_in") or pending.get("h_in", 0.0)
            if payload.get("name"):
                pending["name"] = payload["name"]
            if payload.get("dp_fg") is not None:
                pending["dp_fg"] = payload["dp_fg"]

            self.on_barcode_added(pending)
            self._pending_new_design = None
            try:
                record = fetch_mbarcd_by_pk(pk_from_editor)
                if record:
                    self.all_dicts[pk_from_editor] = record
            except Exception:
                pass
            self._save_design_layout(payload, is_new=True)
        else:
            # ── Existing design: update sticker/dims + canvas layout ────
            self._save_design_layout(payload, is_new=False)

        self.load_data()
        self._show_list()

    def _save_design_layout(self, payload: dict, is_new: bool = False):
        # Use original_pk (the key that exists in DB) for WHERE clause.
        # payload["pk"] may have been edited by the user in the General tab.
        new_pk       = payload.get("pk", "").strip()
        original_pk  = payload.get("original_pk", new_pk).strip() or new_pk
        usrm         = payload.get("usrm", "[]")
        itrm         = payload.get("itrm", "{}")
        sticker_name = payload.get("sticker_name") or ""
        h_in         = float(payload.get("h_in") or 0)
        w_in         = float(payload.get("w_in") or 0)
        h_px         = int(payload.get("h_px") or 0)
        w_px         = int(payload.get("w_px") or 0)
        name         = payload.get("name", "")
        dp_fg        = payload.get("dp_fg")  # may be None — treated as "don't change"

        if not original_pk:
            return

        print(f"[_save_design_layout] original_pk={original_pk!r} new_pk={new_pk!r} name={name!r} dp_fg={dp_fg!r}")

        try:
            from server.repositories.mbarcd_repo import update_mbarcd_layout
            update_mbarcd_layout(
                pk=original_pk, new_pk=new_pk, usrm=usrm, itrm=itrm,
                sticker_name=sticker_name,
                h_in=h_in, w_in=w_in, h_px=h_px, w_px=w_px,
                is_new=is_new,
                name=name,
                dp_fg=dp_fg,
                user=self.current_user,
            )
            print(f"[_save_design_layout] pk={original_pk!r}  name={name!r}  dp_fg={dp_fg!r}  usrm={len(usrm)}B  itrm={len(itrm)}B")
        except (ImportError, TypeError):
            self._save_design_layout_direct(
                original_pk, usrm, itrm, is_new=is_new,
                sticker_name=sticker_name,
                h_in=h_in, w_in=w_in, h_px=h_px, w_px=w_px,
                name=name,
                dp_fg=dp_fg,
            )
        except Exception as e:
            print(f"[_save_design_layout] Skipped — {e}")

    def _save_design_layout_direct(self, pk: str, usrm: str, itrm: str, is_new: bool = False,
                                    sticker_name: str = "", h_in: float = 0.0, w_in: float = 0.0,
                                    h_px: int = 0, w_px: int = 0,
                                    name: str = "", dp_fg=None):
        conn = self._get_db_connection()
        if conn is None:
            print("[_save_design_layout_direct] No DB connection found — layout not saved.")
            return

        try:
            cur = conn.cursor()
            if is_new:
                cur.execute(
                    """
                    UPDATE barcodesap.mbarcd
                       SET mbusrm = %s,
                           mbitrm = %s,
                           mbstnm = %s,
                           mbheig = %s,
                           mbwidt = %s,
                           mbpixh = %s,
                           mbpixw = %s,
                           mbbrnm = CASE WHEN %s <> '' THEN %s ELSE mbbrnm END,
                           mbdpfg = CASE WHEN %s IS NOT NULL THEN %s ELSE mbdpfg END
                     WHERE mbbrcd = %s
                    """,
                    (usrm, itrm,
                     sticker_name or None,
                     h_in if h_in else None,
                     w_in if w_in else None,
                     h_px if h_px else None,
                     w_px if w_px else None,
                     name, name,
                     dp_fg, dp_fg,
                     pk),
                )
            else:
                cur.execute(
                    """
                    UPDATE barcodesap.mbarcd
                       SET mbusrm = %s,
                           mbitrm = %s,
                           mbstnm = %s,
                           mbheig = %s,
                           mbwidt = %s,
                           mbpixh = %s,
                           mbpixw = %s,
                           mbbrnm = CASE WHEN %s <> '' THEN %s ELSE mbbrnm END,
                           mbdpfg = CASE WHEN %s IS NOT NULL THEN %s ELSE mbdpfg END,
                           mbchno = mbchno + 1,
                           mbchby = %s,
                           mbchdt = NOW()
                     WHERE mbbrcd = %s
                    """,
                    (usrm, itrm,
                     sticker_name or None,
                     h_in if h_in else None,
                     w_in if w_in else None,
                     h_px if h_px else None,
                     w_px if w_px else None,
                     name, name,
                     dp_fg, dp_fg,
                     self.current_user,
                     pk),
                )
            conn.commit()
            print(f"[_save_design_layout_direct] Saved for pk={pk!r} name={name!r} dp_fg={dp_fg!r} sticker={sticker_name!r} (is_new={is_new})")
        except Exception as e:
            conn.rollback()
            print(f"[_save_design_layout_direct] Skipped — {e}")
        finally:
            conn.close()

    # -----------------------
    # Text wrapping helpers
    # -----------------------

    def _wrap_text(self, text: str, max_chars: int) -> str:
        s = "" if text is None else str(text)
        s = " ".join(s.split())
        if max_chars <= 0 or len(s) <= max_chars:
            return s

        words = s.split(" ")
        lines: list[str] = []
        current = ""
        for w in words:
            if not current:
                current = w
                continue
            if len(current) + 1 + len(w) <= max_chars:
                current += " " + w
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)
        return "\n".join(lines)

    def _row_line_count(self, row: int) -> int:
        max_lines = 1
        for c in range(self.table.columnCount()):
            it = self.table.item(row, c)
            if it is None:
                continue
            max_lines = max(max_lines, it.text().count("\n") + 1)
        return max_lines

    def init_ui(self):
        self._list_page.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        layout = QVBoxLayout(self._list_page)
        layout.setContentsMargins(40, 20, 40, 12)
        layout.setSpacing(0)

        enabled = ["Add", "Excel", "Refresh", "View Detail"]
        self.header = StandardPageHeader(
            title="Barcode Design",
            subtitle="Generate and manage enterprise-wide barcode assets.",
            enabled_actions=enabled
        )
        layout.addWidget(self.header)

        self.header.get_action_button("Refresh").clicked.connect(self.load_data)
        self.header.get_action_button("Add").clicked.connect(self.handle_add_action)
        self.header.get_action_button("Excel").clicked.connect(self.handle_export_action)
        self.header.get_action_button("Edit").clicked.connect(self.handle_edit_action)
        self.header.get_action_button("Delete").clicked.connect(self.handle_delete_action)
        self.header.get_action_button("View Detail").clicked.connect(self.handle_view_detail_action)

        layout.addSpacing(12)

        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        layout.addWidget(self.search_bar)
        layout.addSpacing(5)

        column_labels = [
            "CODE", "NAME", "STICKER SIZE", "STATUS",
            "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"
        ]
        self.table_comp = StandardTable(column_labels)
        self.table = self.table_comp.table

        self.table.itemSelectionChanged.connect(self.on_row_selection_changed)

        header_obj = self.table.horizontalHeader()
        header_obj.setSectionResizeMode(QHeaderView.Interactive)
        header_obj.setSectionResizeMode(3, QHeaderView.Fixed)
        header_obj.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header_obj.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header_obj.setSectionResizeMode(6, QHeaderView.Fixed)
        header_obj.setSectionResizeMode(7, QHeaderView.ResizeToContents)

        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(1, 360)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(6, 120)
        self.table.setColumnWidth(8, 100)

        self.sort_bar = SortByWidget(self.table)
        self.sort_bar.sortChanged.connect(self.on_sort_changed)
        layout.addWidget(self.sort_bar)
        layout.addSpacing(8)

        layout.addWidget(self.table_comp)
        layout.addSpacing(16)

        self.pagination = self.table_comp.pagination
        self.pagination.pageChanged.connect(self.on_page_changed)
        self.pagination.pageSizeChanged.connect(self.on_page_size_changed)

        self.sort_bar.initialize_default_sort()
        self._update_selection_dependent_state(False)

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _update_selection_dependent_state(self, enabled: bool):
        for label in ("Edit", "Delete", "View Detail"):
            btn = self.header.get_action_button(label)
            if btn:
                btn.setEnabled(enabled)

    def on_row_selection_changed(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            item = self.table.item(row, 0)
            if item:
                self.selected_row_data = item.data(Qt.UserRole)
                pk = self.selected_row_data[0] if self.selected_row_data else None
                self.selected_row_dict = self.all_dicts.get(pk)
                self._update_selection_dependent_state(True)
        else:
            self.selected_row_data = None
            self.selected_row_dict = None
            self._update_selection_dependent_state(False)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def load_data(self):
        try:
            records = fetch_all_mbarcd()
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load barcode data:\n{e}")
            records = []

        self.all_dicts = {r["pk"]: r for r in records}
        self.all_data = [_dict_to_row(r) for r in records]
        self._apply_filter_and_reset_page()

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        data = self.filtered_data if self.filtered_data is not None else []

        total = len(data)
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_data = data[start_idx:end_idx]

        for r, row_data in enumerate(page_data):
            self.table.insertRow(r)

            for c in range(3):
                raw = "" if row_data[c] is None else str(row_data[c])
                if c == 1:
                    txt = self._wrap_text(raw, max_chars=32)
                elif c == 0:
                    txt = self._wrap_text(raw, max_chars=18)
                else:
                    txt = raw

                item = QTableWidgetItem(txt)
                if c == 0:
                    item.setForeground(QColor(COLORS["link"]))
                    item.setData(Qt.UserRole, row_data)
                self.table.setItem(r, c, item)

            status_val = str(row_data[3])
            status_item = QTableWidgetItem(status_val)
            status_item.setTextAlignment(Qt.AlignCenter)
            if "NOT" in status_val:
                status_item.setForeground(QColor(COLORS["status_gray_text"]))
            else:
                status_item.setForeground(QColor(COLORS["status_green_text"]))
            self.table.setItem(r, 3, status_item)

            self.table.setItem(r, 4, QTableWidgetItem(str(row_data[4])))
            self.table.setItem(r, 5, QTableWidgetItem(str(row_data[5])))
            self.table.setItem(r, 6, QTableWidgetItem(str(row_data[6])))
            self.table.setItem(r, 7, QTableWidgetItem(str(row_data[7])))

            changed_no_item = QTableWidgetItem(str(row_data[8]))
            changed_no_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 8, changed_no_item)

            metrics = QFontMetrics(self.table.font())
            lines = self._row_line_count(r)
            base_padding = 12
            self.table.setRowHeight(r, max(28, lines * metrics.lineSpacing() + base_padding))

        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

        self.table.setSortingEnabled(False)

        has_prev = self.current_page > 0
        has_next = end_idx < total
        start_human = 0 if total == 0 else start_idx + 1
        end_human = 0 if total == 0 else end_idx
        self.pagination.update(
            start=start_human,
            end=end_human,
            total=total,
            has_prev=has_prev,
            has_next=has_next,
            current_page=self.current_page,
            page_size=self.page_size,
            available_page_sizes=self.available_page_sizes,
        )

    # ------------------------------------------------------------------
    # Shared modal opener
    # ------------------------------------------------------------------

    def _open_view_detail_modal(self, row_data: tuple):
        fields = [
            (label, str(row_data[i]) if i < len(row_data) and row_data[i] is not None else "")
            for label, i in VIEW_DETAIL_FIELDS
        ]
        modal = GenericFormModal(
            title="Barcode Detail",
            subtitle="Full details for the selected barcode record.",
            fields=fields,
            parent=self,
            mode="view"
        )
        modal.exec()

    # ------------------------------------------------------------------
    # Filter / sort
    # ------------------------------------------------------------------

    def filter_table(self, filter_type, search_text):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self) -> None:
        query = (self._last_search_text or "").lower().strip()

        headers = self.table_comp.headers()
        header_to_index = {h: i for i, h in enumerate(headers)}
        col_index = header_to_index.get(self._last_filter_type, 0)

        if not query:
            self.filtered_data = list(self.all_data)
        else:
            out = []
            for row in self.all_data:
                if col_index >= len(row):
                    continue
                val = "" if row[col_index] is None else str(row[col_index])
                if query in val.lower():
                    out.append(row)
            self.filtered_data = out

        self._apply_sort()
        self.current_page = 0
        self.render_page()

    def on_sort_changed(self, fields: list[str], field_directions: dict):
        self._sort_fields = fields or []
        self._sort_directions = field_directions or {}
        self._apply_filter_and_reset_page()

    def _apply_sort(self):
        if not self._sort_fields or not self.filtered_data:
            return

        headers = self.table_comp.headers()
        header_to_index = {h: i for i, h in enumerate(headers)}

        for field in reversed(self._sort_fields):
            direction = self._sort_directions.get(field, "asc")
            reverse = (direction == "desc")
            idx = header_to_index.get(field)
            if idx is None:
                continue
            self.filtered_data.sort(
                key=lambda row, i=idx: self._get_sort_value(row, i),
                reverse=reverse
            )

    def _get_sort_value(self, row, idx):
        val = row[idx] if idx < len(row) else ""
        str_val = "" if val is None else str(val)
        numeric_cols = ["CHANGED NO"]
        header = self.table_comp.headers()[idx] if idx < len(self.table_comp.headers()) else ""
        if header in numeric_cols:
            try:
                return float(str_val.replace(",", ""))
            except ValueError:
                return 0
        return str_val.lower()

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def on_page_changed(self, page_action: int) -> None:
        total = len(self.filtered_data) if self.filtered_data is not None else 0
        total_pages = (total + self.page_size - 1) // self.page_size
        if total_pages <= 0:
            self.current_page = 0
            self.render_page()
            return

        if page_action == -1:
            self.current_page = max(0, self.current_page - 1)
        elif page_action == 1:
            self.current_page = min(total_pages - 1, self.current_page + 1)
        else:
            self.current_page = max(0, min(int(page_action), total_pages - 1))

        self.render_page()

    def on_page_size_changed(self, new_size: int) -> None:
        self.page_size = new_size
        self.current_page = 0
        self.render_page()

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def handle_add_action(self):
        # Open the editor directly with a blank form — no modal needed
        blank = {
            "pk":           "",
            "name":         "",
            "sticker_name": "",
            "h_in":         0.0,
            "w_in":         0.0,
            "h_px":         400,
            "w_px":         600,
            "dp_fg":        1,
            "db_fg":        0,
            "flag": 0, "cont": 0, "print_": 0, "print_flag": 0, "ad_fg": 0,
        }
        self._pending_new_design = blank
        self._get_editor_page().reset_for_new(blank)
        self._show_editor()

    def handle_edit_action(self):
        if not self.selected_row_data:
            QMessageBox.warning(self, "Edit", "Please select a row to edit.")
            return

        pk = self.selected_row_data[0]
        row_dict = dict(self.all_dicts.get(pk) or {})

        try:
            from server.repositories.mbarcd_repo import fetch_mbarcd_layout
            layout = fetch_mbarcd_layout(pk)
            if layout:
                row_dict["usrm"] = layout.get("usrm", "")
                row_dict["itrm"] = layout.get("itrm", "")
        except ImportError:
            try:
                conn = self._get_db_connection()
                if conn:
                    try:
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT mbusrm, mbitrm FROM barcodesap.mbarcd "
                            "WHERE mbbrcd = %s",
                            (pk,),
                        )
                        row = cur.fetchone()
                        if row:
                            row_dict["usrm"] = row[0] or ""
                            row_dict["itrm"] = row[1] or ""
                    finally:
                        conn.close()
            except Exception as e:
                print(f"[handle_edit_action] Could not fetch layout columns: {e}")
        except Exception as e:
            print(f"[handle_edit_action] Could not fetch layout columns: {e}")

        self._get_editor_page().load_design(self.selected_row_data, row_dict)
        self._show_editor()

    def _get_db_connection(self):
        for mod_path in ("server.db", "db", "database", "server.database", "core.db"):
            try:
                import importlib
                mod = importlib.import_module(mod_path)
                for fn_name in ("get_connection", "get_conn", "connect", "get_db"):
                    if hasattr(mod, fn_name):
                        return getattr(mod, fn_name)()
            except (ImportError, Exception):
                continue
        return None

    def on_barcode_added(self, form_data: dict):
        try:
            created_pk = create_mbarcd(
                pk=form_data["pk"],
                name=form_data["name"],
                h_in=form_data["h_in"],
                w_in=form_data["w_in"],
                h_px=form_data["h_px"],
                w_px=form_data["w_px"],
                company=form_data.get("company"),
                type_=form_data.get("type_"),
                sticker_name=form_data.get("sticker_name"),
                flag=form_data.get("flag", 0),
                cont=form_data.get("cont", 0),
                print_=form_data.get("print_", 0),
                print_flag=form_data.get("print_flag", 0),
                db_fg=form_data.get("db_fg", 0),
                ad_fg=form_data.get("ad_fg", 0),
                dp_fg=form_data.get("dp_fg", 0),
            )
        except Exception as e:
            QMessageBox.critical(self, "Create Error", f"Failed to create barcode:\n{e}")
            return

        self.load_data()
        QMessageBox.information(self, "Success", f"Barcode '{created_pk}' has been created successfully!")

    def handle_export_action(self):
        import openpyxl
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "barcode.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Barcode"

        headers = [
            "CODE", "NAME", "STICKER SIZE", "STATUS",
            "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT",
            "CHANGED NO", "LAST PRINT BY", "LAST PRINT AT"
        ]
        ws.append(headers)

        for row in self.filtered_data:
            ws.append([str(val) if val is not None else "" for val in row])

        wb.save(path)
        QMessageBox.information(
            self, "Export Complete",
            f"Exported {len(self.filtered_data)} records to:\n{path}"
        )

    def handle_view_detail_action(self):
        if not self.selected_row_data:
            return
        self._open_view_detail_modal(self.selected_row_data)

    def on_barcode_edited(self, form_data: dict):
        if not self.selected_row_dict:
            QMessageBox.warning(self, "Edit", "No record selected for editing.")
            return

        old_pk = self.selected_row_dict["pk"]
        old_changed_no = self.selected_row_dict.get("changed_no", 0)

        try:
            update_mbarcd(
                old_pk=old_pk,
                new_pk=form_data.get("new_pk", old_pk),
                name=form_data["name"],
                h_in=form_data["h_in"],
                w_in=form_data["w_in"],
                h_px=form_data["h_px"],
                w_px=form_data["w_px"],
                old_changed_no=old_changed_no,
                company=form_data.get("company"),
                type_=form_data.get("type_"),
                sticker_name=form_data.get("sticker_name"),
                user=self.current_user,
            )
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Failed to update barcode:\n{e}")
            return

        self.load_data()
        QMessageBox.information(self, "Success", f"Barcode '{old_pk}' has been updated successfully!")

    def handle_delete_action(self):
        if not self.selected_row_data:
            QMessageBox.warning(self, "Delete", "Please select a row to delete.")
            return

        code_to_delete = self.selected_row_data[0]

        reply = QMessageBox.question(
            self,
            "Delete Confirmation",
            f"Are you sure you want to delete barcode '{code_to_delete}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                delete_mbarcd(pk=code_to_delete, user=self.current_user)
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete barcode:\n{e}")
                return

            self.selected_row_data = None
            self.selected_row_dict = None
            self.load_data()
            QMessageBox.information(
                self, "Deleted",
                f"Barcode '{code_to_delete}' has been deleted successfully!"
            )