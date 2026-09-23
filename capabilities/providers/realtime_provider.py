"""Real-Time Information Capability Provider for JARVIS.

Implements Capability 32: Real-Time Information under the frozen architecture.
Supports:
- info.get_weather (live weather conditions, apparent temp, wind, humidity, forecast, observation time)
- info.get_news (recent headlines, publication timestamps, retrieval timestamps, source identity, dedup)
- info.verify_freshness (explicit TTL verification: LIVE, FRESH, RECENT, CACHED, STALE, UNAVAILABLE)

Decoupled from general web research (Capability 31).
Enforces prompt injection defense via <UNTRUSTED_EXTERNAL_DATA> quarantine tags.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional
import urllib.parse
import xml.etree.ElementTree as ET

import httpx

from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult

logger = logging.getLogger("JARVIS.Capabilities.Providers.RealTimeInfo")

# Explicit TTL Policies (seconds)
TTL_POLICIES = {
    "weather": 900.0,         # 15 minutes
    "weather_forecast": 3600.0, # 60 minutes
    "breaking_news": 900.0,    # 15 minutes
    "general_news": 2700.0,   # 45 minutes
    "market": 300.0,          # 5 minutes
}


class RealTimeInfoProvider(BaseCapabilityProvider):
    """Primary provider for Capability 32 (Real-Time Information)."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._success_count: int = 0
        self._failure_count: int = 0

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_id="provider.info.realtime_feeds",
            name="Real-Time Feeds Provider",
            version="2.0.0",
            description="Fetches live weather and news feeds with strict freshness timestamping and quarantine.",
            supported_capabilities=["info.get_weather", "info.get_news", "info.verify_freshness"],
            device_target="cloud_or_local",
            safety_level="read_only",
            author="system",
        )

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        capability: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Standard capability dispatch for real-time information."""
        t0 = time.perf_counter()
        params = parameters or {}

        try:
            if capability == "info.get_weather":
                return self._handle_get_weather(params, context, t0)
            elif capability == "info.get_news":
                return self._handle_get_news(params, context, t0)
            elif capability == "info.verify_freshness":
                return self._handle_verify_freshness(params, t0)
            else:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                return ActionResult(
                    status="FAILED",
                    output={"error": f"Unsupported operation '{capability}' on provider '{self.provider_id}'"},
                    message=f"Unsupported capability: {capability}",
                    execution_time_ms=elapsed_ms,
                )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error("[RealTimeInfoProvider] Execution error on %s: %s", capability, exc, exc_info=True)
            return ActionResult(
                status="FAILED",
                output={"error": str(exc)},
                message=f"Operation failed: {exc}",
                execution_time_ms=elapsed_ms,
            )

    # -------------------------------------------------------------------------
    # 1. Weather Operation (info.get_weather)
    # -------------------------------------------------------------------------
    def _handle_get_weather(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        t0: float,
    ) -> ActionResult:
        location = str(params.get("location") or params.get("city") or "").strip()
        time_target = str(params.get("time_target") or params.get("time") or "now").lower()
        force_refresh = bool(params.get("force_refresh", False))

        # Fallback to context or default Delhi if location not provided
        if not location:
            if context and context.get("last_location"):
                location = str(context["last_location"])
            elif context and context.get("user_profile", {}).get("city"):
                location = str(context["user_profile"]["city"])
            else:
                location = "Delhi"

        cache_key = f"weather:{location.lower()}:{time_target}"
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        # Check Cache
        if not force_refresh:
            cached = self._get_from_cache(cache_key)
            if cached:
                cached_data = dict(cached["data"])
                cached_data["freshness"] = "CACHED"
                cached_data["is_stale"] = cached["is_stale"]
                elapsed_ms = (time.perf_counter() - t0) * 1000
                return ActionResult(
                    status="SUCCESS",
                    output=cached_data,
                    message=f"Retrieved cached weather for {location} ({cached_data['temperature']}°C, {cached_data['condition']})",
                    evidence=f"Cache hit: retrieved_at={cached_data['retrieved_at']}, is_stale={cached['is_stale']}",
                    execution_time_ms=elapsed_ms,
                    metadata={"source": cached_data.get("source"), "provider": self.provider_id, "cached": True},
                )

        # Live Fetch via Open-Meteo (Primary) with fallback to wttr.in
        weather_res = self._fetch_open_meteo_weather(location, time_target, now_iso)
        if not weather_res.get("success"):
            # Fallback to secondary weather provider (wttr.in)
            logger.info("[RealTimeInfoProvider] Open-Meteo failed, falling back to wttr.in for '%s'", location)
            weather_res = self._fetch_wttr_weather(location, time_target, now_iso)

        if not weather_res.get("success"):
            # If all live providers fail, check if stale cache exists to return truthfully as STALE
            cached = self._get_from_cache(cache_key, allow_stale=True)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if cached:
                stale_data = dict(cached["data"])
                stale_data["freshness"] = "STALE"
                stale_data["is_stale"] = True
                return ActionResult(
                    status="PARTIAL",
                    output=stale_data,
                    message=f"Live weather unavailable. Returning stale cache for {location}.",
                    evidence=f"Stale fallback: original retrieved_at={stale_data.get('retrieved_at')}",
                    execution_time_ms=elapsed_ms,
                    metadata={"stale": True, "provider": self.provider_id},
                )
            return ActionResult(
                status="FAILED",
                output={"error": weather_res.get("error", "Weather service unavailable"), "location": location},
                message=f"Could not retrieve weather for '{location}': {weather_res.get('error')}",
                execution_time_ms=elapsed_ms,
            )

        # Store in cache
        ttl = TTL_POLICIES["weather"] if time_target in ["now", "today"] else TTL_POLICIES["weather_forecast"]
        self._put_in_cache(cache_key, weather_res, ttl)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        return ActionResult(
            status="SUCCESS",
            output=weather_res,
            message=weather_res.get("message", f"Weather in {location}: {weather_res.get('temperature')}°C"),
            evidence=f"Live weather observed: {weather_res.get('location')} -> {weather_res.get('temperature')}°C, {weather_res.get('condition')} at {weather_res.get('observation_time')}",
            execution_time_ms=elapsed_ms,
            metadata={"provider": self.provider_id, "source": weather_res.get("source"), "cached": False},
        )

    def _fetch_open_meteo_weather(self, location: str, time_target: str, now_iso: str) -> Dict[str, Any]:
        """Fetches live weather from Open-Meteo API with full field set."""
        try:
            headers = {"User-Agent": "JARVIS-RealTime-Info/2.0 (https://github.com/jarvis)"}
            # 1. Geocode
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location)}&count=1&language=en&format=json"
            with httpx.Client(timeout=self.timeout) as client:
                geo_resp = client.get(geo_url, headers=headers)
                if geo_resp.status_code != 200 or not geo_resp.json().get("results"):
                    return {"success": False, "error": f"Coordinates not found for location '{location}'"}
                geo_data = geo_resp.json()["results"][0]
                lat = geo_data["latitude"]
                lon = geo_data["longitude"]
                city_name = geo_data.get("name", location)
                country = geo_data.get("country", "")

                # 2. Weather query with hourly and current fields
                forecast_url = (
                    f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                    "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
                    "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
                    "&timezone=auto"
                )
                weather_resp = client.get(forecast_url, headers=headers)
                if weather_resp.status_code != 200:
                    return {"success": False, "error": f"Open-Meteo returned HTTP {weather_resp.status_code}"}

                wdata = weather_resp.json()
                current = wdata.get("current", {})
                daily = wdata.get("daily", {})

                temp = current.get("temperature_2m", 0.0)
                apparent_temp = current.get("apparent_temperature", temp)
                humidity = current.get("relative_humidity_2m", "unavailable")
                precipitation = current.get("precipitation", 0.0)
                windspeed = current.get("wind_speed_10m", 0.0)
                wcode = current.get("weather_code", 0)
                condition = self._map_weather_code(wcode)
                obs_time = current.get("time", now_iso)

                # Forecast summary
                forecast_items = []
                if daily and "time" in daily:
                    for i in range(min(len(daily["time"]), 3)):
                        d_time = daily["time"][i]
                        d_max = daily.get("temperature_2m_max", [temp])[i]
                        d_min = daily.get("temperature_2m_min", [temp])[i]
                        d_code = daily.get("weather_code", [0])[i]
                        forecast_items.append({
                            "date": d_time,
                            "max_temp": d_max,
                            "min_temp": d_min,
                            "condition": self._map_weather_code(d_code),
                            "precipitation": daily.get("precipitation_sum", [0.0])[i],
                        })

                loc_label = f"{city_name}, {country}" if country else city_name
                msg = f"Weather in {loc_label}: {temp}°C (feels like {apparent_temp}°C), {condition}. Wind: {windspeed} km/h, Humidity: {humidity}%."

                return {
                    "success": True,
                    "location": loc_label,
                    "city": city_name,
                    "country": country,
                    "latitude": lat,
                    "longitude": lon,
                    "time_target": time_target,
                    "temperature": temp,
                    "apparent_temperature": apparent_temp,
                    "condition": condition,
                    "humidity": humidity,
                    "windspeed": windspeed,
                    "precipitation": precipitation,
                    "unit": "celsius",
                    "forecast": forecast_items,
                    "observation_time": obs_time,
                    "retrieved_at": now_iso,
                    "freshness": "LIVE",
                    "is_stale": False,
                    "source": "Open-Meteo",
                    "provider": "provider.info.realtime_feeds",
                    "message": msg,
                    "raw_quarantined": f"<UNTRUSTED_EXTERNAL_DATA source='open-meteo'>{msg}</UNTRUSTED_EXTERNAL_DATA>",
                }
        except Exception as exc:
            logger.warning("[RealTimeInfoProvider] Open-Meteo lookup error: %s", exc)
            return {"success": False, "error": str(exc)}

    def _fetch_wttr_weather(self, location: str, time_target: str, now_iso: str) -> Dict[str, Any]:
        """Fallback live weather fetcher using wttr.in JSON interface."""
        try:
            encoded_loc = urllib.parse.quote(location)
            url = f"https://wttr.in/{encoded_loc}?format=j1"
            headers = {"User-Agent": "curl/7.68.0"}

            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code != 200:
                    return {"success": False, "error": f"wttr.in returned HTTP {resp.status_code}"}
                data = resp.json()

                current = data.get("current_condition", [{}])[0]
                temp = float(current.get("temp_C", 0))
                apparent_temp = float(current.get("FeelsLikeC", temp))
                humidity = float(current.get("humidity", 0))
                windspeed = float(current.get("windspeedKmph", 0))
                condition = current.get("weatherDesc", [{}])[0].get("value", "Clear")
                precip = float(current.get("precipMM", 0.0))

                area = data.get("nearest_area", [{}])[0]
                city_name = area.get("areaName", [{}])[0].get("value", location)
                country = area.get("country", [{}])[0].get("value", "")
                loc_label = f"{city_name}, {country}" if country else city_name
                msg = f"Weather in {loc_label}: {temp}°C, {condition}. Wind: {windspeed} km/h, Humidity: {humidity}%."

                return {
                    "success": True,
                    "location": loc_label,
                    "city": city_name,
                    "country": country,
                    "time_target": time_target,
                    "temperature": temp,
                    "apparent_temperature": apparent_temp,
                    "condition": condition,
                    "humidity": humidity,
                    "windspeed": windspeed,
                    "precipitation": precip,
                    "unit": "celsius",
                    "forecast": [],
                    "observation_time": now_iso,
                    "retrieved_at": now_iso,
                    "freshness": "LIVE",
                    "is_stale": False,
                    "source": "wttr.in",
                    "provider": "provider.info.realtime_feeds",
                    "message": msg,
                    "raw_quarantined": f"<UNTRUSTED_EXTERNAL_DATA source='wttr.in'>{msg}</UNTRUSTED_EXTERNAL_DATA>",
                }
        except Exception as exc:
            logger.warning("[RealTimeInfoProvider] wttr.in fallback error: %s", exc)
            return {"success": False, "error": str(exc)}

    # -------------------------------------------------------------------------
    # 2. News Operation (info.get_news)
    # -------------------------------------------------------------------------
    def _handle_get_news(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]],
        t0: float,
    ) -> ActionResult:
        topic = str(params.get("topic") or params.get("category") or "general").strip()
        time_filter = str(params.get("time_filter") or "latest").lower()
        count = int(params.get("count") or 5)
        force_refresh = bool(params.get("force_refresh", False))

        # Check Context if topic missing or generic follow-up
        if topic in ["", "news", "the news", "it", "that topic"]:
            if context and context.get("last_news_topic"):
                topic = str(context["last_news_topic"])
            else:
                topic = "general"

        cache_key = f"news:{topic.lower()}:{time_filter}"
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        # Check Cache
        if not force_refresh:
            cached = self._get_from_cache(cache_key)
            if cached:
                cached_data = dict(cached["data"])
                cached_data["freshness"] = "CACHED"
                cached_data["is_stale"] = cached["is_stale"]
                elapsed_ms = (time.perf_counter() - t0) * 1000
                return ActionResult(
                    status="SUCCESS",
                    output=cached_data,
                    message=f"Retrieved {len(cached_data.get('articles', []))} cached news articles for '{topic}'",
                    evidence=f"Cache hit: retrieved_at={cached_data.get('retrieved_at')}, count={len(cached_data.get('articles', []))}",
                    execution_time_ms=elapsed_ms,
                    metadata={"provider": self.provider_id, "cached": True},
                )

        # Live Fetch via Google News RSS & DuckDuckGo News
        news_res = self._fetch_live_news(topic, time_filter, count, now_iso)

        if not news_res.get("success"):
            # Fallback to stale cache if available
            cached = self._get_from_cache(cache_key, allow_stale=True)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if cached:
                stale_data = dict(cached["data"])
                stale_data["freshness"] = "STALE"
                stale_data["is_stale"] = True
                return ActionResult(
                    status="PARTIAL",
                    output=stale_data,
                    message=f"Live news unavailable. Returning stale cache for '{topic}'.",
                    evidence=f"Stale fallback: original retrieved_at={stale_data.get('retrieved_at')}",
                    execution_time_ms=elapsed_ms,
                    metadata={"stale": True, "provider": self.provider_id},
                )
            return ActionResult(
                status="FAILED",
                output={"error": news_res.get("error", "News service unavailable"), "topic": topic, "articles": []},
                message=f"Could not retrieve news for '{topic}': {news_res.get('error')}",
                execution_time_ms=elapsed_ms,
            )

        # Store in cache
        ttl = TTL_POLICIES["breaking_news"] if time_filter in ["breaking", "now", "latest"] else TTL_POLICIES["general_news"]
        self._put_in_cache(cache_key, news_res, ttl)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        article_count = len(news_res.get("articles", []))
        return ActionResult(
            status="SUCCESS",
            output=news_res,
            message=f"Retrieved {article_count} live news articles for '{topic}' ({time_filter})",
            evidence=f"News observed: {article_count} articles from sources: {[a.get('source') for a in news_res.get('articles', [])[:3]]}",
            execution_time_ms=elapsed_ms,
            metadata={"provider": self.provider_id, "count": article_count, "cached": False},
        )

    def _fetch_live_news(self, topic: str, time_filter: str, count: int, now_iso: str) -> Dict[str, Any]:
        """Fetches live news from Google News RSS feed, cleans, and deduplicates."""
        try:
            query = f"{topic} news" if "news" not in topic.lower() else topic
            if time_filter == "today":
                query += " today"
            encoded_query = urllib.parse.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JARVIS/2.0"}

            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(rss_url, headers=headers)
                if resp.status_code != 200:
                    return {"success": False, "error": f"RSS feed returned HTTP {resp.status_code}"}

                root = ET.fromstring(resp.content)
                channel = root.find("channel")
                if channel is None:
                    return {"success": False, "error": "Invalid RSS structure received"}

                raw_articles: List[Dict[str, Any]] = []
                seen_headlines = set()

                for item in channel.findall("item"):
                    title = (item.findtext("title") or "Untitled").strip()
                    link = (item.findtext("link") or "").strip()
                    pub_date = (item.findtext("pubDate") or now_iso).strip()
                    source_el = item.find("source")
                    source_name = source_el.text.strip() if source_el is not None and source_el.text else "News Agency"

                    # Normalize headline and parse source from title if embedded
                    headline = title
                    if " - " in title:
                        parts = title.rsplit(" - ", 1)
                        headline = parts[0].strip()
                        if source_name == "News Agency" and len(parts) > 1:
                            source_name = parts[1].strip()

                    # Deduplication check
                    norm_key = re.sub(r"[^a-zA-Z0-9]", "", headline.lower())[:40]
                    if norm_key in seen_headlines:
                        continue
                    seen_headlines.add(norm_key)

                    # Wrap in untrusted data quarantine tag
                    quarantined_snippet = f"<UNTRUSTED_EXTERNAL_DATA source='{source_name}'>{headline}</UNTRUSTED_EXTERNAL_DATA>"

                    raw_articles.append({
                        "headline": headline,
                        "summary": headline,
                        "source": source_name,
                        "source_url": link,
                        "published_at": pub_date,
                        "retrieved_at": now_iso,
                        "quarantined_content": quarantined_snippet,
                    })

                    if len(raw_articles) >= count:
                        break

                if not raw_articles:
                    return {
                        "success": True,
                        "topic": topic,
                        "time_filter": time_filter,
                        "count": 0,
                        "articles": [],
                        "retrieved_at": now_iso,
                        "freshness": "LIVE",
                        "is_stale": False,
                        "source": "Google News RSS",
                        "provider": "provider.info.realtime_feeds",
                    }

                return {
                    "success": True,
                    "topic": topic,
                    "time_filter": time_filter,
                    "count": len(raw_articles),
                    "articles": raw_articles,
                    "retrieved_at": now_iso,
                    "freshness": "LIVE",
                    "is_stale": False,
                    "source": "Google News RSS",
                    "provider": "provider.info.realtime_feeds",
                }
        except Exception as exc:
            logger.warning("[RealTimeInfoProvider] Live news fetch error: %s", exc)
            return {"success": False, "error": str(exc)}

    # -------------------------------------------------------------------------
    # 3. Freshness Verification (info.verify_freshness)
    # -------------------------------------------------------------------------
    def _handle_verify_freshness(
        self,
        params: Dict[str, Any],
        t0: float,
    ) -> ActionResult:
        retrieved_at = params.get("retrieved_at")
        data_type = str(params.get("data_type") or "weather").lower()
        custom_ttl = params.get("custom_ttl_seconds")

        ttl = float(custom_ttl) if custom_ttl is not None else TTL_POLICIES.get(data_type, 900.0)

        if not retrieved_at:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return ActionResult(
                status="FAILED",
                output={"error": "Missing 'retrieved_at' timestamp parameter", "status": "UNKNOWN"},
                message="Cannot verify freshness without a timestamp",
                execution_time_ms=elapsed_ms,
            )

        # Parse retrieved_at
        try:
            if isinstance(retrieved_at, (int, float)):
                dt_retrieved = datetime.fromtimestamp(retrieved_at, tz=timezone.utc)
            elif isinstance(retrieved_at, str):
                # ISO-8601 parsing
                if retrieved_at.endswith("Z"):
                    retrieved_at = retrieved_at[:-1] + "+00:00"
                dt_retrieved = datetime.fromisoformat(retrieved_at)
                if dt_retrieved.tzinfo is None:
                    dt_retrieved = dt_retrieved.replace(tzinfo=timezone.utc)
            else:
                raise ValueError("Invalid timestamp format")
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return ActionResult(
                status="FAILED",
                output={"error": f"Malformed timestamp: {e}", "status": "UNKNOWN"},
                message="Malformed timestamp provided for freshness verification",
                execution_time_ms=elapsed_ms,
            )

        now_dt = datetime.now(timezone.utc)
        age_seconds = (now_dt - dt_retrieved).total_seconds()

        # Freshness classification
        if age_seconds < 0:
            # Future timestamp or slight clock skew
            freshness_label = "LIVE"
            is_stale = False
        elif age_seconds <= 120.0:
            freshness_label = "LIVE"
            is_stale = False
        elif age_seconds <= ttl:
            freshness_label = "FRESH"
            is_stale = False
        elif age_seconds <= (ttl * 1.5):
            freshness_label = "RECENT"
            is_stale = False
        else:
            freshness_label = "STALE"
            is_stale = True

        out = {
            "status": freshness_label,
            "data_type": data_type,
            "age_seconds": round(age_seconds, 2),
            "ttl_seconds": ttl,
            "is_fresh": not is_stale,
            "is_stale": is_stale,
            "verified_at": now_dt.isoformat(),
        }

        elapsed_ms = (time.perf_counter() - t0) * 1000
        return ActionResult(
            status="SUCCESS",
            output=out,
            message=f"Freshness evaluated as '{freshness_label}' (age: {out['age_seconds']}s, TTL: {ttl}s)",
            evidence=f"Timestamp verification: age={out['age_seconds']}s, status={freshness_label}",
            execution_time_ms=elapsed_ms,
            metadata={"freshness": freshness_label, "is_stale": is_stale},
        )

    # -------------------------------------------------------------------------
    # 4. Cache Helper Methods
    # -------------------------------------------------------------------------
    def _get_from_cache(self, key: str, allow_stale: bool = False) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            now_ts = time.time()
            is_stale = now_ts > entry["expires_at"]
            if is_stale and not allow_stale:
                return None
            return {
                "data": entry["data"],
                "retrieved_at": entry["retrieved_at"],
                "is_stale": is_stale,
            }

    def _put_in_cache(self, key: str, data: Dict[str, Any], ttl_seconds: float):
        with self._lock:
            now_ts = time.time()
            self._cache[key] = {
                "data": data,
                "retrieved_at": data.get("retrieved_at", datetime.now(timezone.utc).isoformat()),
                "expires_at": now_ts + ttl_seconds,
                "ttl_seconds": ttl_seconds,
            }

    def clear_cache(self):
        """Clears cache store for testing or forced cache invalidation."""
        with self._lock:
            self._cache.clear()

    def invalidate_key(self, key: str):
        """Invalidates a specific cache entry."""
        with self._lock:
            self._cache.pop(key, None)

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


# Global provider instance
realtime_info_provider = RealTimeInfoProvider()
