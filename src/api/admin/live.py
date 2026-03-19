import datetime
import json
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import date

from fastapi import APIRouter, Body, Query

from src.config.settings import settings
from src.db.live_store import (
    get_agent_config,
    get_recent_call_events,
    get_recent_calls,
    get_recent_reservations,
    get_recent_transcripts,
    get_system_settings_summary,
    update_agent_config,
)
from src.db.sql_stock import delete_room_config, ensure_horizon, get_month_availability, get_room_catalog, toggle_room_active, upsert_room_config

router = APIRouter()

POSITIVE_WORDS = {
    'merci',
    'parfait',
    'super',
    'ok',
    'daccord',
    "d'accord",
    'excellent',
    'convient',
    'valide',
    'confirme',
    'top',
}
NEGATIVE_WORDS = {
    'non',
    'annuler',
    'annule',
    'probleme',
    'mauvais',
    'pas',
    'jamais',
    'dommage',
    'attendre',
    'impossible',
}


@contextmanager
def _conn():
    url = settings.database_url
    path = url.replace('sqlite:///', '', 1) if url.startswith('sqlite:///') else 'hotel_stock.db'
    conn = sqlite3.connect(path)
    try:
        yield conn
    finally:
        conn.close()


def _safe_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _normalize_period(period: str) -> str:
    value = (period or 'week').strip().lower()
    return value if value in {'day', 'week', 'month'} else 'week'


def _period_start_iso(period: str) -> str:
    normalized = _normalize_period(period)
    days = {'day': 1, 'week': 7, 'month': 30}[normalized]
    start = datetime.datetime.utcnow() - datetime.timedelta(days=days - 1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat()


def _room_price_map() -> dict[str, int]:
    items = get_room_catalog(active_only=False)
    return {(i.get('room_type') or '').strip().lower(): int(i.get('price_eur') or 0) for i in items}


def _sentiment_score(text: str) -> int:
    lowered = (text or '').lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in lowered)
    neg = sum(1 for w in NEGATIVE_WORDS if w in lowered)
    return pos - neg


def _load_calls_in_period(period: str) -> dict[str, dict]:
    start_iso = _period_start_iso(period)
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT call_sid, event_type, payload_json, created_at
            FROM live_call_events
            WHERE created_at >= ?
            ORDER BY id ASC
            """,
            (start_iso,),
        ).fetchall()

    calls: dict[str, dict] = {}
    for call_sid, event_type, payload_json, created_at in rows:
        if not call_sid:
            continue
        item = calls.setdefault(
            call_sid,
            {
                'call_sid': call_sid,
                'events': 0,
                'last_seen': created_at,
                'started_at': created_at,
                'caller_number': None,
                'finalized_at': None,
                'booking_payload': {},
            },
        )
        item['events'] += 1
        item['last_seen'] = created_at
        payload = _safe_json(payload_json)

        if event_type == 'call_started' and not item['caller_number']:
            number = (payload.get('caller_number') or '').strip()
            item['caller_number'] = number or None
            item['started_at'] = created_at

        if event_type == 'booking_finalized':
            item['finalized_at'] = created_at
            item['booking_payload'] = payload or {}

    return calls


def _load_reservations_by_call(period: str) -> dict[str, dict]:
    start_iso = _period_start_iso(period)
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT call_sid, reservation_ref, room_type, guests, check_in_date, check_out_date,
                   nights, sms_sent, sms_status, sms_error, created_at
            FROM live_reservations
            WHERE created_at >= ?
            ORDER BY id DESC
            """,
            (start_iso,),
        ).fetchall()

    by_call: dict[str, dict] = {}
    for r in rows:
        call_sid = r[0]
        if not call_sid or call_sid in by_call:
            continue
        by_call[call_sid] = {
            'call_sid': call_sid,
            'reservation_ref': r[1],
            'room_type': r[2],
            'guests': r[3],
            'check_in_date': r[4],
            'check_out_date': r[5],
            'nights': r[6],
            'sms_sent': bool(r[7]),
            'sms_status': r[8],
            'sms_error': r[9],
            'created_at': r[10],
        }
    return by_call


