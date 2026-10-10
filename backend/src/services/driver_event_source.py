"""Select native driver events, with opt-in NUT polling during stream failure."""
import time

# The bridge sends a heartbeat every 15s; two missed heartbeats plus margin.
BRIDGE_STALE_SECONDS = 35
# Queued ups.status edges older than this are dropped instead of replayed.
STATUS_EDGE_MAX_AGE = 25


async def read_driver_variables(monitor):
    """Return ``(variables, source)``.

    ``source`` is ``'event'`` for a newly received frame, ``'cache'`` when the
    healthy snapshot has not changed since the last read, and ``'poll'`` when
    the stream is unavailable and NUT was queried as a fallback.  Only a fresh,
    healthy event snapshot suppresses NUT network reads.
    """
    now = time.monotonic()
    healthy = now - monitor._driver_bridge_seen < BRIDGE_STALE_SECONDS and bool(
        monitor._driver_bridge_data.get('ups.status'))
    monitor._event_mode_active = healthy
    while monitor._driver_bridge_statuses and now - monitor._driver_bridge_statuses[0][0] > STATUS_EDGE_MAX_AGE:
        monitor._driver_bridge_statuses.popleft()
    if healthy:
        if monitor._driver_bridge_statuses:
            return monitor._driver_bridge_statuses.popleft()[1], 'event'
        fresh = monitor._driver_bridge_seq != monitor._driver_bridge_consumed_seq
        monitor._driver_bridge_consumed_seq = monitor._driver_bridge_seq
        return dict(monitor._driver_bridge_data), 'event' if fresh else 'cache'
    monitor._driver_bridge_statuses.clear()
    if monitor.config.event_driven_fallback:
        # list_vars handles reconnects and raises on stale/unavailable UPS data.
        # Never substitute the old event snapshot when this query fails.
        return await monitor.nut_client.list_vars(), 'poll'
    return {}, 'poll'
