"""
CureMenu — Veritabanı Katmanımız (SQLite)
Kullanıcı profillerini ve logları şimdilik lokalde (SQLite) tutuyoruz.
İleride canlıya (Production) çıkarken kolayca PostgreSQL'e geçebilelim diye veri katmanını izole ettik.
"""
import sqlite3
import json
from datetime import datetime
from src.models import KullaniciProfili
from src.logger import get_logger
from src.config import settings
from src.governance.kpi import calculate_clinical_kpis
from src.privacy.redaction import dumps_redacted_json, redact_json_string, redact_text
from contextlib import contextmanager

logger = get_logger(__name__)

_db_initialized = False


def _connect() -> sqlite3.Connection:
    """Eşzamanlı (Concurrent) isteklerde kilitlenmeyi (Lock) önlemek için WAL modunda bağlanıyoruz."""
    conn = sqlite3.connect(
        settings.CUREMENU_DB_PATH,
        timeout=settings.CUREMENU_DB_TIMEOUT,
        check_same_thread=False,
    )
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def icd11_cache_get(cache_key: str, conn: sqlite3.Connection = None) -> str | None:
    _ensure_db()
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute("SELECT sonuc FROM icd11_cache WHERE cache_key = ?", (cache_key,))
        row = cursor.fetchone()
        return row[0] if row else None

def icd11_cache_set(cache_key: str, sonuc: str, conn: sqlite3.Connection = None) -> None:
    _ensure_db()
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute("""
            INSERT INTO icd11_cache (cache_key, sonuc)
            VALUES (?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET sonuc = excluded.sonuc
        """, (cache_key, sonuc))
        _conn.commit()

def get_db():
    """
    FastAPI Dependency Injection (Bağımlılık Enjeksiyonu) için kullanılan jeneratör.
    Her HTTP isteğinde güvenli bir bağlantı açar ve istek bitince bağlantıyı kapatır.
    """
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_connection(conn: sqlite3.Connection = None):
    """Mevcut bağlantıyı kullan veya yenisini oluşturup iş bitince kapat (DRY)."""
    own_conn = conn is None
    _conn = conn or _connect()
    try:
        yield _conn
    finally:
        if own_conn:
            _conn.close()


def _ensure_db():
    """Sunucu kalkarken veritabanı tablolarımızı sadece bir kez (singleton) initialize ediyoruz."""
    # Production schema changes should be managed through Alembic migrations.
    # This initializer stays for backward compatibility and ephemeral test DBs.
    global _db_initialized
    if _db_initialized:
        return
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            telefon TEXT PRIMARY KEY,
            kullanici_adi TEXT,
            sifre_hash TEXT,
            profil_data TEXT,
            kayit_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
            son_guncelleme TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Geriye dönük uyumluluk (migration)
    try:
        cursor.execute("ALTER TABLE profiles ADD COLUMN sifre_hash TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interaction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telefon TEXT,
            kullanici_adi TEXT,
            sayfa TEXT,
            istek TEXT,
            cevap TEXT,
            metadata TEXT,
            tarih TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (telefon) REFERENCES profiles(telefon)
        )
    """)

    try:
        cursor.execute("ALTER TABLE interaction_logs ADD COLUMN metadata TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS icd11_cache (
            cache_key TEXT PRIMARY KEY,
            sonuc TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clinical_decisions (
            decision_id TEXT PRIMARY KEY,
            telefon TEXT,
            kimin_icin TEXT,
            istek TEXT,
            final_answer TEXT,
            final_action TEXT,
            risk_score REAL,
            confidence_score REAL,
            confidence_data TEXT,
            component_versions TEXT,
            citations TEXT,
            created_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (telefon) REFERENCES profiles(telefon)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decision_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT,
            sequence_no INTEGER,
            event_type TEXT,
            component TEXT,
            status TEXT,
            metadata TEXT,
            created_at TEXT,
            FOREIGN KEY (decision_id) REFERENCES clinical_decisions(decision_id)
        )
    """)

    conn.commit()
    conn.close()
    _db_initialized = True


def profil_getir_db(telefon: str, conn: sqlite3.Connection = None) -> KullaniciProfili:
    """Telefon numarasına göre kullanıcının profilini çekip Pydantic objesine çeviriyoruz."""
    _ensure_db()
    
    # Manage DB connection via context manager if not injected / DI desteği için veritabanı bağlantısı yönetimi
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute("SELECT profil_data FROM profiles WHERE telefon = ?", (telefon,))
        row = cursor.fetchone()
        
        if row:
            try:
                return KullaniciProfili.model_validate_json(row[0])
            except Exception as e:
                logger.warning("Profil JSON çözümleme hatası (%s): %s", telefon, e)
                return None
        return None