def _load_user_turns(period: str) -> dict[str, list[tuple[str, str]]]:
    start_iso = _period_start_iso(period)
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT call_sid, text, created_at
            FROM live_transcripts
            WHERE created_at >= ? AND speaker = 'user'
            ORDER BY id ASC
            """,
            (start_iso,),
        ).fetchall()

    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for call_sid, text, created_at in rows:
        if call_sid:
            grouped[call_sid].append((text or '', created_at))
    return grouped


def _build_success_calls(period: str) -> list[dict]:
    calls = _load_calls_in_period(period)
    reservations = _load_reservations_by_call(period)
    user_turns = _load_user_turns(period)
    prices = _room_price_map()

    out: list[dict] = []
    for call_sid, call_info in calls.items():
        reservation = reservations.get(call_sid)
        if not reservation:
            continue

        sms_sent = bool(reservation.get('sms_sent'))
        finalized = bool(call_info.get('finalized_at'))
        if not (sms_sent and finalized):
            continue

        room_type = (reservation.get('room_type') or 'standard').strip().lower()
        nights = int(reservation.get('nights') or 0)
        unit_price = int(prices.get(room_type, 0))
        total_price = unit_price * max(0, nights)

        turns = user_turns.get(call_sid, [])
        score = 0
        for text, created_at in turns:
            if call_info.get('finalized_at') and created_at <= call_info['finalized_at']:
                score += _sentiment_score(text)

        satisfaction_label = 'satisfait' if score >= 0 else 'insatisfait'

        out.append(
            {
                'call_sid': call_sid,
                'timestamp': reservation.get('created_at') or call_info.get('last_seen'),
                'phone_number': call_info.get('caller_number'),
                'reservation_ref': reservation.get('reservation_ref'),
                'room_type': room_type,
                'guests': reservation.get('guests'),
                'nights': nights,
                'check_in_date': reservation.get('check_in_date'),
                'check_out_date': reservation.get('check_out_date'),
                'price_total_eur': total_price,
                'status': 'confirmee',
                'sms_status': reservation.get('sms_status'),
                'sentiment_score': score,
                'satisfaction': satisfaction_label,
                'turns_before_confirmation': len([1 for _, created_at in turns if created_at <= call_info['finalized_at']]),
            }
        )

    out.sort(key=lambda x: x.get('timestamp') or '', reverse=True)
    return out


def _usage_series(period: str) -> list[dict]:
    start_iso = _period_start_iso(period)
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT DATE(created_at) as day, COUNT(DISTINCT call_sid) as calls
            FROM live_call_events
            WHERE created_at >= ? AND call_sid IS NOT NULL
            GROUP BY DATE(created_at)
            ORDER BY day ASC
            """,
            (start_iso,),
        ).fetchall()

    data_map = {r[0]: int(r[1]) for r in rows}
    normalized = _normalize_period(period)
    days = {'day': 1, 'week': 7, 'month': 30}[normalized]
    start_day = (datetime.datetime.utcnow() - datetime.timedelta(days=days - 1)).date()

    items: list[dict] = []
    for i in range(days):
        d = start_day + datetime.timedelta(days=i)
        iso = d.isoformat()
        items.append({'day': iso, 'calls': data_map.get(iso, 0)})
    return items


