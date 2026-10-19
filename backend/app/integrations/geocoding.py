"""Reverse geocoding (coordinates -> street address) via OpenStreetMap Nominatim.

Used only to show staff a readable address for a location the customer shared
in Telegram. The customer's coordinates are sent to Nominatim for that lookup
(public instance: low volume, identified User-Agent, no bulk use). Any failure
returns None and the bot asks the customer to type the address instead.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("synora.geocoding")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "SYNORA-restaurant-orders/1.0 (order address lookup)"
_TIMEOUT = httpx.Timeout(6.0)


def format_address(payload: dict) -> str | None:
    addr = payload.get("address") or {}
    street = addr.get("road") or addr.get("pedestrian") or addr.get("footway") or addr.get("residential")
    house = addr.get("house_number")
    area = addr.get("neighbourhood") or addr.get("suburb") or addr.get("quarter") or addr.get("city_district")
    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality")
    parts = []
    if city:
        parts.append(city)
    if area:
        parts.append(area)
    if street:
        parts.append(f"{street} {house}".strip() if house else street)
    elif house:
        parts.append(f"uy {house}")
    if parts:
        return ", ".join(parts)
    name = (payload.get("display_name") or "").strip()
    return name[:200] or None


async def reverse_geocode(lat: float, lng: float) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _USER_AGENT}) as client:
            response = await client.get(
                NOMINATIM_URL,
                params={
                    "format": "jsonv2",
                    "lat": f"{lat:.6f}",
                    "lon": f"{lng:.6f}",
                    "zoom": 18,
                    "addressdetails": 1,
                    "accept-language": "uz,ru",
                },
            )
        if response.status_code != 200:
            return None
        return format_address(response.json())
    except Exception:  # noqa: BLE001 — geocoding is best-effort
        logger.warning("reverse geocoding failed")
        return None
