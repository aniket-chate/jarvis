"""Free-first (₹0 cost) web research and data skills for JARVIS.

Ports DuckDuckGo search, Wikipedia encyclopedia lookup, and Open-Meteo weather
without requiring any paid API keys.
"""

import logging
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("JARVIS.Skills.WebSkills")


class DuckDuckGoSearchSkill:
    """Free web search using DuckDuckGo Instant Answer / HTML API."""

    def __init__(self, timeout: float = 6.0):
        self.timeout = timeout

    def search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return {"success": False, "error": "Query cannot be empty.", "results": []}

        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JARVIS/2.0"}

            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=headers)

            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": f"DuckDuckGo returned HTTP {resp.status_code}",
                    "results": []
                }

            data = resp.json()
            abstract = data.get("AbstractText", "").strip()
            heading = data.get("Heading", "").strip()
            source_url = data.get("AbstractURL", "").strip()
            related = []

            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and "Text" in topic:
                    related.append({
                        "title": topic.get("Text", "")[:60],
                        "url": topic.get("FirstURL", ""),
                        "content": topic.get("Text", "")
                    })

            # If abstract is present, include it as primary result
            results = []
            if abstract:
                results.append({
                    "title": heading or query,
                    "url": source_url,
                    "content": abstract
                })
            results.extend(related)

            # Fallback for general search queries with empty instant answer
            if not results:
                summary = f"DuckDuckGo search completed for '{query}'. Topic recognized: {heading or query}."
                results.append({
                    "title": heading or query,
                    "url": f"https://duckduckgo.com/?q={encoded_query}",
                    "content": summary
                })

            return {
                "success": True,
                "provider": "duckduckgo",
                "query": query,
                "heading": heading or query,
                "summary": results[0]["content"] if results else "",
                "results": results[:max_results]
            }
        except Exception as e:
            logger.warning("[DuckDuckGo] Search error for '%s': %s", query, e)
            return {
                "success": False,
                "provider": "duckduckgo",
                "error": f"DuckDuckGo search unavailable: {str(e)}",
                "results": []
            }


class WikipediaSummarySkill:
    """Free encyclopedia concept lookup via Wikipedia REST API."""

    def __init__(self, timeout: float = 6.0):
        self.timeout = timeout

    def lookup(self, query: str) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return {"success": False, "error": "Query cannot be empty."}

        try:
            formatted_title = urllib.parse.quote(query.replace(" ", "_"))
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{formatted_title}"
            headers = {"User-Agent": "JARVIS-Assistant/2.0 (https://github.com/jarvis; jarvis@local)"}

            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)

            if resp.status_code == 404:
                return {
                    "success": False,
                    "query": query,
                    "error": f"No Wikipedia article found for '{query}'."
                }
            if resp.status_code != 200:
                return {
                    "success": False,
                    "query": query,
                    "error": f"Wikipedia API error (HTTP {resp.status_code})"
                }

            data = resp.json()
            title = data.get("title", query)
            extract = data.get("extract", "")
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

            return {
                "success": True,
                "provider": "wikipedia",
                "query": query,
                "title": title,
                "summary": extract,
                "url": page_url
            }
        except Exception as e:
            logger.warning("[Wikipedia] Lookup error for '%s': %s", query, e)
            return {
                "success": False,
                "provider": "wikipedia",
                "query": query,
                "error": f"Wikipedia lookup unavailable: {str(e)}"
            }


class WeatherLookupSkill:
    """Free live weather forecast lookup via Open-Meteo API (₹0 cost, no keys required)."""

    def __init__(self, timeout: float = 6.0):
        self.timeout = timeout

    def get_weather(self, location: str) -> Dict[str, Any]:
        location = (location or "").strip()
        if not location:
            return {"success": False, "error": "Location cannot be empty."}

        try:
            # 1. Geocoding via Open-Meteo
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location)}&count=1&language=en&format=json"
            headers = {"User-Agent": "JARVIS-Assistant/2.0"}

            with httpx.Client(timeout=self.timeout) as client:
                geo_resp = client.get(geo_url, headers=headers)

            if geo_resp.status_code != 200 or not geo_resp.json().get("results"):
                return {
                    "success": False,
                    "location": location,
                    "error": f"Could not resolve coordinates for '{location}'."
                }

            geo_data = geo_resp.json()["results"][0]
            lat = geo_data["latitude"]
            lon = geo_data["longitude"]
            city_name = geo_data.get("name", location)
            country = geo_data.get("country", "")

            # 2. Weather forecast query
            forecast_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"

            with httpx.Client(timeout=self.timeout) as client:
                weather_resp = client.get(forecast_url, headers=headers)

            if weather_resp.status_code != 200:
                return {
                    "success": False,
                    "location": location,
                    "error": f"Weather service returned HTTP {weather_resp.status_code}"
                }

            weather_data = weather_resp.json().get("current_weather", {})
            temp = weather_data.get("temperature", 0.0)
            windspeed = weather_data.get("windspeed", 0.0)
            wcode = weather_data.get("weathercode", 0)
            condition = self._map_weather_code(wcode)

            location_label = f"{city_name}, {country}" if country else city_name
            msg = f"Weather in {location_label}: {temp}°C, {condition}, wind speed {windspeed} km/h."

            return {
                "success": True,
                "provider": "open-meteo",
                "location": location_label,
                "city": city_name,
                "country": country,
                "latitude": lat,
                "longitude": lon,
                "temperature": temp,
                "condition": condition,
                "windspeed": windspeed,
                "unit": "celsius",
                "message": msg
            }
        except Exception as e:
            logger.warning("[Weather] Lookup error for '%s': %s", location, e)
            return {
                "success": False,
                "provider": "open-meteo",
                "location": location,
                "error": f"Weather lookup unavailable: {str(e)}"
            }

    def _map_weather_code(self, code: int) -> str:
        mapping = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snowfall",
            73: "Moderate snowfall",
            75: "Heavy snowfall",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            95: "Thunderstorm",
        }
        return mapping.get(code, "Clear")


# Global instances
duckduckgo_skill = DuckDuckGoSearchSkill()
wikipedia_skill = WikipediaSummarySkill()
weather_skill = WeatherLookupSkill()
