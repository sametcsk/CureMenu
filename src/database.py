"""
CureMenu — Veritabanı Katmanımız (SQLite)
Kullanıcı profillerini ve logları şimdilik lokalde (SQLite) tutuyoruz.
İleride canlıya (Production) çıkarken kolayca PostgreSQL'e geçebilelim diye veri katmanını izole ettik.
"""
import sqlite3
import json
import hashlib
import time
from datetime import datetime
from src.models import KullaniciProfili
from src.logger import get_logger, log_failure
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
        logger.debug("Column sifre_hash already exists, skipping")

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
        logger.debug("Column metadata already exists in interaction_logs, skipping")

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS revoked_refresh_tokens (
            jti_hash TEXT PRIMARY KEY,
            expires_at INTEGER NOT NULL,
            revoked_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_revoked_refresh_tokens_expires_at
        ON revoked_refresh_tokens(expires_at)
    """)

    conn.commit()
    conn.close()
    _db_initialized = True


def _refresh_jti_hash(jti: str) -> str:
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def refresh_token_jti_is_revoked_db(jti: str | None, conn: sqlite3.Connection = None) -> bool:
    if not jti:
        return False
    _ensure_db()
    with get_connection(conn) as _conn:
        row = _conn.execute(
            "SELECT 1 FROM revoked_refresh_tokens WHERE jti_hash = ?",
            (_refresh_jti_hash(jti),),
        ).fetchone()
        return row is not None


def refresh_token_jti_consume_db(
    jti: str | None,
    expires_at: int | float | None,
    conn: sqlite3.Connection = None,
) -> bool:
    """Atomically consume a refresh JTI; False means it was already consumed."""
    if not jti:
        return False
    _ensure_db()
    expiry = int(expires_at or time.time())
    with get_connection(conn) as _conn:
        _conn.execute(
            "DELETE FROM revoked_refresh_tokens WHERE expires_at < ?",
            (int(time.time()),),
        )
        cursor = _conn.execute(
            """
            INSERT OR IGNORE INTO revoked_refresh_tokens (jti_hash, expires_at, revoked_at)
            VALUES (?, ?, ?)
            """,
            (_refresh_jti_hash(jti), expiry, datetime.now().isoformat()),
        )
        _conn.commit()
        return cursor.rowcount == 1


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
                log_failure(logger, "profile_json_parse", e, component="database")
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
            SELECT id, kullanici_adi, sayfa, istek, cevap, metadata, tarih
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
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error (clinical_decisions.{key}): {e}")
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
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error (decision_events.metadata): {e}")
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
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error (clinical_decisions.{key} in kpi): {e}")
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
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error (decision_events.metadata): {e}")
                event["metadata"] = {}
            events.append(event)

        return calculate_clinical_kpis(decisions, events)


def account_export_db(telefon: str, conn: sqlite3.Connection = None) -> dict | None:
    """Return one account's persisted data without password material."""
    _ensure_db()
    with get_connection(conn) as _conn:
        profile_row = _conn.execute(
            """
            SELECT telefon, kullanici_adi, profil_data, kayit_tarihi, son_guncelleme
            FROM profiles WHERE telefon = ?
            """,
            (telefon,),
        ).fetchone()
        if not profile_row:
            return None

        profile_columns = ["telefon", "kullanici_adi", "profil_data", "kayit_tarihi", "son_guncelleme"]
        profile = dict(zip(profile_columns, profile_row))
        try:
            profile["profil_data"] = json.loads(profile["profil_data"] or "{}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error (profiles.profil_data in export): {e}")
            profile["profil_data"] = {}

        interactions = loglari_getir_db(telefon, limit=100_000, offset=0, conn=_conn)
        for interaction in interactions:
            try:
                interaction["metadata"] = json.loads(interaction.get("metadata") or "{}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error (interaction_logs.metadata in export): {e}")
                interaction["metadata"] = {}

        decision_cursor = _conn.execute(
            """
            SELECT decision_id, kimin_icin, istek, final_answer, final_action,
                   risk_score, confidence_score, confidence_data, component_versions,
                   citations, created_at, completed_at
            FROM clinical_decisions WHERE telefon = ? ORDER BY completed_at DESC
            """,
            (telefon,),
        )
        decision_columns = [column[0] for column in decision_cursor.description]
        decisions = [dict(zip(decision_columns, row)) for row in decision_cursor.fetchall()]
        decision_ids = [decision["decision_id"] for decision in decisions]
        events: list[dict] = []
        if decision_ids:
            placeholders = ",".join("?" for _ in decision_ids)
            event_cursor = _conn.execute(
                f"""
                SELECT decision_id, sequence_no, event_type, component, status, metadata, created_at
                FROM decision_events WHERE decision_id IN ({placeholders})
                ORDER BY decision_id, sequence_no
                """,
                decision_ids,
            )
            event_columns = [column[0] for column in event_cursor.description]
            events = [dict(zip(event_columns, row)) for row in event_cursor.fetchall()]

        return {
            "schema_version": "1",
            "exported_at": datetime.now().isoformat(),
            "profile": profile,
            "interactions": interactions,
            "clinical_decisions": decisions,
            "decision_events": events,
        }


def account_memory_metadata_db(telefon: str, conn: sqlite3.Connection = None) -> list[dict]:
    """Return lifecycle metadata needed to remove historical user-memory namespaces."""
    _ensure_db()
    with get_connection(conn) as _conn:
        rows = _conn.execute(
            "SELECT metadata FROM interaction_logs WHERE telefon = ? AND metadata IS NOT NULL",
            (telefon,),
        ).fetchall()
    result: list[dict] = []
    for (raw_metadata,) in rows:
        try:
            metadata = json.loads(raw_metadata or "{}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error (account_memory_metadata_db): {e}")
            continue
        if isinstance(metadata, dict):
            result.append(metadata)
    return result


def delete_account_relational_db(telefon: str, conn: sqlite3.Connection = None) -> dict[str, int]:
    """Delete one account's relational records in a single SQLite transaction."""
    _ensure_db()
    with get_connection(conn) as _conn:
        try:
            _conn.execute("BEGIN")
            decision_ids = [
                row[0]
                for row in _conn.execute(
                    "SELECT decision_id FROM clinical_decisions WHERE telefon = ?",
                    (telefon,),
                ).fetchall()
            ]
            event_count = 0
            if decision_ids:
                placeholders = ",".join("?" for _ in decision_ids)
                event_count = _conn.execute(
                    f"DELETE FROM decision_events WHERE decision_id IN ({placeholders})",
                    decision_ids,
                ).rowcount
            decision_count = _conn.execute(
                "DELETE FROM clinical_decisions WHERE telefon = ?", (telefon,)
            ).rowcount
            interaction_count = _conn.execute(
                "DELETE FROM interaction_logs WHERE telefon = ?", (telefon,)
            ).rowcount
            profile_count = _conn.execute(
                "DELETE FROM profiles WHERE telefon = ?", (telefon,)
            ).rowcount
            _conn.commit()
        except Exception:
            _conn.rollback()
            raise
    return {
        "profiles": profile_count,
        "interactions": interaction_count,
        "clinical_decisions": decision_count,
        "decision_events": event_count,
    }

def retention_summary_db(
    cutoff_iso: str,
    *,
    apply: bool = False,
    conn: sqlite3.Connection = None,
) -> dict[str, int]:
    """Count or delete expired interaction and decision records without touching profiles."""
    _ensure_db()
    with get_connection(conn) as _conn:
        interaction_count = _conn.execute(
            "SELECT COUNT(*) FROM interaction_logs WHERE tarih < ?", (cutoff_iso,)
        ).fetchone()[0]
        decision_ids = [
            row[0]
            for row in _conn.execute(
                "SELECT decision_id FROM clinical_decisions WHERE completed_at < ?",
                (cutoff_iso,),
            ).fetchall()
        ]
        event_count = 0
        if decision_ids:
            placeholders = ",".join("?" for _ in decision_ids)
            event_count = _conn.execute(
                f"SELECT COUNT(*) FROM decision_events WHERE decision_id IN ({placeholders})",
                decision_ids,
            ).fetchone()[0]
        if apply:
            try:
                _conn.execute("BEGIN")
                if decision_ids:
                    placeholders = ",".join("?" for _ in decision_ids)
                    _conn.execute(
                        f"DELETE FROM decision_events WHERE decision_id IN ({placeholders})",
                        decision_ids,
                    )
                _conn.execute(
                    "DELETE FROM clinical_decisions WHERE completed_at < ?", (cutoff_iso,)
                )
                _conn.execute("DELETE FROM interaction_logs WHERE tarih < ?", (cutoff_iso,))
                _conn.commit()
            except Exception:
                _conn.rollback()
                raise
    return {
        "interactions": interaction_count,
        "clinical_decisions": len(decision_ids),
        "decision_events": event_count,
    }
