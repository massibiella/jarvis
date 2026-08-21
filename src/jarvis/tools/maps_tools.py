"""Native TomTom maps tool: distance/travel-time between two locations,
including live traffic impact. Same shape as weather_tools.py /
web_browsing_tools.py — plain HTTP calls, no MCP subprocess.

Swapped in for Google Maps: Google requires an active billing account
(card on file) before its APIs work at all, even fully within the free
quota. TomTom's free tier (2,500 requests/day) needs no card and still
gives live traffic-aware ETAs — closest match to what Google offered,
without that friction.

Two TomTom calls per lookup, not one: unlike Google's Distance Matrix
API, TomTom's Routing API takes coordinates, not free-text addresses —
so a place name has to be geocoded first (Search API), then routed
(Routing API). Both share one API key (TOMTOM_API_KEY).
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx2

from jarvis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_GEOCODE_URL = "https://api.tomtom.com/search/2/geocode/{query}.json"
_ROUTE_URL = "https://api.tomtom.com/routing/1/calculateRoute/{origin}:{destination}/json"

# TomTom's travelMode vocabulary, mapped from the friendlier names we expose
# to the model. TomTom has no transit-routing mode, unlike Google's API.
_MODE_MAP = {"driving": "car", "walking": "pedestrian", "bicycling": "bicycle"}


def _format_duration(total_seconds: float) -> str:
    minutes = round(total_seconds / 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} hr {minutes} min" if hours else f"{minutes} min"


async def _geocode(
    client: httpx2.AsyncClient, api_key: str, place: str
) -> tuple[float, float] | None:
    response = await client.get(
        _GEOCODE_URL.format(query=quote(place, safe="")), params={"key": api_key, "limit": 1}
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        return None
    position = results[0]["position"]
    return position["lat"], position["lon"]


def register_maps_tools(tools: ToolRegistry) -> None:
    @tools.register()
    async def get_travel_time(origin: str, destination: str, mode: str = "driving") -> str:
        """Get travel distance and time between two locations (addresses,
        place names, or landmarks). For mode="driving" (the default),
        also reports current traffic conditions — how much longer the
        trip is taking right now vs. normal. mode: "driving", "walking",
        or "bicycling"."""
        if mode not in _MODE_MAP:
            return f"Invalid mode {mode!r}. Choose one of: {', '.join(sorted(_MODE_MAP))}."

        api_key = os.environ.get("TOMTOM_API_KEY")
        if not api_key:
            return (
                "Maps is not configured: set the TOMTOM_API_KEY "
                "environment variable (see .env.example)."
            )

        try:
            async with httpx2.AsyncClient(timeout=30.0) as client:
                origin_coords = await _geocode(client, api_key, origin)
                if origin_coords is None:
                    return f"Couldn't find a location matching '{origin}'."
                destination_coords = await _geocode(client, api_key, destination)
                if destination_coords is None:
                    return f"Couldn't find a location matching '{destination}'."

                response = await client.get(
                    _ROUTE_URL.format(
                        origin=f"{origin_coords[0]},{origin_coords[1]}",
                        destination=f"{destination_coords[0]},{destination_coords[1]}",
                    ),
                    params={"key": api_key, "traffic": "true", "travelMode": _MODE_MAP[mode]},
                )
                response.raise_for_status()
                data = response.json()
        except httpx2.HTTPError as e:
            logger.error("TomTom request failed for %r -> %r: %s", origin, destination, e)
            return f"Sorry, couldn't get travel time from '{origin}' to '{destination}' right now."

        routes = data.get("routes")
        if not routes:
            return f"Couldn't find a route from '{origin}' to '{destination}'."

        summary = routes[0]["summary"]
        distance_km = summary["lengthInMeters"] / 1000
        travel_seconds = summary["travelTimeInSeconds"]
        delay_seconds = summary.get("trafficDelayInSeconds", 0)
        duration = _format_duration(travel_seconds)

        if mode != "driving" or delay_seconds <= 60:
            return f"{origin} to {destination}: {distance_km:.1f} km, {duration} ({mode})."

        normal_duration = _format_duration(travel_seconds - delay_seconds)
        delay_minutes = round(delay_seconds / 60)
        return (
            f"{origin} to {destination}: {distance_km:.1f} km, {duration} in current traffic "
            f"(+{delay_minutes} min vs. normal {normal_duration})."
        )
