from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models.app_models import ContractInfo, DeliveryInfo, SystemInfo


class STSDatabase:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.conn: sqlite3.Connection | None = None

    def connect(self):
        if self.conn:
            return self.conn
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _now(self):
        return datetime.utcnow().isoformat(timespec="seconds")

    def init_schema(self):
        c = self.connect()
        c.executescript(
            """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS platforms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, sort_order INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, role TEXT, active INTEGER DEFAULT 1, payload_json TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS components (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, version TEXT, unit TEXT, active INTEGER DEFAULT 1, usage REAL DEFAULT 1, payload_json TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, color TEXT, kind TEXT, payload_json TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS contracts (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL, contract_no TEXT NOT NULL, user_name TEXT, contract_type TEXT, type_display TEXT, link_type TEXT, status TEXT, completion_date TEXT, content TEXT, start_date TEXT, end_date TEXT, duration_months INTEGER, is_main INTEGER DEFAULT 1, search_text TEXT, payload_json TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS systems (id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL, system_name TEXT, acceptance_name TEXT, acceptance_date TEXT, remaining_days INTEGER, status TEXT, sort_order INTEGER DEFAULT 0, payload_json TEXT);
CREATE TABLE IF NOT EXISTS deliveries (id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL, system_name TEXT, delivery_name TEXT, delivery_date TEXT, amount REAL, status TEXT, sort_order INTEGER DEFAULT 0, payload_json TEXT);
CREATE TABLE IF NOT EXISTS contract_tags (id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL, tag_name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, action TEXT, entity_type TEXT, entity_key TEXT, message TEXT, payload_json TEXT);
CREATE TABLE IF NOT EXISTS contract_rows (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 contract_id INTEGER NOT NULL,
 platform TEXT NOT NULL,
 contract_no TEXT NOT NULL,
 contract_type TEXT,
 row_kind TEXT,
 activity_name TEXT,
 delivery_acceptance_name TEXT,
 content TEXT,
 signed_date TEXT,
 t0_date TEXT,
 t0_months INTEGER,
 termin_date TEXT,
 status TEXT,
 acceptance_date TEXT,
 note TEXT,
 source_row INTEGER,
 sort_order INTEGER DEFAULT 0,
 payload_json TEXT,
 FOREIGN KEY(contract_id) REFERENCES contracts(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS contract_row_components (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 contract_row_id INTEGER NOT NULL,
 contract_id INTEGER NOT NULL,
 component_name TEXT NOT NULL,
 qty_required REAL DEFAULT 0,
 qty_delivered REAL DEFAULT 0,
 qty_remaining REAL DEFAULT 0,
 sort_order INTEGER DEFAULT 0,
 payload_json TEXT,
 FOREIGN KEY(contract_row_id) REFERENCES contract_rows(id) ON DELETE CASCADE,
 FOREIGN KEY(contract_id) REFERENCES contracts(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_contracts_platform ON contracts(platform);
CREATE INDEX IF NOT EXISTS idx_contracts_no ON contracts(contract_no);
CREATE INDEX IF NOT EXISTS idx_contracts_search ON contracts(search_text);
CREATE INDEX IF NOT EXISTS idx_contracts_platform_no ON contracts(platform, contract_no);
CREATE INDEX IF NOT EXISTS idx_systems_contract_id ON systems(contract_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_contract_id ON deliveries(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_tags_contract_id ON contract_tags(contract_id);
CREATE INDEX IF NOT EXISTS idx_logs_created_at ON activity_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_contract_rows_contract_id ON contract_rows(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_rows_platform_no ON contract_rows(platform, contract_no);
CREATE INDEX IF NOT EXISTS idx_contract_rows_row_kind ON contract_rows(row_kind);
CREATE INDEX IF NOT EXISTS idx_contract_rows_activity_name ON contract_rows(activity_name);
CREATE INDEX IF NOT EXISTS idx_crc_contract_id ON contract_row_components(contract_id);
CREATE INDEX IF NOT EXISTS idx_crc_row_id ON contract_row_components(contract_row_id);
CREATE INDEX IF NOT EXISTS idx_crc_component_name ON contract_row_components(component_name);
"""
        )
        c.commit()

    def create_new(self): self.connect(); self.init_schema(); self.set_meta("created_at", self._now())
    def get_meta(self, key, default=None):
        r=self.connect().execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone(); return r[0] if r else default
    def set_meta(self, key, value): self.connect().execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value))); self.conn.commit()
    def list_platforms(self): return [r[0] for r in self.connect().execute("SELECT name FROM platforms WHERE is_active=1 ORDER BY sort_order,name")]
    def upsert_platform(self,name,sort_order=0,is_active=True):
        n=self._now(); self.connect().execute("INSERT INTO platforms(name,sort_order,is_active,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET sort_order=excluded.sort_order,is_active=excluded.is_active,updated_at=excluded.updated_at", (name,sort_order,int(is_active),n,n)); self.conn.commit()
    def delete_platform(self,name): self.connect().execute("DELETE FROM platforms WHERE name=?", (name,)); self.conn.commit()
    def list_users(self): return [dict(r) for r in self.connect().execute("SELECT * FROM users ORDER BY name")]
    def upsert_user(self,p):
        name = str((p or {}).get("name", "") or "").strip()
        if not name:
            return
        n=self._now(); c=self.connect(); r=c.execute("SELECT id FROM users WHERE name=?", (name,)).fetchone()
        role = (p or {}).get("yi_yd") or (p or {}).get("role", "")
        payload = json.dumps(p, ensure_ascii=False)
        if r:
            c.execute("UPDATE users SET role=?, active=?, payload_json=?, updated_at=? WHERE id=?", (role, int((p or {}).get("active", True)), payload, n, int(r[0])))
        else:
            c.execute("INSERT INTO users(name,role,active,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?)", (name, role, int((p or {}).get("active",True)), payload, n,n))
        self.conn.commit()
    def list_components(self): return [dict(r) for r in self.connect().execute("SELECT * FROM components ORDER BY name")]
    def upsert_component(self,p):
        name = str((p or {}).get("name", "") or "").strip()
        if not name:
            return
        n=self._now(); c=self.connect(); r=c.execute("SELECT id FROM components WHERE name=?", (name,)).fetchone()
        payload = json.dumps(p, ensure_ascii=False)
        vals = (str((p or {}).get("version", "")), str((p or {}).get("unit", "Adet")), int((p or {}).get("active", True)), float((p or {}).get("usage", 1) or 1), payload, n)
        if r:
            c.execute("UPDATE components SET version=?, unit=?, active=?, usage=?, payload_json=?, updated_at=? WHERE id=?", vals + (int(r[0]),))
        else:
            c.execute("INSERT INTO components(name,version,unit,active,usage,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (name,) + vals + (n,))
        self.conn.commit()
    def list_tags(self): return [dict(r) for r in self.connect().execute("SELECT * FROM tags ORDER BY name")]
    def upsert_tag(self,p):
        n=self._now(); self.connect().execute("INSERT INTO tags(name,color,kind,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET color=excluded.color,kind=excluded.kind,payload_json=excluded.payload_json,updated_at=excluded.updated_at", (p.get('name',''), p.get('color','#3B82F6'), p.get('kind',''), json.dumps(p,ensure_ascii=False), n,n)); self.conn.commit()

    def get_or_create_platform(self, name: str): self.upsert_platform(name); r=self.connect().execute("SELECT id FROM platforms WHERE name=?", (name,)).fetchone(); return int(r[0]) if r else None
    def ensure_default_user(self):
        if not self.list_users(): self.upsert_user({"name":"Sistem","role":"Varsayılan","active":True})
    def clear_all(self, clear_meta=False):
        c=self.connect()
        for t in ["contract_row_components","contract_rows","contract_tags","deliveries","systems","contracts","tags","components","users","platforms","activity_logs"]: c.execute(f"DELETE FROM {t}")
        if clear_meta: c.execute("DELETE FROM meta")
        c.commit()

    def set_contract_tags(self, contract_id:int, tag_names:list[str]):
        c=self.connect(); c.execute("DELETE FROM contract_tags WHERE contract_id=?", (contract_id,))
        seen=set()
        for t in tag_names or []:
            nm=str(t or '').strip()
            if not nm or nm.casefold() in seen: continue
            seen.add(nm.casefold()); self.upsert_tag({"name":nm,"color":"#3B82F6","kind":"MANUAL"})
            c.execute("INSERT INTO contract_tags(contract_id,tag_name) VALUES(?,?)", (contract_id,nm))
        c.commit()

    def _upsert_contract_card(self, item: dict) -> int:
        c=self.connect(); n=self._now(); platform=str(item.get('platform') or '').strip(); no=str(item.get('no') or item.get('contract_no') or '').strip(); ctype=str(item.get('contract_type') or item.get('type') or '').strip()
        item_id = int(item.get("id") or 0)
        r = None
        if item_id:
            r = c.execute("SELECT id FROM contracts WHERE id=?", (item_id,)).fetchone()
        if not r:
            r=c.execute("SELECT id FROM contracts WHERE platform=? AND contract_no=? AND contract_type=? ORDER BY id DESC LIMIT 1", (platform,no,ctype)).fetchone()
        stext=str(item.get('search_text') or item.get('search') or '').lower()
        args=(platform,no,str(item.get('user') or item.get('user_name') or ''),ctype,str(item.get('type_display') or ctype),str(item.get('link') or ''),str(item.get('status') or ''),str(item.get('completion_date') or ''),str(item.get('content') or ''),str(item.get('signed_date') or ''),str(item.get('termin_date') or ''),int(item.get('t0_months') or 0),int(bool(item.get('is_main',True))),stext,json.dumps(item.get('payload_json') if isinstance(item.get('payload_json'),dict) else dict(item),ensure_ascii=False),n)
        if r:
            cid=int(r[0]); c.execute("UPDATE contracts SET platform=?,contract_no=?,user_name=?,contract_type=?,type_display=?,link_type=?,status=?,completion_date=?,content=?,start_date=?,end_date=?,duration_months=?,is_main=?,search_text=?,payload_json=?,updated_at=? WHERE id=?", args+(cid,))
        else:
            cur=c.execute("INSERT INTO contracts(platform,contract_no,user_name,contract_type,type_display,link_type,status,completion_date,content,start_date,end_date,duration_months,is_main,search_text,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", args+(n,)); cid=int(cur.lastrowid)
        c.commit(); return cid

    def upsert_contract_from_excel_block(self, contract_header: dict, rows: list[dict]) -> int:
        base = dict(contract_header)
        base["is_main"] = True
        base["search_text"] = " ".join([str(base.get(k, "") or "") for k in ["platform","contract_no","user_name","contract_type","status","content","activity_name","delivery_acceptance_name"]]).lower()
        cid = self._upsert_contract_card(base)
        c=self.connect(); c.execute("DELETE FROM contract_row_components WHERE contract_id=?", (cid,)); c.execute("DELETE FROM contract_rows WHERE contract_id=?", (cid,))
        for i, row in enumerate(rows or []):
            cur=c.execute("INSERT INTO contract_rows(contract_id,platform,contract_no,contract_type,row_kind,activity_name,delivery_acceptance_name,content,signed_date,t0_date,t0_months,termin_date,status,acceptance_date,note,source_row,sort_order,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid,row.get('platform',''),row.get('contract_no',''),row.get('contract_type',''),row.get('row_kind','other'),row.get('activity_name',''),row.get('delivery_acceptance_name',''),row.get('content',''),row.get('signed_date',''),row.get('t0_date',''),int(row.get('t0_months') or 0),row.get('termin_date',''),row.get('status',''),row.get('acceptance_date',''),row.get('note',''),int(row.get('source_row') or 0),i,json.dumps(row,ensure_ascii=False)))
            row_id=int(cur.lastrowid)
            for j,comp in enumerate(row.get('components') or []):
                c.execute("INSERT INTO contract_row_components(contract_row_id,contract_id,component_name,qty_required,qty_delivered,qty_remaining,sort_order,payload_json) VALUES(?,?,?,?,?,?,?,?)", (row_id,cid,comp.get('name',''),float(comp.get('required',0) or 0),float(comp.get('delivered',0) or 0),float(comp.get('remaining',0) or 0),j,json.dumps(comp,ensure_ascii=False)))
        c.commit(); return cid

    def upsert_contract_from_dict(self, item: dict) -> int:
        if item.get("rows"): return self.upsert_contract_from_excel_block(item, item.get("rows") or [])
        return self._upsert_contract_card(item)

    def list_contracts(self, platform=None): return self.search_contracts("", platform)
    def search_contracts(self, query="", platform=None):
        sql="SELECT * FROM contracts WHERE 1=1"; args=[]
        if platform: sql+=" AND platform=?"; args.append(platform)
        if str(query).strip(): sql+=" AND search_text LIKE ?"; args.append(f"%{str(query).lower()}%")
        sql+=" ORDER BY platform, contract_no"
        out=[]
        for r in self.connect().execute(sql, tuple(args)).fetchall():
            tags=[x[0] for x in self.connect().execute("SELECT tag_name FROM contract_tags WHERE contract_id=? ORDER BY id", (r['id'],)).fetchall()]
            out.append({"id":r["id"],"row":r["id"],"platform":r["platform"],"no":r["contract_no"],"user":r["user_name"] or "","type":r["contract_type"] or "","type_display":r["type_display"] or (r["contract_type"] or ""),"link":r["link_type"] or "","status":r["status"] or "","completion_date":r["completion_date"] or "","content":r["content"] or "","is_main":bool(r["is_main"]),"tags":tags,"search":r["search_text"] or ""})
        return out

    def get_contract(self, contract_id:int): r=self.connect().execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone(); return dict(r) if r else None
    def get_contract_by_key(self, platform, contract_no, contract_type="", start_row=None):
        r=self.connect().execute("SELECT * FROM contracts WHERE platform=? AND contract_no=? AND (?='' OR contract_type=?) ORDER BY id DESC LIMIT 1", (platform,contract_no,contract_type,contract_type)).fetchone(); return dict(r) if r else None

    def get_contract_detail(self, contract_id:int):
        c=self.get_contract(contract_id)
        if not c: return None, [], {}
        payload=json.loads(c.get('payload_json') or '{}')
        ci_payload = {k: payload.get(k) for k in ["no","platform","user","yi_yd","contract_type","signature_date","t0_date","t0_months","completion_date","status","note","acceptance_date","entry_start_row","sd_anchor_start_row","sd_anchor_end_row","sd_anchor_platform","sd_anchor_no"]} if isinstance(payload, dict) else {}
        ci=ContractInfo(**ci_payload) if ci_payload and all(ci_payload.get(k) is not None for k in ["no","platform","user","yi_yd","contract_type","signature_date","t0_date","t0_months","completion_date"]) else ContractInfo(no=c['contract_no'],platform=c['platform'],user=c.get('user_name') or '',yi_yd='',contract_type=c.get('contract_type') or '',signature_date=c.get('start_date') or '',t0_date=c.get('start_date') or '',t0_months=int(c.get('duration_months') or 0),completion_date=c.get('completion_date') or '',status=c.get('status') or 'PLAN',note=c.get('content') or '')
        setattr(ci, 'entry_start_row', int(contract_id)); setattr(ci, 'contract_id', int(contract_id))
        systems=[]; deliveries={}
        rows=self.connect().execute("SELECT * FROM contract_rows WHERE contract_id=? ORDER BY sort_order,id", (contract_id,)).fetchall()
        if rows:
            for rr in rows:
                p=json.loads(rr['payload_json'] or '{}')
                if rr['row_kind'] in {'system_total','contract_total'}:
                    nm=str((p.get('system_name') if isinstance(p, dict) else '') or rr['activity_name'] or rr['delivery_acceptance_name'] or 'Sistem')
                    comps={}
                    for cc in self.connect().execute("SELECT * FROM contract_row_components WHERE contract_row_id=? ORDER BY sort_order,id", (rr['id'],)):
                        comps[str(cc['component_name'] or '')]=float(cc['qty_required'] or 0)
                    systems.append(SystemInfo(name=nm, components=comps, t0_date=str(rr['t0_date'] or ''), t0_months=int(rr['t0_months'] or 0), completion_date=str(rr['termin_date'] or ''), status=str(rr['status'] or 'Başlanmadı'), acceptance_date=str(rr['acceptance_date'] or '')))
                elif rr['row_kind'] == 'acceptance':
                    d=DeliveryInfo(name=str(rr['delivery_acceptance_name'] or 'Kabul'), status=str(rr['status'] or ''), acceptance_date=str(rr['acceptance_date'] or ''), note=str(rr['note'] or ''), planned=(p.get('planned') if isinstance(p, dict) else {}) or {}, delivered=(p.get('delivered') if isinstance(p, dict) else {}) or {})
                    deliveries.setdefault(str(rr['activity_name'] or 'Sistem'), []).append(d)
        else:
            psys = payload.get("systems") if isinstance(payload, dict) else None
            pdel = payload.get("deliveries") if isinstance(payload, dict) else None
            for s in psys or []:
                systems.append(SystemInfo(**s) if isinstance(s, dict) else s)
            for k, vals in (pdel or {}).items():
                deliveries[str(k)] = [DeliveryInfo(**d) if isinstance(d, dict) else d for d in (vals or [])]
        if not systems: systems=[SystemInfo(name='Sistem', components={}, status=ci.status, acceptance_date=ci.acceptance_date)]
        return ci, systems, deliveries

    def upsert_contract(self, ci, systems=None, deliveries=None, old_contract_id=None):
        systems = systems or []
        deliveries = deliveries or {}
        payload_ci = asdict(ci)
        payload_ci["systems"] = [asdict(s) if hasattr(s, "__dataclass_fields__") else dict(s or {}) for s in systems]
        payload_ci["deliveries"] = {str(k): [asdict(d) if hasattr(d, "__dataclass_fields__") else dict(d or {}) for d in (v or [])] for k, v in deliveries.items()}
        item={"id": old_contract_id, "platform":ci.platform,"contract_no":ci.no,"user_name":ci.user,"contract_type":ci.contract_type,"status":ci.status,"content":ci.note,"signed_date":ci.signature_date,"termin_date":ci.completion_date,"t0_months":ci.t0_months,"type_display":ci.contract_type,"link":"","is_main":True,"payload_json":payload_ci,"search_text":" ".join([ci.platform,ci.no,ci.user,ci.contract_type,ci.status,ci.note]).lower()}
        cid = self._upsert_contract_card(item)
        c=self.connect(); c.execute("DELETE FROM contract_row_components WHERE contract_id=?", (cid,)); c.execute("DELETE FROM contract_rows WHERE contract_id=?", (cid,))
        base_row=(cid, str(ci.platform or ""), str(ci.no or ""), str(ci.contract_type or ""))
        c.execute("INSERT INTO contract_rows(contract_id,platform,contract_no,contract_type,row_kind,activity_name,delivery_acceptance_name,content,signed_date,t0_date,t0_months,termin_date,status,acceptance_date,note,source_row,sort_order,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", base_row + ("contract_total","GENEL","Ana Sözleşme Toplamı",str(ci.note or ""),str(ci.signature_date or ""),str(ci.t0_date or ""),int(ci.t0_months or 0),str(ci.completion_date or ""),str(ci.status or ""),str(getattr(ci,'acceptance_date','') or ''),str(ci.note or ''),int(cid or 0),0,json.dumps(payload_ci,ensure_ascii=False)))
        sort_order=1
        for sys in systems:
            sd = asdict(sys) if hasattr(sys, "__dataclass_fields__") else dict(sys or {})
            sname = str(sd.get("name") or sd.get("system_name") or "Sistem")
            cur = c.execute("INSERT INTO contract_rows(contract_id,platform,contract_no,contract_type,row_kind,activity_name,delivery_acceptance_name,content,signed_date,t0_date,t0_months,termin_date,status,acceptance_date,note,source_row,sort_order,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", base_row + ("system_total",sname,f"{sname} Toplamı","",str(ci.signature_date or ""),str(sd.get("t0_date") or ci.t0_date or ""),int(sd.get("t0_months") or ci.t0_months or 0),str(sd.get("completion_date") or ci.completion_date or ""),str(sd.get("status") or ci.status or ""),str(sd.get("acceptance_date") or ""),str(sd.get("note") or ""),int(cid or 0),sort_order,json.dumps(sd,ensure_ascii=False)))
            sort_order += 1
            row_id = int(cur.lastrowid)
            for i,(cn,qty) in enumerate((sd.get("components") or {}).items()):
                req=float(qty or 0); c.execute("INSERT INTO contract_row_components(contract_row_id,contract_id,component_name,qty_required,qty_delivered,qty_remaining,sort_order,payload_json) VALUES(?,?,?,?,?,?,?,?)", (row_id,cid,str(cn),req,0.0,req,i,json.dumps({"name":cn,"required":req},ensure_ascii=False)))
            for d in deliveries.get(sname, []) or []:
                dd = asdict(d) if hasattr(d, "__dataclass_fields__") else dict(d or {})
                c.execute("INSERT INTO contract_rows(contract_id,platform,contract_no,contract_type,row_kind,activity_name,delivery_acceptance_name,content,signed_date,t0_date,t0_months,termin_date,status,acceptance_date,note,source_row,sort_order,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", base_row + ("acceptance",sname,str(dd.get("name") or "Kabul"),"",str(ci.signature_date or ""),str(dd.get("t0_date") or sd.get("t0_date") or ci.t0_date or ""),int(dd.get("t0_months") or sd.get("t0_months") or ci.t0_months or 0),str(dd.get("completion_date") or sd.get("completion_date") or ci.completion_date or ""),str(dd.get("status") or ""),str(dd.get("acceptance_date") or ""),str(dd.get("note") or ""),int(cid or 0),sort_order,json.dumps(dd,ensure_ascii=False)))
                sort_order += 1
        c.commit(); return int(cid)

    def delete_contract(self, contract_id:int):
        c=self.connect(); c.execute("DELETE FROM contract_row_components WHERE contract_id=?", (contract_id,)); c.execute("DELETE FROM contract_rows WHERE contract_id=?", (contract_id,)); c.execute("DELETE FROM contract_tags WHERE contract_id=?", (contract_id,)); c.execute("DELETE FROM systems WHERE contract_id=?", (contract_id,)); c.execute("DELETE FROM deliveries WHERE contract_id=?", (contract_id,)); c.execute("DELETE FROM contracts WHERE id=?", (contract_id,)); c.commit(); self.add_log("contract_deleted","contract",str(contract_id),"Sözleşme silindi")
    def count_contract_rows(self): return int(self.connect().execute("SELECT COUNT(*) FROM contract_rows").fetchone()[0])
    def count_contract_row_components(self): return int(self.connect().execute("SELECT COUNT(*) FROM contract_row_components").fetchone()[0])
    def add_log(self, action, entity_type, entity_key, message="", payload=None): self.connect().execute("INSERT INTO activity_logs(created_at,action,entity_type,entity_key,message,payload_json) VALUES(?,?,?,?,?,?)", (self._now(),action,entity_type,entity_key,message,json.dumps(payload or {}, ensure_ascii=False))); self.conn.commit()
    def list_logs(self, limit=500): return [dict(r) for r in self.connect().execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?", (int(limit),))]
    def vacuum(self): self.connect().execute("VACUUM")
