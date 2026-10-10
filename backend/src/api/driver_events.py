"""Ingress from the NUT container's native driver event bridge.

This route is excluded from the global API-token middleware and authenticated
with a dedicated shared secret (``NUT_EVENT_SECRET``) so that the NUT container
never needs the full-privilege API token, and the browser-visible API token
cannot be used to inject UPS power states.
"""
import hmac
import os
import time
from typing import Dict, Literal, Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from services.monitor import get_monitor

router = APIRouter()

DRIVER_EVENT_PATH = '/api/system/driver-event'
MIN_SECRET_LENGTH = 16


class DriverFrame(BaseModel):
    variables: Dict[str, str] = Field(default_factory=dict)
    healthy: bool
    reason: Literal['STATUS', 'UPDATE', 'HEARTBEAT', 'DISCONNECTED']
    created_at: float


def bridge_secret() -> str:
    return os.environ.get('NUT_EVENT_SECRET', '')


@router.post('/system/driver-event')
async def receive_driver_event(
        frame: DriverFrame,
        x_nut_event_secret: Optional[str] = Header(default=None)):
    if os.environ.get('NUT_EVENT_BRIDGE') != 'true':
        raise HTTPException(404, 'Not found')
    secret = bridge_secret()
    if len(secret) < MIN_SECRET_LENGTH:
        raise HTTPException(503, 'NUT_EVENT_SECRET is not configured')
    if not x_nut_event_secret or not hmac.compare_digest(
            x_nut_event_secret.encode(), secret.encode()):
        raise HTTPException(401, 'Invalid driver event secret')
    monitor = get_monitor()
    if not monitor:
        raise HTTPException(503, 'Monitor not ready')
    if not -5 <= time.time() - frame.created_at <= 30:
        raise HTTPException(422, 'Expired driver frame')
    if len(frame.variables) > 512 or any(len(k) > 256 or len(v) > 8192 for k, v in frame.variables.items()):
        raise HTTPException(422, 'Invalid driver frame size')
    active = monitor.ingest_driver_frame(frame.variables, frame.healthy, frame.reason)
    return {'accepted': True, 'event_mode_active': active}
