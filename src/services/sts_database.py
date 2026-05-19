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

    def _now(self) -> str:
        return datetime.utcnow().isoformat(timespec="seconds")

    def init_schema(self):
        c = self.connect()
        c.executescript("""
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS platforms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, sort_order INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, role TEXT, active INTEGER DEFAULT 1, payload_json TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS components (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, version TEXT, unit TEXT, active INTEGER DEFAULT 1, usage REAL DEFAULT 1, payload_json TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, color TEXT, kind TEXT, payload_json TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS contracts (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL, contract_no TEXT NOT NULL, user_name TEXT, contract_type TEXT, type_display TEXT, link_type TEXT, status TEXT, completion_date TEXT, content TEXT, start_date TEXT, end_date TEXT, duration_months INTEGER, is_main INTEGER DEFAULT 1, search_text TEXT, payload_json TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS systems (id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL, system_name TEXT, acceptance_name TEXT, acceptance_date TEXT, remaining_days INTEGER, status TEXT, sort_order INTEGER DEFAULT 0, payload_json TEXT);
CREATE TABLE IF NOT EXISTS deliveries (id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL, system_name TEXT, delivery_name TEXT, delivery_date TEXT, amount REAL, status TEXT, sort_order INTEGER DEFAULT 0, payload_json TEXT);
CREATE TABLE IF NOT EXISTS contract_tags (id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL, tag_name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS activity_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, action TEXT, entity_type TEXT, entity_key TEXT, message TEXT, payload_json TEXT);
CREATE INDEX IF NOT EXISTS idx_contracts_platform ON contracts(platform);
CREATE INDEX IF NOT EXISTS idx_contracts_no ON contracts(contract_no);
CREATE INDEX IF NOT EXISTS idx_contracts_search ON contracts(search_text);
CREATE INDEX IF NOT EXISTS idx_contracts_platform_no ON contracts(platform, contract_no);
CREATE INDEX IF NOT EXISTS idx_systems_contract_id ON systems(contract_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_contract_id ON deliveries(contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_tags_contract_id ON contract_tags(contract_id);
CREATE INDEX IF NOT EXISTS idx_logs_created_at ON activity_logs(created_at);
""")
        c.commit()

    def create_new(self):
        self.connect(); self.init_schema(); self.set_meta("created_at", self._now())

    def get_meta(self, key: str, default=None):
        row = self.connect().execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value):
        self.connect().execute("INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        self.conn.commit()

    def list_platforms(self) -> list[str]:
        rows = self.connect().execute("SELECT name FROM platforms WHERE is_active=1 ORDER BY sort_order, name").fetchall()
        return [r[0] for r in rows]

    def upsert_platform(self, name: str, sort_order: int = 0, is_active: bool = True):
        now = self._now(); c = self.connect()
        c.execute("INSERT INTO platforms(name, sort_order, is_active, created_at, updated_at) VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET sort_order=excluded.sort_order,is_active=excluded.is_active,updated_at=excluded.updated_at", (name, sort_order, int(is_active), now, now))
        c.commit()

    def delete_platform(self, name: str):
        self.connect().execute("DELETE FROM platforms WHERE name=?", (name,)); self.conn.commit()

    def list_users(self) -> list[dict]:
        return [dict(r) for r in self.connect().execute("SELECT * FROM users ORDER BY name")]
    def upsert_user(self, payload: dict):
        now=self._now(); name=str(payload.get('name','')).strip();
        self.connect().execute("INSERT INTO users(name, role, active, payload_json, created_at, updated_at) VALUES(?,?,?,?,?,?)", (name, payload.get('yi_yd') or payload.get('role',''), int(payload.get('active',True)), json.dumps(payload, ensure_ascii=False), now, now)); self.conn.commit()
    def list_components(self) -> list[dict]: return [dict(r) for r in self.connect().execute("SELECT * FROM components ORDER BY name")]
    def upsert_component(self, payload: dict):
        now=self._now(); self.connect().execute("INSERT INTO components(name,version,unit,active,usage,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (payload.get('name',''), payload.get('version',''), payload.get('unit','Adet'), int(payload.get('active',True)), float(payload.get('usage',1) or 1), json.dumps(payload, ensure_ascii=False), now, now)); self.conn.commit()
    def list_tags(self) -> list[dict]: return [dict(r) for r in self.connect().execute("SELECT * FROM tags ORDER BY name")]
    def upsert_tag(self, payload: dict):
        now=self._now(); self.connect().execute("INSERT INTO tags(name,color,kind,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET color=excluded.color,kind=excluded.kind,payload_json=excluded.payload_json,updated_at=excluded.updated_at", (payload.get('name',''), payload.get('color','#3B82F6'), payload.get('kind',''), json.dumps(payload, ensure_ascii=False), now, now)); self.conn.commit()

    def list_contracts(self, platform: str | None = None) -> list[dict]:
        return self.search_contracts("", platform)

    def search_contracts(self, query: str = "", platform: str | None = None) -> list[dict]:
        sql = "SELECT * FROM contracts WHERE 1=1"; args: list[Any] = []
        if platform: sql += " AND platform=?"; args.append(platform)
        if query.strip(): sql += " AND search_text LIKE ?"; args.append(f"%{query.lower()}%")
        sql += " ORDER BY platform, contract_no"
        rows = self.connect().execute(sql, tuple(args)).fetchall()
        out=[]
        for r in rows:
            out.append({"id":r["id"],"platform":r["platform"],"no":r["contract_no"],"contract_type":r["contract_type"] or "","status":r["status"] or "","completion":r["completion_date"] or "","user":r["user_name"] or "","row":r["id"]})
        return out

    def get_contract(self, contract_id: int) -> dict | None:
        r=self.connect().execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone(); return dict(r) if r else None
    def get_contract_by_key(self, platform: str, contract_no: str, contract_type: str = "", start_row: int | None = None):
        r=self.connect().execute("SELECT * FROM contracts WHERE platform=? AND contract_no=? AND (?='' OR contract_type=?) ORDER BY id DESC LIMIT 1", (platform, contract_no, contract_type, contract_type)).fetchone(); return dict(r) if r else None

    def get_contract_detail(self, contract_id: int) -> tuple:
        c = self.get_contract(contract_id)
        if not c: return None, [], {}
        payload = json.loads(c.get("payload_json") or "{}")
        ci = ContractInfo(**payload) if payload else ContractInfo(no=c["contract_no"], platform=c["platform"], user=c.get("user_name") or "", yi_yd=c.get("link_type") or "", contract_type=c.get("contract_type") or "", signature_date=c.get("start_date") or "", t0_date=c.get("start_date") or "", t0_months=int(c.get("duration_months") or 0), completion_date=c.get("completion_date") or "", status=c.get("status") or "PLAN", note=c.get("content") or "")
        systems=[]
        for s in self.connect().execute("SELECT * FROM systems WHERE contract_id=? ORDER BY sort_order,id", (contract_id,)):
            p=json.loads(s["payload_json"] or "{}")
            systems.append(SystemInfo(**p) if p else SystemInfo(name=s["system_name"] or "", components={}, acceptance_date=s["acceptance_date"] or "", status=s["status"] or "Başlanmadı"))
        deliveries: dict[str, list[DeliveryInfo]] = {}
        for d in self.connect().execute("SELECT * FROM deliveries WHERE contract_id=? ORDER BY sort_order,id", (contract_id,)):
            p=json.loads(d["payload_json"] or "{}")
            di=DeliveryInfo(**p) if p else DeliveryInfo(name=d["delivery_name"] or "", status=d["status"] or "", acceptance_date=d["delivery_date"] or "", note="", planned={}, delivered={})
            deliveries.setdefault(d["system_name"] or "", []).append(di)
        return ci, systems, deliveries

    def upsert_contract(self, ci, systems=None, deliveries=None, old_contract_id: int | None = None) -> int:
        now=self._now(); systems=systems or []; deliveries=deliveries or {}
        stext = " ".join([str(getattr(ci,'platform','')), str(getattr(ci,'no','')), str(getattr(ci,'user','')), str(getattr(ci,'contract_type','')), str(getattr(ci,'status','')), str(getattr(ci,'note',''))]).lower()
        c=self.connect()
        if old_contract_id:
            cid=old_contract_id
            c.execute("UPDATE contracts SET platform=?, contract_no=?, user_name=?, contract_type=?, link_type=?, status=?, completion_date=?, content=?, start_date=?, end_date=?, duration_months=?, search_text=?, payload_json=?, updated_at=? WHERE id=?", (ci.platform, ci.no, ci.user, ci.contract_type, getattr(ci,'yi_yd',''), ci.status, ci.completion_date, ci.note, ci.signature_date, ci.completion_date, int(getattr(ci,'t0_months',0) or 0), stext, json.dumps(asdict(ci), ensure_ascii=False), now, cid))
            c.execute("DELETE FROM systems WHERE contract_id=?", (cid,)); c.execute("DELETE FROM deliveries WHERE contract_id=?", (cid,))
        else:
            cur=c.execute("INSERT INTO contracts(platform,contract_no,user_name,contract_type,link_type,status,completion_date,content,start_date,end_date,duration_months,search_text,payload_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (ci.platform, ci.no, ci.user, ci.contract_type, getattr(ci,'yi_yd',''), ci.status, ci.completion_date, ci.note, ci.signature_date, ci.completion_date, int(getattr(ci,'t0_months',0) or 0), stext, json.dumps(asdict(ci), ensure_ascii=False), now, now)); cid=cur.lastrowid
        for i,s in enumerate(systems):
            c.execute("INSERT INTO systems(contract_id,system_name,acceptance_date,status,sort_order,payload_json) VALUES(?,?,?,?,?,?)", (cid, getattr(s,'name',''), getattr(s,'acceptance_date',''), getattr(s,'status',''), i, json.dumps(asdict(s), ensure_ascii=False)))
        for sys_name, items in deliveries.items():
            for i,d in enumerate(items):
                c.execute("INSERT INTO deliveries(contract_id,system_name,delivery_name,delivery_date,status,sort_order,payload_json) VALUES(?,?,?,?,?,?,?)", (cid, sys_name, getattr(d,'name',''), getattr(d,'acceptance_date',''), getattr(d,'status',''), i, json.dumps(asdict(d), ensure_ascii=False)))
        c.commit(); return int(cid)

    def delete_contract(self, contract_id: int):
        c=self.connect(); c.execute("DELETE FROM systems WHERE contract_id=?", (contract_id,)); c.execute("DELETE FROM deliveries WHERE contract_id=?", (contract_id,)); c.execute("DELETE FROM contracts WHERE id=?", (contract_id,)); c.commit()
    def add_log(self, action: str, entity_type: str, entity_key: str, message: str = "", payload: dict | None = None):
        self.connect().execute("INSERT INTO activity_logs(created_at,action,entity_type,entity_key,message,payload_json) VALUES(?,?,?,?,?,?)", (self._now(), action, entity_type, entity_key, message, json.dumps(payload or {}, ensure_ascii=False))); self.conn.commit()
    def list_logs(self, limit: int = 500):
        return [dict(r) for r in self.connect().execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?", (int(limit),))]
    def vacuum(self): self.connect().execute("VACUUM")
