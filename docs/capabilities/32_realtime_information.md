# Capability 32: Real-Time Information Reference Specification

**Capability ID:** `32_realtime_information`  
**Domain:** `info`  
**Target Provider:** `provider.info.realtime_feeds`  
**Contract Operations:**
- `info.get_weather`: Retrieves live weather, forecast, observation timestamp, and conditions.
- `info.get_news`: Retrieves recent headlines, publication timestamps, retrieval timestamps, source identity, and deduplicated articles.
- `info.verify_freshness`: Audits explicit data freshness thresholds against explicit TTL policies.
**Safety Classification:** `READ_ONLY`  
**Verification Strategy:** `TIMESTAMP_FRESHNESS_CHECK`  
**Status:** `VERIFIED END-TO-END`

---

## 1. Architectural Role & Boundary

Capability 32 provides time-volatile real-time feeds where correctness depends on the current/fresh state.
It is strictly differentiated from **Capability 31 (Web Research)**:

| Dimension | Capability 31: Web Research | Capability 32: Real-Time Information |
| :--- | :--- | :--- |
| **Primary Focus** | General web research, historical documents, broad source discovery | Volatile live feeds, current weather, breaking/category news |
| **Target Provider** | `provider.web.search_fetch` | `provider.info.realtime_feeds` |
| **Freshness Window** | Hours to days/weeks | 5 to 45 minutes |
| **Key Operations** | `search.web`, `web.fetch`, `search.synthesize_citations` | `info.get_weather`, `info.get_news`, `info.verify_freshness` |
| **Temporal Semantics** | Retrospective / Encyclopedic | "Right now", "Today", "Tonight", "Tomorrow", "Latest" |

---

## 2. Capability Pipeline

```
User Request ("What's the weather right now?" / "Latest tech news")
    ↓
Perception / Understanding Engine (Intent, Temporal & Entity Parsing)
    ↓
Context & World Model (Last queried location, last news topic, timezone)
    ↓
Cognitive Core (Single Router, System 1 Fast-Path / System 2 DAG)
    ↓
Capability Intelligence (select_provider: provider.info.realtime_feeds)
    ↓
RealTimeInfoProvider
    ├─ Cache Lookup (TTL: 15m weather, 15m breaking news, 45m general news)
    ├─ Live Weather Engine (Open-Meteo REST API → wttr.in fallback)
    └─ Live News Engine (Google News RSS → DuckDuckGo News)
    ↓
Untrusted Data Quarantine (<UNTRUSTED_EXTERNAL_DATA>)
    ↓
Observation & Empirical Verification Kernel (_verify_realtime_info_state)
    ↓
World Model State Feedback (last_location, last_news_topic, last_weather_query)
    ↓
Response
```

---

## 3. Operations Specification

### 3.1 `info.get_weather`
- **Parameters:**
  - `location`: Optional string (city/region). Defaults to World Model `last_location` or user profile.
  - `time_target`: Optional string (`"now"`, `"today"`, `"tomorrow"`, `"tonight"`).
  - `force_refresh`: Optional boolean. Bypasses cache when `True`.
- **Output Schema:**
  - `location`: Resolved label (e.g. `"Delhi, India"`).
  - `temperature`: Numeric temperature in Celsius.
  - `apparent_temperature`: Feels-like temperature.
  - `condition`: Text description (e.g. `"Clear sky"`, `"Light rain"`).
  - `windspeed`: Wind speed in km/h.
  - `humidity`: Percentage or `"unavailable"`.
  - `precipitation`: mm of precipitation.
  - `forecast`: Array of daily forecasts (when requested).
  - `observation_time`: Source observation timestamp.
  - `retrieved_at`: Retrieval ISO-8601 timestamp.
  - `freshness`: `"LIVE"` | `"CACHED"` | `"STALE"`.
  - `is_stale`: Boolean indicator.
  - `source`: `"Open-Meteo"` | `"wttr.in"`.
  - `provider`: `"provider.info.realtime_feeds"`.

### 3.2 `info.get_news`
- **Parameters:**
  - `topic`: News category or keyword query (e.g. `"technology"`, `"business"`).
  - `time_filter`: `"latest"`, `"today"`, `"yesterday"`.
  - `count`: Maximum number of articles (default `5`).
  - `force_refresh`: Optional boolean.
- **Output Schema:**
  - `topic`: Query topic.
  - `articles`: Array of articles:
    - `headline`: Title string.
    - `source`: Authoritative agency name (e.g. `"Reuters"`, `"BBC"`).
    - `source_url`: Link to article.
    - `published_at`: Publication timestamp from source.
    - `retrieved_at`: Retrieval ISO-8601 timestamp.
    - `quarantined_content`: Text wrapped in `<UNTRUSTED_EXTERNAL_DATA>`.
  - `freshness`: `"LIVE"` | `"CACHED"` | `"STALE"`.

### 3.3 `info.verify_freshness`
- **Parameters:**
  - `retrieved_at`: ISO-8601 string or numeric unix timestamp.
  - `data_type`: `"weather"` | `"breaking_news"` | `"general_news"` | `"market"`.
  - `custom_ttl_seconds`: Optional custom TTL override.
- **Freshness Classification Rules:**
  - `age <= 120s`: `"LIVE"`
  - `age <= TTL`: `"FRESH"`
  - `age <= TTL * 1.5`: `"RECENT"`
  - `age > TTL * 1.5`: `"STALE"`

---

## 4. Operational Classification

| Operation | Implementation | Test Coverage | Classification |
| :--- | :--- | :---: | :--- |
| `info.get_weather` | Open-Meteo REST API + wttr.in fallback + cache | Live API & Cache | **VERIFIED END-TO-END** |
| `info.get_news` | Google News RSS + DuckDuckGo fallback + dedup | Live RSS & Cache | **VERIFIED END-TO-END** |
| `info.verify_freshness` | Multi-tier TTL policy evaluation | Deterministic time bounds | **VERIFIED END-TO-END** |
| Contextual Follow-up | World Model location & topic resolution | Context snapshot suite | **VERIFIED END-TO-END** |
| Multi-Intent Decomposition | DAG planning (`get_weather` + `get_news`) | Cognitive Kernel DAG plan | **VERIFIED END-TO-END** |
| Security Quarantine | Untrusted tag isolation + PolicyKernel shell block | Injection refusal suite | **VERIFIED END-TO-END** |