def sifre_hash_getir(telefon: str, conn: sqlite3.Connection = None) -> str | None:
    _ensure_db()
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute("SELECT sifre_hash FROM profiles WHERE telefon = ?", (telefon,))
        row = cursor.fetchone()
        return row[0] if row else None

def sifre_hash_kaydet(telefon: str, sifre_hash: str, conn: sqlite3.Connection = None):
    _ensure_db()
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute("""
            UPDATE profiles SET sifre_hash = ? WHERE telefon = ?
        """, (sifre_hash, telefon))
        _conn.commit()

def profil_kaydet_db(telefon: str, kullanici_adi: str, profil: KullaniciProfili, conn: sqlite3.Connection = None):
    """Kullanıcı profilini Upsert (Var ise güncelle, yoksa ekle) mantığıyla kaydediyoruz."""
    _ensure_db()
    profil_json = profil.model_dump_json()
    simdi = datetime.now().isoformat()
    
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute("""
            INSERT INTO profiles (telefon, kullanici_adi, profil_data, kayit_tarihi, son_guncelleme)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telefon) DO UPDATE SET
                kullanici_adi = CASE
                    WHEN excluded.kullanici_adi != '' THEN excluded.kullanici_adi
                    ELSE profiles.kullanici_adi
                END,
                profil_data = excluded.profil_data,
                son_guncelleme = ?
        """, (telefon, kullanici_adi, profil_json, simdi, simdi, simdi))
        _conn.commit()


