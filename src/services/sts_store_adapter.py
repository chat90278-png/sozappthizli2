from __future__ import annotations

from contextlib import contextmanager
import getpass


class STSStoreAdapter:
    def __init__(self, db):
        self.db = db
        self.path = db.path
        self.wb = None

    def platform_names(self): return self.db.list_platforms()
    def load_users(self): return self.db.list_users()
    def write_users(self, users_payload, actor="Sistem"):
        for u in users_payload or []: self.db.upsert_user(dict(u or {}))
    def load_components(self): return self.db.list_components()
    def write_components(self, components, actor="Sistem"):
        for c in components or []:
            payload = c if isinstance(c, dict) else getattr(c, "__dict__", {})
            self.db.upsert_component(dict(payload or {}))
    def load_tags(self): return self.db.list_tags()
    def all_contract_tags_map(self):
        out = {}
        for c in self.db.list_contracts():
            out[(c.get("platform",""), c.get("no",""), c.get("type",""))] = list(c.get("tags") or [])
        return out
    def build_contract_index(self): return self.db.list_contracts()
    def list_main_contracts(self, platform, tags_map=None): return self.db.list_contracts(platform)
    def load_contract_structure(self, platform, contract_no, start_row=None):
        row = self.db.get_contract_by_key(platform, contract_no, "", start_row=start_row)
        if not row: return None, [], {}
        cid = int(row.get("id") or 0)
        ci, systems, deliveries = self.db.get_contract_detail(cid)
        if ci is not None:
            setattr(ci, "contract_id", cid)
        return ci, systems, deliveries
    def write_contract(self, ci, systems, deliveries, old_contract_no=None, old_start_row=None):
        return self.db.upsert_contract(ci, systems, deliveries, old_contract_id=(int(old_start_row or 0) or None))
    def delete_contract(self, platform, contract_no, start_row=None, actor=None, progress_cb=None):
        row = self.db.get_contract_by_key(platform, contract_no, "", start_row=start_row)
        cid = int((row or {}).get("id") or (start_row or 0) or 0)
        if cid: self.db.delete_contract(cid)
        return {"platform": platform, "contract_no": contract_no, "start_row": start_row or cid, "end_row": start_row or cid, "deleted_rows": 1}
    def save(self): return None
    def reload_from_disk(self): return None
    @contextmanager
    def batch_save(self):
        yield self
    def flush_pending_styles(self): return None
    def rebuild_platform_headers(self, *args, **kwargs): return None
    def style_platform_rows(self, *args, **kwargs): return None
    def current_actor(self):
        try: return getpass.getuser() or "Sistem"
        except Exception: return "Sistem"