def _revenue_for_days(days: int) -> int:
    start = datetime.datetime.utcnow() - datetime.timedelta(days=max(1, days) - 1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    start_iso = start.isoformat()
    prices = _room_price_map()

    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT room_type, nights
            FROM live_reservations
            WHERE created_at >= ? AND sms_sent = 1
            """,
            (start_iso,),
        ).fetchall()

    total = 0
    for room_type, nights in rows:
        rt = (room_type or 'standard').strip().lower()
        total += int(prices.get(rt, 0)) * max(0, int(nights or 0))
    return total


@router.get('/health')
async def admin_health():
    return {'status': 'ok'}


@router.get('/calls')
async def calls(limit: int = Query(default=30, ge=1, le=200)):
    return {'items': get_recent_calls(limit=limit)}


@router.get('/events')
async def events(call_sid: str | None = None, limit: int = Query(default=200, ge=1, le=500)):
    return {'items': get_recent_call_events(call_sid=call_sid, limit=limit)}


@router.get('/transcripts')
async def transcripts(call_sid: str | None = None, limit: int = Query(default=200, ge=1, le=500)):
    return {'items': get_recent_transcripts(call_sid=call_sid, limit=limit)}


@router.get('/reservations')
async def reservations(limit: int = Query(default=100, ge=1, le=500)):
    return {'items': get_recent_reservations(limit=limit)}


@router.get('/dashboard/summary-cards')
async def dashboard_summary_cards(period: str = Query(default='week')):
    normalized = _normalize_period(period)
    calls = _load_calls_in_period(normalized)
    success_calls = _build_success_calls(normalized)
    success_by_call = {item['call_sid'] for item in success_calls}

    total_calls = len(calls)
    successful_calls = len(success_by_call)
    total_events = sum(c.get('events', 0) for c in calls.values())

    confirmation_rate = round((successful_calls / total_calls) * 100, 1) if total_calls else 0.0
    abandonment_rate = round(max(0.0, 100.0 - confirmation_rate), 1) if total_calls else 0.0

    turns_values = [int(item.get('turns_before_confirmation') or 0) for item in success_calls]
    avg_turns = round(sum(turns_values) / len(turns_values), 1) if turns_values else 0.0

    satisfied = sum(1 for item in success_calls if item.get('satisfaction') == 'satisfait')
    satisfaction_pct = round((satisfied / len(success_calls)) * 100, 1) if success_calls else 0.0

    return {
        'period': normalized,
        'calls_detected': total_calls,
        'successful_calls': successful_calls,
        'events_total': total_events,
        'confirmation_rate': confirmation_rate,
        'abandonment_rate': abandonment_rate,
        'avg_turns_before_confirmation': avg_turns,
        'customer_satisfaction_post_call_pct': satisfaction_pct,
    }


@router.get('/dashboard/success-calls')
async def dashboard_success_calls(
    period: str = Query(default='week'),
    limit: int = Query(default=10, ge=1, le=100),
):
    items = _build_success_calls(_normalize_period(period))
    return {'period': _normalize_period(period), 'items': items[:limit]}


@router.get('/dashboard/revenue')
async def dashboard_revenue():
    day_revenue = _revenue_for_days(1)
    week_revenue = _revenue_for_days(7)
    month_revenue = _revenue_for_days(30)

    success_calls = _build_success_calls('month')
    avg_basket = round(month_revenue / len(success_calls), 1) if success_calls else 0.0

    return {
        'day_eur': day_revenue,
        'week_eur': week_revenue,
        'month_eur': month_revenue,
        'average_basket_eur': avg_basket,
    }


@router.get('/dashboard/usage')
async def dashboard_usage(period: str = Query(default='week')):
    normalized = _normalize_period(period)
    items = _usage_series(normalized)
    return {
        'period': normalized,
        'items': items,
    }


@router.get('/dashboard/conversion-metrics')
async def dashboard_conversion_metrics(period: str = Query(default='week')):
    normalized = _normalize_period(period)
    calls = _load_calls_in_period(normalized)
    success_calls = _build_success_calls(normalized)

    total_calls = len(calls)
    successful_calls = len(success_calls)
    confirmation_rate = round((successful_calls / total_calls) * 100, 1) if total_calls else 0.0
    abandonment_rate = round(max(0.0, 100.0 - confirmation_rate), 1) if total_calls else 0.0

    # SMS KPI on full call base (not only successful calls) to avoid misleading 100%.
    sms_ok = 0
    for call in calls.values():
        payload = call.get('booking_payload') or {}
        if payload.get('sms_sent') is True and str(payload.get('sms_status') or '').startswith('20'):
            sms_ok += 1
    sms_success_rate = round((sms_ok / total_calls) * 100, 1) if total_calls else 0.0

    avg_turns = 0.0
    if successful_calls:
        avg_turns = round(
            sum(float(item.get('turns_before_confirmation') or 0) for item in success_calls) / successful_calls,
            1,
        )

    bars = [
        {'key': 'confirmation_rate', 'label': 'Taux de confirmation', 'value': confirmation_rate, 'unit': '%'},
        {'key': 'abandonment_rate', 'label': 'Taux d abandon', 'value': abandonment_rate, 'unit': '%'},
        {'key': 'sms_success_rate', 'label': 'SMS delivres', 'value': sms_success_rate, 'unit': '%'},
        {'key': 'avg_turns', 'label': 'Tours avant confirmation', 'value': avg_turns, 'unit': ''},
    ]

    return {
        'period': normalized,
        'bars': bars,
    }


@router.get('/agent-config')
async def agent_config():
    return get_agent_config()


@router.put('/agent-config')
async def agent_config_update(payload: dict = Body(...)):
    return update_agent_config(payload)


@router.get('/settings')
async def settings_summary():
    return get_system_settings_summary()


@router.get('/inventory/rooms')
async def inventory_rooms(active_only: bool = Query(default=False)):
    return {'items': get_room_catalog(active_only=active_only)}


@router.put('/inventory/rooms')
async def inventory_room_upsert(payload: dict = Body(...)):
    item = upsert_room_config(payload)
    return {'item': item, 'items': get_room_catalog(active_only=False)}

@router.delete("/inventory/rooms/{room_type:path}")
async def inventory_room_delete(room_type: str):
    from fastapi import HTTPException
    result = delete_room_config(room_type)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("reason", "categorie_introuvable"))
    return {"ok": True, "items": get_room_catalog(active_only=False)}


@router.patch("/inventory/rooms/{room_type:path}")
async def inventory_room_toggle(room_type: str, is_active: bool = Query(..., description="actif/bloque")):
    from fastapi import HTTPException
    result = toggle_room_active(room_type, is_active)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("reason", "categorie_introuvable"))
    return {"ok": True, "item": result, "items": get_room_catalog(active_only=False)}


@router.post('/inventory/seed')
async def inventory_seed(days: int = Body(default=120, embed=True)):
    inserted = ensure_horizon(days=max(1, int(days)))
    return {'ok': True, 'inserted': inserted, 'days': days}


@router.get('/inventory/month')
async def inventory_month(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
):
    today = date.today()
    y = year or today.year
    m = month or today.month
    ensure_horizon(days=120)
    return get_month_availability(y, m)
