from datetime import date

from fastapi import APIRouter, Body, Query

from src.db.live_store import (
    get_agent_config,
    get_recent_call_events,
    get_recent_calls,
    get_recent_reservations,
    get_recent_transcripts,
    get_system_settings_summary,
    update_agent_config,
)
from src.db.sql_stock import (
    ensure_horizon,
    get_month_availability,
    get_room_catalog,
    upsert_room_config,
)

router = APIRouter()


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
