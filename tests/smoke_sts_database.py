import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pathlib import Path
from tempfile import TemporaryDirectory

from src.models.app_models import ContractInfo, DeliveryInfo, SystemInfo
from src.services.sts_database import STSDatabase

with TemporaryDirectory() as td:
    db = STSDatabase(Path(td) / "smoke.sts")
    db.create_new()
    db.upsert_platform("KIZILELMA")
    db.upsert_user({"name": "Sistem", "role": "Varsayılan", "active": True})
    db.upsert_component({"name": "Motor", "version": "v1", "unit": "Adet", "active": True, "usage": 1})
    db.upsert_tag({"name": "Kritik", "color": "#FF0000", "kind": "MANUAL"})
    ci = ContractInfo(no="K-001", platform="KIZILELMA", user="Sistem", yi_yd="Yİ", contract_type="Ana Sözleşme", signature_date="2026-01-01", t0_date="2026-01-01", t0_months=12, completion_date="2026-12-31")
    sid = SystemInfo(name="SYS", components={"Motor": 1})
    did = DeliveryInfo(name="Teslim", status="Plan", acceptance_date="2026-06-01", note="", planned={}, delivered={})
    cid = db.upsert_contract(ci, [sid], {"SYS": [did]})
    db.set_contract_tags(cid, ["Kritik"])
    assert len(db.list_platforms()) == 1
    assert len(db.search_contracts("K-001")) == 1
    dci, systems, deliveries = db.get_contract_detail(cid)
    assert dci and dci.no == "K-001"
    assert len(systems) == 1
    assert len(deliveries.get("SYS", [])) == 1
    db.delete_contract(cid)
    assert len(db.list_contracts("KIZILELMA")) == 0
print("smoke_sts_database: OK")
