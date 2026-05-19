import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.sts_database import STSDatabase

with TemporaryDirectory() as td:
    db = STSDatabase(Path(td) / "smoke.sts")
    db.create_new()
    db.upsert_platform("AKINCI")
    db.upsert_user({"name":"Sistem","role":"Varsayılan","active":True})
    db.upsert_component({"name":"HAVA ARACI","unit":"Adet","active":True,"usage":1})
    header={"platform":"AKINCI","contract_no":"A-1","user_name":"Sistem","contract_type":"Ana Sözleşme","status":"Plan","content":"İçerik","activity_name":"GENEL","delivery_acceptance_name":"Ana Sözleşme Toplamı","signed_date":"2026-01-01","t0_date":"2026-01-01","t0_months":12,"termin_date":"2026-12-31","acceptance_date":"","note":""}
    rows=[
      {**header,"source_row":6,"row_kind":"contract_total","components":[{"name":"HAVA ARACI","required":10,"delivered":2,"remaining":8}]},
      {**header,"source_row":7,"row_kind":"system_total","activity_name":"Sistem 1","delivery_acceptance_name":"Sistem 1 Toplamı","components":[{"name":"HAVA ARACI","required":10,"delivered":2,"remaining":8}]},
      {**header,"source_row":8,"row_kind":"acceptance","activity_name":"Sistem 1","delivery_acceptance_name":"Kabul 1","acceptance_date":"2026-06-01","components":[{"name":"HAVA ARACI","required":2,"delivered":2,"remaining":0}]},
    ]
    cid=db.upsert_contract_from_excel_block(header, rows)
    assert len(db.list_contracts("AKINCI")) == 1
    ci, systems, deliveries = db.get_contract_detail(cid)
    assert ci is not None and systems is not None and deliveries is not None
    assert db.count_contract_rows() > 0
    assert db.count_contract_row_components() > 0
    db.delete_contract(cid)
    assert len(db.list_contracts("AKINCI")) == 0
print('smoke_sts_database: OK')
