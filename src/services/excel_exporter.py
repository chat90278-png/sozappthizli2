from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from src.services.sts_database import STSDatabase


def export_sts_to_excel(db: STSDatabase, output_path: Path, progress_cb=None):
    wb = Workbook()
    wb.remove(wb.active)
    platforms = db.list_platforms() or ["TumSozlesmeler"]
    total = max(len(platforms), 1)
    for i, platform in enumerate(platforms, start=1):
        ws = wb.create_sheet(title=str(platform)[:31] or "Platform")
        headers = ["No", "Kullanıcı", "Tür", "Durum", "Tamamlanma", "İçerik"]
        ws.append(headers)
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F4E78")
        for r in db.list_contracts(platform):
            full = db.get_contract(int(r["id"])) or {}
            ws.append([r.get("no", ""), r.get("user", ""), r.get("contract_type", ""), r.get("status", ""), r.get("completion", ""), full.get("content", "")])
        if progress_cb:
            progress_cb(int(i * 100 / total), f"Excel'e aktarılıyor: {platform}")
    wb.save(str(output_path))
