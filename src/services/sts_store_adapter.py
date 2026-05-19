from __future__ import annotations

from contextlib import contextmanager
import getpass
import re

from src.models.app_models import TagDef


class STSStoreAdapter:
    def __init__(self, db):
        self.db = db
        self.path = db.path
        self.wb = None

    def platform_names(self): return self.db.list_platforms()
    def all_sheet_names(self): return self.platform_names()
    def load_users(self, active_only=True):
        users = self.db.list_users()
        if active_only:
            return [u for u in users if bool(u.get("active", 1))]
        return users
    def write_users(self, users_payload, actor="Sistem"):
        for u in users_payload or []: self.db.upsert_user(dict(u or {}))
    def load_components(self): return self.db.list_components()
    def write_components(self, components, actor="Sistem"):
        for c in components or []:
            payload = c if isinstance(c, dict) else getattr(c, "__dict__", {})
            self.db.upsert_component(dict(payload or {}))
    def load_tags(self): return self.db.list_tags()
    def _normalize_label(self, s: str) -> str:
        txt = str(s or "").strip().lower()
        repl = {"ı":"i","İ":"i","ş":"s","Ş":"s","ğ":"g","Ğ":"g","ü":"u","Ü":"u","ö":"o","Ö":"o","ç":"c","Ç":"c"}
        for a,b in repl.items(): txt = txt.replace(a,b)
        txt = re.sub(r"[^\w\s]", " ", txt)
        txt = txt.replace("_", " ")
        return re.sub(r"\s+", " ", txt).strip()
    def all_contract_tags_map(self):
        out = {}
        for c in self.db.list_contracts():
            out[(c.get("platform",""), c.get("no",""), c.get("type",""))] = list(c.get("tags") or [])
        return out
    def load_tag_snapshot(self):
        tags = []
        for t in self.db.list_tags():
            try:
                tags.append(TagDef(name=t.get("name", ""), color=t.get("color") or "#3B82F6", kind=t.get("kind") or "contract"))
            except TypeError:
                tags.append(t)
        return tags, self.all_contract_tags_map()
    def write_tag_snapshot(self, tags, assignments_by_key=None, actor="Sistem"):
        for t in tags or []:
            payload = t if isinstance(t, dict) else getattr(t, "__dict__", {})
            self.db.upsert_tag({"name": payload.get("name", ""), "color": payload.get("color") or "#3B82F6", "kind": payload.get("kind") or "contract"})
        for key, names in (assignments_by_key or {}).items():
            platform, contract_no, contract_type = (list(key) + ["", "", ""])[:3]
            row = self.db.get_contract_by_key(platform, contract_no, contract_type)
            if row and row.get("id"):
                self.db.set_contract_tags(int(row["id"]), list(names or []))
    def write_tags(self, tags, assignments_by_key=None, actor="Sistem"):
        return self.write_tag_snapshot(tags, assignments_by_key=assignments_by_key, actor=actor)
    def save_contract_tags(self, platform, contract_no, contract_type, tags, actor="Sistem"):
        row = self.db.get_contract_by_key(platform, contract_no, contract_type)
        if row and row.get("id"):
            names = [((t or {}).get("name") if isinstance(t, dict) else str(t)) for t in (tags or [])]
            self.db.set_contract_tags(int(row["id"]), [str(n or "").strip() for n in names if str(n or "").strip()])
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
    def load_excluded_platforms(self): return set()
    def save_excluded_platforms(self, *_args, **_kwargs): return None
    def create_platform(self, name, *args, **kwargs):
        self.db.upsert_platform(name)
        self.db.add_log("platform_created", "platform", str(name), "Platform eklendi")
    def delete_platform(self, name, *args, **kwargs): self.db.delete_platform(name)
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
