from __future__ import annotations

import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Tuple

from openpyxl import load_workbook

from src.config.app_config import BASE_HEADERS, TAG_HEADERS, TAG_KIND_ASSIGN, TAG_SHEET, USERS_SHEET, COMP_SHEET
from src.domain.constants import CORE_SHEETS, DATA_START_ROW
from src.models.app_models import ContractInfo
from src.workers.excel_workers import is_system_sheet_name, normalize_sheet_name, safe_sheet_name


class FastExcelReader:
    def __init__(self, excel_path: Path):
        self.excel_path = Path(excel_path)
        self.wb = None

    def open_workbook(self):
        if self.wb is None:
            self.wb = load_workbook(self.excel_path, read_only=True, data_only=True, keep_links=False)
        return self.wb

    def close_workbook(self):
        if self.wb is not None:
            self.wb.close()
            self.wb = None

    def _to_iso(self, v) -> str:
        if v is None:
            return ""
        if isinstance(v, datetime):
            return v.date().isoformat()
        if isinstance(v, date):
            return v.isoformat()
        s = str(v).strip()
        return s

    def platform_names(self) -> list[str]:
        wb = self.open_workbook()
        excluded = {normalize_sheet_name(x) for x in CORE_SHEETS}
        extra = {"anasayfa", "kullanicilar", "etiketler", "log", "config", "konfigurasyon", "logo", "logolar", "sistemtipleri", "bilesenler", "bilesen"}
        out = []
        for ws in wb.worksheets:
            title = str(ws.title or "")
            n = normalize_sheet_name(title)
            if getattr(ws, "sheet_state", "visible") != "visible":
                continue
            if title.startswith("_") or n.startswith("_"):
                continue
            if is_system_sheet_name(title):
                continue
            if n in excluded or n in extra:
                continue
            out.append(title)
        return out

    def load_tags_map(self) -> dict:
        wb = self.open_workbook()
        out: Dict[Tuple[str, str, str], List[str]] = {}
        tag_defs: List[dict] = []
        if TAG_SHEET not in wb.sheetnames:
            return {"tag_defs": tag_defs, "assignments": out}
        ws = wb[TAG_SHEET]
        for ridx, row_data in enumerate(ws.iter_rows(min_row=2, max_col=len(TAG_HEADERS), values_only=True), start=2):
            try:
                kind = str((row_data[0] if len(row_data) > 0 else "") or "").strip().upper()
                name = str((row_data[1] if len(row_data) > 1 else "") or "").strip()
                color = str((row_data[3] if len(row_data) > 3 else "") or "").strip() or "#3B82F6"
                platform = safe_sheet_name(str((row_data[5] if len(row_data) > 5 else "") or "").strip())
                no = str((row_data[6] if len(row_data) > 6 else "") or "").strip()
                ctype = str((row_data[7] if len(row_data) > 7 else "") or "").strip()
                if name:
                    tag_defs.append({"name": name, "color": color, "kind": kind or "MANUAL", "source_row": ridx})
                if kind in {"ASSIGN", TAG_KIND_ASSIGN} and name and platform and no:
                    out.setdefault((platform, no, ctype), []).append(name)
            except Exception:
                continue
        return {"tag_defs": tag_defs, "assignments": out}

    def load_users(self) -> list[dict]:
        wb = self.open_workbook()
        if USERS_SHEET not in wb.sheetnames:
            return []
        ws = wb[USERS_SHEET]
        items = []
        for row in ws.iter_rows(min_row=2, max_col=6, values_only=True):
            name = str((row[0] if len(row) > 0 else "") or "").strip()
            if not name:
                continue
            role = str((row[1] if len(row) > 1 else "") or "").strip()
            active_raw = (row[2] if len(row) > 2 else True)
            active = str(active_raw).strip().lower() not in {"0", "false", "hayir", "pasif"}
            items.append({"name": name, "role": role, "active": active, "payload_json": {"raw": list(row)}})
        return items

    def load_components(self) -> list[dict]:
        wb = self.open_workbook()
        if COMP_SHEET not in wb.sheetnames:
            return []
        ws = wb[COMP_SHEET]
        items = []
        for row in ws.iter_rows(min_row=2, max_col=8, values_only=True):
            name = str((row[0] if len(row) > 0 else "") or "").strip()
            if not name:
                continue
            version = str((row[1] if len(row) > 1 else "") or "").strip()
            unit = str((row[2] if len(row) > 2 else "") or "").strip() or "Adet"
            usage = float((row[3] if len(row) > 3 and row[3] is not None else 1) or 1)
            active_raw = (row[4] if len(row) > 4 else True)
            active = str(active_raw).strip().lower() not in {"0", "false", "hayir", "pasif"}
            items.append({"name": name, "version": version, "unit": unit, "usage": usage, "active": active, "payload_json": {"raw": list(row)}})
        return items

    def build_contract_index(self, progress_cb=None) -> list[dict]:
        wb = self.open_workbook()
        tags_map = self.load_tags_map().get("assignments", {})
        platforms = self.platform_names()
        rows = []
        total = max(len(platforms), 1)
        for i, platform in enumerate(platforms, start=1):
            if progress_cb:
                progress_cb(40 + int(i * 45 / total), f"{platform} aktarılıyor... ({i}/{total})")
            ws = wb[platform]
            p = safe_sheet_name(platform)
            for ridx, row_data in enumerate(ws.iter_rows(min_row=DATA_START_ROW, max_col=len(BASE_HEADERS), values_only=True), start=DATA_START_ROW):
                try:
                    no = str((row_data[0] if len(row_data) > 0 else "") or "").strip()
                    user = str((row_data[1] if len(row_data) > 1 else "") or "").strip()
                    ctype = str((row_data[3] if len(row_data) > 3 else "") or "").strip()
                    activity = str((row_data[4] if len(row_data) > 4 else "") or "").strip().upper()
                    delivery = str((row_data[5] if len(row_data) > 5 else "") or "").strip().lower()
                    content = str((row_data[6] if len(row_data) > 6 else "") or "").strip()
                    completion = self._to_iso(row_data[10] if len(row_data) > 10 else "")
                    status = str((row_data[11] if len(row_data) > 11 else "") or "").strip()
                    if not no:
                        continue
                    if activity != "GENEL" or "ana sözleşme" not in delivery.replace("sozlesme", "sözleşme"):
                        continue
                    is_main = normalize_sheet_name(ctype) == normalize_sheet_name("Ana Sözleşme")
                    tags = tags_map.get((p, no, ctype), [])
                    item = {
                        "platform": p, "no": no, "contract_no": no, "user": user, "user_name": user,
                        "type": ctype, "contract_type": ctype, "type_display": ctype if is_main else f"↳ {ctype}",
                        "link": "Ana Sözleşme" if is_main else "Ana sözleşmeye bağlı SD", "status": status,
                        "completion_date": completion, "content": content, "row": ridx, "start_row": ridx,
                        "is_main": is_main, "tags": tags,
                    }
                    item["search_text"] = " ".join(str(item.get(k, "") or "") for k in ["platform", "no", "user", "contract_type", "status", "completion_date", "content"]).lower()
                    rows.append(item)
                except Exception:
                    continue
        return rows

    def load_contract_detail(self, platform: str, contract_no: str, start_row: int | None = None) -> tuple:
        # TODO: read_only modda detay blok parse'i geliştirilir.
        return None, [], {}

    def import_to_sts(self, db, progress_cb=None) -> dict:
        from datetime import datetime
        report = {"platforms": 0, "users": 0, "components": 0, "tags": 0, "contracts": 0, "systems": 0, "deliveries": 0, "errors": []}
        try:
            if progress_cb: progress_cb(5, "Excel açılıyor...")
            self.open_workbook()
            db.init_schema()
            db.set_meta("imported_from_excel_path", str(self.excel_path))
            db.set_meta("imported_at", datetime.utcnow().isoformat(timespec="seconds"))
            db.set_meta("importer_version", "2.0-fast-import")
            stat = self.excel_path.stat()
            db.set_meta("source_excel_size", stat.st_size)
            db.set_meta("source_excel_mtime", int(stat.st_mtime))

            if progress_cb: progress_cb(12, "Platformlar okunuyor...")
            platforms = self.platform_names()
            for p in platforms:
                db.upsert_platform(safe_sheet_name(p))
            report["platforms"] = len(platforms)

            if progress_cb: progress_cb(20, "Kullanıcılar aktarılıyor...")
            users = self.load_users()
            if users:
                for u in users: db.upsert_user(u)
            else:
                db.upsert_user({"name": "Sistem", "role": "Varsayılan", "active": True})
                users = [{"name": "Sistem"}]
            report["users"] = len(users)

            if progress_cb: progress_cb(28, "Bileşenler aktarılıyor...")
            components = self.load_components()
            for c in components: db.upsert_component(c)
            report["components"] = len(components)

            if progress_cb: progress_cb(34, "Etiketler aktarılıyor...")
            tmap = self.load_tags_map()
            tag_defs = tmap.get("tag_defs", [])
            assignments = tmap.get("assignments", {})
            for t in tag_defs: db.upsert_tag(t)
            report["tags"] = len(tag_defs)

            if progress_cb: progress_cb(40, "Sözleşmeler okunuyor...")
            rows = self.build_contract_index(progress_cb=progress_cb)
            for it in rows:
                try:
                    payload = dict(it)
                    payload.update({"source_platform": it.get("platform"), "source_start_row": it.get("start_row"), "source_contract_no": it.get("no"), "source_imported_at": datetime.utcnow().isoformat(timespec="seconds")})
                    it2 = dict(it); it2["payload_json"] = payload
                    cid = db.upsert_contract_from_dict(it2)
                    tags = list(it.get("tags") or assignments.get((it.get("platform"), it.get("no"), it.get("contract_type", "")), []))
                    db.set_contract_tags(cid, tags)
                    report["contracts"] += 1
                except Exception as exc:
                    report["errors"].append(f"contract:{it.get('platform')}/{it.get('no')} -> {exc}")

            if progress_cb: progress_cb(94, "Veritabanı optimize ediliyor...")
            db.add_log("excel_import_finished", "database", str(db.path), "Excel dosyası STS veritabanına aktarıldı", payload=report)
            db.vacuum()
            if progress_cb: progress_cb(100, "Aktarım tamamlandı.")
            return report
        except Exception as exc:
            raise RuntimeError(f"Excel STS aktarımı başarısız: {exc}\n{traceback.format_exc()}")
        finally:
            self.close_workbook()
