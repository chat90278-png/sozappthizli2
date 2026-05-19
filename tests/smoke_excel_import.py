import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from openpyxl import Workbook
except Exception:
    print("smoke_excel_import: SKIP (openpyxl yok)")
    raise SystemExit(0)

from src.services.fast_excel_reader import FastExcelReader
from src.services.sts_database import STSDatabase

with TemporaryDirectory() as td:
    td = Path(td)
    xlsx = td / "legacy.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "KIZILELMA"
    for _ in range(1, 6):
        ws.append([""] * 12)
    ws.append(["K-001", "Sistem", "", "Ana Sözleşme", "GENEL", "Ana Sözleşme Toplamı", "İçerik", "", "", "", "2026-12-31", "Plan"])
    wb.save(xlsx)
    wb.close()

    db = STSDatabase(td / "out.sts")
    db.create_new()
    rep = FastExcelReader(xlsx).import_to_sts(db)
    assert rep["contracts"] > 0
    assert len(db.list_contracts()) > 0
print("smoke_excel_import: OK")
