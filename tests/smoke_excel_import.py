import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from openpyxl import Workbook
except Exception:
    print('smoke_excel_import: SKIP (openpyxl yok)')
    raise SystemExit(0)

from src.services.fast_excel_reader import FastExcelReader
from src.services.sts_database import STSDatabase

with TemporaryDirectory() as td:
    td=Path(td)
    x=td/'legacy.xlsx'
    wb=Workbook(); ws=wb.active; ws.title='AKINCI'
    ws['A4']='Sözleşme Adı'; ws['O4']='HAVA ARACI'; ws['R4']='YKI -SABİT'
    ws['O5']='Teslim Edilecek'; ws['P5']='Teslim Edilen'; ws['Q5']='Kalan'
    ws['R5']='Teslim Edilecek'; ws['S5']='Teslim Edilen'; ws['T5']='Kalan'
    ws.append([]); ws.append([]); ws.append([]); ws.append([]); ws.append([])
    ws.append(['A-1','Sistem','Yİ','Ana Sözleşme','GENEL','Ana Sözleşme Toplamı','İçerik','2026-01-01','2026-01-01',12,'2026-12-31','Plan','','',10,2,8,4,1,3])
    ws.append(['A-1','Sistem','Yİ','Ana Sözleşme','Sistem 1','Sistem 1 Toplamı','','2026-01-01','2026-01-01',12,'2026-12-31','Plan','','',10,2,8,4,1,3])
    ws.append(['A-1','Sistem','Yİ','Ana Sözleşme','Sistem 1','Kabul 1','','2026-01-01','2026-01-01',12,'2026-12-31','Plan','2026-06-01','',2,2,0,1,1,0])
    wb.save(x); wb.close()
    db=STSDatabase(td/'out.sts'); db.create_new()
    rep=FastExcelReader(x).import_to_sts(db)
    assert rep['contracts'] > 0 and rep['contract_rows'] > 0 and rep['row_components'] > 0
print('smoke_excel_import: OK')
