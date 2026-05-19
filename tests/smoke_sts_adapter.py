import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.sts_database import STSDatabase
from src.services.sts_store_adapter import STSStoreAdapter
from src.models.app_models import ContractInfo, SystemInfo, DeliveryInfo


def main():
    with TemporaryDirectory() as td:
        p = Path(td) / "adapter_test.sts"
        db = STSDatabase(p)
        db.create_new()
        db.upsert_platform("AKINCI")
        db.upsert_user({"name": "Sistem", "role": "Varsayılan", "active": True})
        db.upsert_component({"name": "Kamera", "unit": "Adet", "active": True, "usage": 1})

        adapter = STSStoreAdapter(db)
        assert "AKINCI" in adapter.platform_names()

        users = adapter.load_users(active_only=False)
        assert isinstance(users, list) and users

        assert adapter._normalize_label("ANA SÖZLEŞME TOPLAMI") == "ana sozlesme toplami"

        tags, assignments = adapter.load_tag_snapshot()
        assert isinstance(tags, list)
        assert isinstance(assignments, dict)

        with adapter.batch_save():
            pass

        ci = ContractInfo(
            no="SOZ-001", user="Sistem", yi_yd="Yİ", contract_type="Ana Sözleşme",
            signature_date="2026-01-01", t0_date="2026-01-01", t0_months=12,
            completion_date="2026-12-31", status="Açık", note="Test içerik", platform="AKINCI",
        )
        systems = [
            SystemInfo(name="Sistem 1", components={"Kamera": 10}, t0_date="2026-01-01", t0_months=12,
                       completion_date="2026-12-31", status="Devam")
        ]
        deliveries = {
            "Sistem 1": [
                DeliveryInfo(name="Kabul 1", status="Kısmi", acceptance_date="2026-06-01", note="not",
                             planned={"Kamera": 10}, delivered={"Kamera": 4})
            ]
        }

        start_row = adapter.write_contract(ci, systems, deliveries)
        assert start_row is not None

        idx = adapter.build_contract_index()
        assert any(item.get("no") == "SOZ-001" for item in idx)

        ci2, systems2, deliveries2 = adapter.load_contract_structure("AKINCI", "SOZ-001")
        assert ci2 is not None
        assert systems2
        assert deliveries2.get("Sistem 1")

        res = adapter.delete_contract("AKINCI", "SOZ-001")
        assert res.get("deleted_rows") == 1
        assert not adapter.build_contract_index()

        db.close()

    print("smoke_sts_adapter: OK")


if __name__ == "__main__":
    main()