def etkilesim_logla(telefon: str, kullanici_adi: str, sayfa: str, istek: str, cevap: str, metadata: str = None, conn: sqlite3.Connection = None):
    """Persist an interaction log after masking direct personal identifiers."""
    _ensure_db()
    safe_kullanici_adi = redact_text(kullanici_adi or "")
    safe_istek = redact_text(istek or "")
    safe_cevap = redact_text(cevap or "")
    safe_metadata = redact_json_string(metadata)
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        if not safe_kullanici_adi:
            cursor.execute(
                "SELECT kullanici_adi FROM profiles WHERE telefon = ?",
                (telefon,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                safe_kullanici_adi = redact_text(row[0])
        cursor.execute("""
            INSERT INTO interaction_logs (telefon, kullanici_adi, sayfa, istek, cevap, metadata, tarih)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (telefon, safe_kullanici_adi, sayfa, safe_istek, safe_cevap, safe_metadata, datetime.now().isoformat()))
        _conn.commit()


def loglari_getir_db(telefon: str, limit: int = 10, offset: int = 0, conn: sqlite3.Connection = None) -> list:
    """Kullanıcının geçmiş loglarını (Pagination) sayfalama destekli olarak getirir."""
    _ensure_db()
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute("""
            SELECT kullanici_adi, sayfa, istek, cevap, metadata, tarih
            FROM interaction_logs
            WHERE telefon = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (telefon, limit, offset))

        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]


def log_sayisi_getir_db(telefon: str, conn: sqlite3.Connection = None) -> int:
    """Kullanıcının toplam log sayısı (pagination için)."""
    _ensure_db()
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM interaction_logs WHERE telefon = ?",
            (telefon,),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def klinik_karar_kaydet(record: dict, conn: sqlite3.Connection = None):
    """Persist one auditable clinical decision and redact direct identifiers first."""
    _ensure_db()
    if not record.get("decision_id"):
        raise ValueError("decision_id is required")

    safe_record = {
        **record,
        "request": redact_text(record.get("request", "")),
        "final_answer": redact_text(record.get("final_answer", "")),
        "confidence": record.get("confidence", {}),
        "component_versions": record.get("component_versions", {}),
        "citations": record.get("citations", []),
        "events": record.get("events", []),
    }

    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO clinical_decisions (
                decision_id, telefon, kimin_icin, istek, final_answer, final_action,
                risk_score, confidence_score, confidence_data, component_versions,
                citations, created_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            safe_record["decision_id"],
            safe_record.get("telefon", ""),
            safe_record.get("kimin_icin", ""),
            safe_record.get("request", ""),
            safe_record.get("final_answer", ""),
            safe_record.get("final_action", ""),
            safe_record.get("risk_score", 0.0),
            safe_record.get("confidence_score", 0.0),
            dumps_redacted_json(safe_record.get("confidence", {})),
            dumps_redacted_json(safe_record.get("component_versions", {})),
            dumps_redacted_json(safe_record.get("citations", [])),
            safe_record.get("created_at", datetime.now().isoformat()),
            safe_record.get("completed_at", datetime.now().isoformat()),
        ))

        cursor.execute(
            "DELETE FROM decision_events WHERE decision_id = ?",
            (safe_record["decision_id"],),
        )
        for index, event in enumerate(safe_record.get("events", []), start=1):
            cursor.execute("""
                INSERT INTO decision_events (
                    decision_id, sequence_no, event_type, component,
                    status, metadata, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                safe_record["decision_id"],
                index,
                event.get("event_type", ""),
                event.get("component", ""),
                event.get("status", "ok"),
                dumps_redacted_json(event.get("metadata", {})),
                event.get("created_at", datetime.now().isoformat()),
            ))

        _conn.commit()


def klinik_karar_getir(decision_id: str, conn: sqlite3.Connection = None) -> dict | None:
    """Fetch one clinical decision with its event chain."""
    _ensure_db()
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute(
            "SELECT * FROM clinical_decisions WHERE decision_id = ?",
            (decision_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        columns = [col[0] for col in cursor.description]
        decision = dict(zip(columns, row))
        for key in ("confidence_data", "component_versions", "citations"):
            try:
                decision[key] = json.loads(decision.get(key) or "{}")
            except json.JSONDecodeError:
                decision[key] = {} if key != "citations" else []

        cursor.execute("""
            SELECT sequence_no, event_type, component, status, metadata, created_at
            FROM decision_events
            WHERE decision_id = ?
            ORDER BY sequence_no ASC
        """, (decision_id,))
        event_columns = [col[0] for col in cursor.description]
        events = []
        for event_row in cursor.fetchall():
            event = dict(zip(event_columns, event_row))
            try:
                event["metadata"] = json.loads(event.get("metadata") or "{}")
            except json.JSONDecodeError:
                event["metadata"] = {}
            events.append(event)
        decision["events"] = events
        return decision


def klinik_kararlari_getir(
    telefon: str,
    limit: int = 10,
    offset: int = 0,
    conn: sqlite3.Connection = None,
) -> list[dict]:
    """List recent clinical decisions for one user."""
    _ensure_db()
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute("""
            SELECT decision_id, kimin_icin, istek, final_action, risk_score,
                   confidence_score, created_at, completed_at
            FROM clinical_decisions
            WHERE telefon = ?
            ORDER BY completed_at DESC
            LIMIT ? OFFSET ?
        """, (telefon, limit, offset))
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def klinik_kpi_getir(telefon: str, conn: sqlite3.Connection = None) -> dict:
    """Calculate operational clinical KPIs for one user's audit records."""
    _ensure_db()
    with get_connection(conn) as _conn:
        cursor = _conn.cursor()
        cursor.execute("""
            SELECT decision_id, risk_score, confidence_score, confidence_data,
                   citations, final_action, completed_at
            FROM clinical_decisions
            WHERE telefon = ?
        """, (telefon,))
        decision_columns = [col[0] for col in cursor.description]
        decisions = []
        decision_ids = []
        for row in cursor.fetchall():
            decision = dict(zip(decision_columns, row))
            decision_ids.append(decision["decision_id"])
            for key in ("confidence_data", "citations"):
                try:
                    decision[key] = json.loads(decision.get(key) or ("[]" if key == "citations" else "{}"))
                except json.JSONDecodeError:
                    decision[key] = [] if key == "citations" else {}
            decisions.append(decision)

        if not decision_ids:
            return calculate_clinical_kpis([], [])

        placeholders = ",".join("?" for _ in decision_ids)
        cursor.execute(f"""
            SELECT decision_id, event_type, component, status, metadata, created_at
            FROM decision_events
            WHERE decision_id IN ({placeholders})
        """, decision_ids)
        event_columns = [col[0] for col in cursor.description]
        events = []
        for row in cursor.fetchall():
            event = dict(zip(event_columns, row))
            try:
                event["metadata"] = json.loads(event.get("metadata") or "{}")
            except json.JSONDecodeError:
                event["metadata"] = {}
            events.append(event)

        return calculate_clinical_kpis(decisions, events)
