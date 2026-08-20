"""Native weather tool, calling Open-Meteo directly.

Moved from a standalone MCP server (weather-mcp) to a native tool —
weather isn't meaningfully reused outside Jarvis in practice, and Google
Calendar already exercises the MCP-client code path (MCPToolClient,
add_tool(), the whole subprocess/stdio machinery), so there's no
remaining reason to pay subprocess-spawn overhead for what's really one
simple HTTP call. See docs/PLAN.md for the full reasoning behind moving
this off MCP. weather-mcp itself still exists as a standalone repo,
just no longer used by Jarvis.

Logic ported unchanged from weather-mcp's weather.py — same geocoding
+ forecast calls, same WMO weather-code mapping, same error handling
(httpx2.HTTPError specifically, not a bare except, so bugs in our own
code still crash loudly instead of being hidden).
"""

from __future__ import annotations

import logging

import httpx2

from jarvis.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
}


def register_weather_tools(tools: ToolRegistry) -> None:
    @tools.register()
    async def get_current_weather(location: str) -> str:
        """Get current weather for a location (a city or town name)."""
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"

        try:
            async with httpx2.AsyncClient(timeout=30.0) as client:
                geocode_response = await client.get(geocode_url)
                geocode_response.raise_for_status()
                geocode_data = geocode_response.json()

                results = geocode_data.get("results")
                if not results:
                    return f"Could not find a location named '{location}'."

                place = results[0]
                latitude, longitude = place["latitude"], place["longitude"]

                weather_url = (
                    f"https://api.open-meteo.com/v1/forecast"
                    f"?latitude={latitude}&longitude={longitude}&current=temperature_2m,weather_code"
                )
                weather_response = await client.get(weather_url)
                weather_response.raise_for_status()
                weather_data = weather_response.json()

                temperature = weather_data["current"]["temperature_2m"]
                weather_code = weather_data["current"]["weather_code"]
                conditions = _WEATHER_CODES.get(weather_code, "unknown conditions")

                place_label = f"{place['name']}, {place.get('admin1', place['country'])}"
                return f"{place_label}: {temperature}°C, {conditions}"
        except httpx2.HTTPError as e:
            logger.error("Failed to get weather for %r: %s", location, e)
            return f"Sorry, couldn't get the weather for '{location}' right now."
