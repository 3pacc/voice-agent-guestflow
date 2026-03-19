import datetime
import json
import sqlite3
from contextlib import contextmanager

from src.config.settings import settings


def _sqlite_path() -> str:
    url = settings.database_url
    if url.startswith('sqlite:///'):
        return url.replace('sqlite:///', '', 1)
    return 'hotel_stock.db'


@contextmanager
def _conn():
    conn = sqlite3.connect(_sqlite_path())
    try:
        yield conn
    finally:
        conn.close()


def init_live_store() -> None:
    with _conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS live_call_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_sid TEXT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS live_transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_sid TEXT,
                speaker TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS live_reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_sid TEXT,
                reservation_ref TEXT,
                room_type TEXT,
                guests INTEGER,
                check_in_date TEXT,
                check_out_date TEXT,
                nights INTEGER,
                sms_sent INTEGER,
                sms_status TEXT,
                sms_error TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                voice_id TEXT NOT NULL,
                speaking_rate REAL NOT NULL,
                llm_temperature REAL NOT NULL DEFAULT 0.3,
                greeting_text TEXT NOT NULL,
                offer_text TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cols = [row[1] for row in c.execute('PRAGMA table_info(agent_config)').fetchall()]
        if 'llm_temperature' not in cols:
            c.execute('ALTER TABLE agent_config ADD COLUMN llm_temperature REAL NOT NULL DEFAULT 0.3')
            c.execute('UPDATE agent_config SET llm_temperature = COALESCE(llm_temperature, 0.3) WHERE id=1')

        c.execute('SELECT COUNT(*) FROM agent_config')
        if (c.fetchone() or [0])[0] == 0:
            now = datetime.datetime.utcnow().isoformat()
            c.execute(
                """
                INSERT INTO agent_config(id, voice_id, speaking_rate, llm_temperature, greeting_text, offer_text, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    'Mathieu',
                    1.2,
                    0.3,
                    "Bonjour et bienvenue chez GuestFlow Hotel, comment puis-je vous aider aujourd'hui ?",
                    "Offre speciale: petit-dejeuner inclus selon disponibilite.",
                    now,
                ),
            )
        conn.commit()


def append_call_event(call_sid: str | None, event_type: str, payload: dict) -> None:
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            'INSERT INTO live_call_events(call_sid, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)',
            (call_sid, event_type, json.dumps(payload, ensure_ascii=False, default=str), now),
        )
        conn.commit()


def append_transcript(call_sid: str | None, speaker: str, text: str) -> None:
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            'INSERT INTO live_transcripts(call_sid, speaker, text, created_at) VALUES (?, ?, ?, ?)',
            (call_sid, speaker, text, now),
        )
        conn.commit()


def append_reservation(payload: dict) -> None:
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO live_reservations(
                call_sid, reservation_ref, room_type, guests,
                check_in_date, check_out_date, nights,
                sms_sent, sms_status, sms_error, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get('call_sid'),
                payload.get('reservation_ref'),
                payload.get('room_type'),
                payload.get('guests'),
                payload.get('check_in_date'),
                payload.get('check_out_date'),
                payload.get('nights'),
                1 if payload.get('sms_sent') else 0,
                payload.get('sms_status'),
                payload.get('sms_error'),
                now,
            ),
        )
        conn.commit()


def get_recent_calls(limit: int = 30) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT call_sid, MAX(created_at) as last_seen, COUNT(*) as events
            FROM live_call_events
            GROUP BY call_sid
            ORDER BY last_seen DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [{'call_sid': r[0], 'last_seen': r[1], 'events': r[2]} for r in rows]


def get_recent_call_events(call_sid: str | None = None, limit: int = 200) -> list[dict]:
    with _conn() as conn:
        if call_sid:
            rows = conn.execute(
                'SELECT id, call_sid, event_type, payload_json, created_at FROM live_call_events WHERE call_sid=? ORDER BY id DESC LIMIT ?',
                (call_sid, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT id, call_sid, event_type, payload_json, created_at FROM live_call_events ORDER BY id DESC LIMIT ?',
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        try:
            payload = json.loads(r[3])
        except Exception:
            payload = {'raw': r[3]}
        out.append({'id': r[0], 'call_sid': r[1], 'event_type': r[2], 'payload': payload, 'created_at': r[4]})
    return out


def get_recent_transcripts(call_sid: str | None = None, limit: int = 200) -> list[dict]:
    with _conn() as conn:
        if call_sid:
            rows = conn.execute(
                'SELECT id, call_sid, speaker, text, created_at FROM live_transcripts WHERE call_sid=? ORDER BY id DESC LIMIT ?',
                (call_sid, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT id, call_sid, speaker, text, created_at FROM live_transcripts ORDER BY id DESC LIMIT ?',
                (limit,),
            ).fetchall()
    return [{'id': r[0], 'call_sid': r[1], 'speaker': r[2], 'text': r[3], 'created_at': r[4]} for r in rows]


def get_recent_reservations(limit: int = 100) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT id, call_sid, reservation_ref, room_type, guests,
                   check_in_date, check_out_date, nights,
                   sms_sent, sms_status, sms_error, created_at
            FROM live_reservations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            'id': r[0],
            'call_sid': r[1],
            'reservation_ref': r[2],
            'room_type': r[3],
            'guests': r[4],
            'check_in_date': r[5],
            'check_out_date': r[6],
            'nights': r[7],
            'sms_sent': bool(r[8]),
            'sms_status': r[9],
            'sms_error': r[10],
            'created_at': r[11],
        }
        for r in rows
    ]


def get_agent_config() -> dict:
    with _conn() as conn:
        row = conn.execute(
            'SELECT voice_id, speaking_rate, llm_temperature, greeting_text, offer_text, updated_at FROM agent_config WHERE id=1'
        ).fetchone()
    if not row:
        return {
            'voice_id': 'Mathieu',
            'speaking_rate': 1.2,
            'llm_temperature': 0.3,
            'greeting_text': "Bonjour et bienvenue chez GuestFlow Hotel, comment puis-je vous aider aujourd'hui ?",
            'offer_text': 'Offre speciale: petit-dejeuner inclus selon disponibilite.',
            'updated_at': None,
        }
    return {
        'voice_id': row[0],
        'speaking_rate': row[1],
        'llm_temperature': row[2],
        'greeting_text': row[3],
        'offer_text': row[4],
        'updated_at': row[5],
    }


def update_agent_config(payload: dict) -> dict:
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            """
            UPDATE agent_config
            SET voice_id=?, speaking_rate=?, llm_temperature=?, greeting_text=?, offer_text=?, updated_at=?
            WHERE id=1
            """,
            (
                payload.get('voice_id', 'Mathieu'),
                float(payload.get('speaking_rate', 1.2)),
                float(payload.get('llm_temperature', 0.3)),
                payload.get('greeting_text', "Bonjour et bienvenue chez GuestFlow Hotel, comment puis-je vous aider aujourd'hui ?"),
                payload.get('offer_text', 'Offre speciale: petit-dejeuner inclus selon disponibilite.'),
                now,
            ),
        )
        conn.commit()
    return get_agent_config()


def get_system_settings_summary() -> dict:
    with _conn() as conn:
        calls_count = conn.execute('SELECT COUNT(*) FROM live_call_events').fetchone()[0]
        transcripts_count = conn.execute('SELECT COUNT(*) FROM live_transcripts').fetchone()[0]
        reservations_count = conn.execute('SELECT COUNT(*) FROM live_reservations').fetchone()[0]
    return {
        'voice_api_enabled': True,
        'dashboard_enabled': True,
        'sms_enabled': bool(getattr(settings, 'booking_sms_enabled', False)),
        'calls_events_count': calls_count,
        'transcripts_count': transcripts_count,
        'reservations_count': reservations_count,
        'llm_model': getattr(settings, 'llm_model', ''),
        'updated_at': datetime.datetime.utcnow().isoformat(),
    }
