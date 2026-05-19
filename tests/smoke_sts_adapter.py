import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from src.services.sts_database import STSDatabase
from src.services.sts_store_adapter import STSStoreAdapter
from src.models.app_models import ContractInfo


def main():
    with TemporaryDirectory() as td:
        p = Path(td) / "adapter_test.sts"
        db = STSDatabase(p)
        db.connect()
        db.init_schema()
        db.ensure_default_user()
        db.upsert_platform("AKINCI")
        db.upsert_component({"name":"Kamera","unit":"Adet","active":True,"usage":1})

        adapter = STSStoreAdapter(db)
        assert "AKINCI" in adapter.platform_names()

        users = adapter.load_users()
        assert isinstance(users, list) and users

        components = adapter.load_components()
        assert any(c.get("name") == "Kamera" for c in components)

        ci = ContractInfo(
            no="SOZ-001",
            user="Sistem",
            yi_yd="Yİ",
            contract_type="Ana Sözleşme",
            signature_date="2026-01-01",
            t0_date="2026-01-01",
            t0_months=12,
            completion_date="2026-12-31",
            status="Açık",
            note="Test içerik",
            platform="AKINCI",
        )
        systems = [{"system": "Sistem 1", "summary": "Sistem 1 Toplamı"}]
        deliveries = {"Sistem 1": [{"delivery": "Kabul 1", "component_counts": {"Kamera": (10, 4, 6)}}]}

        start_row = adapter.write_contract(ci, systems, deliveries)
        assert start_row is not None

        idx = adapter.build_contract_index()
        assert any(item.get("no") == "SOZ-001" for item in idx)

        ci2, systems2, deliveries2 = adapter.load_contract_structure("AKINCI", "SOZ-001")
        assert ci2 is not None
        assert getattr(ci2, "contract_id", None) is not None
        assert isinstance(systems2, list)
        assert isinstance(deliveries2, dict)

        res = adapter.delete_contract("AKINCI", "SOZ-001")
        assert res.get("deleted_rows") == 1

        db.close()

    print("smoke_sts_adapter: OK")


if __name__ == "__main__":
    main()