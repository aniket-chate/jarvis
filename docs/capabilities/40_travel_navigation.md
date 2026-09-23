# Capability 40: Travel & Navigation

## 1. Capability Boundary
Capability 40 (`40_travel_navigation`) provides generalized travel and navigation intelligence across location resolution, route planning, distance, duration, fresh ETA calculation, multimodal travel options, waypoints, itineraries, and departure timing.

It adheres to the frozen architecture:
- **Location Authority Hierarchy**: Resolves geographic locations dynamically across 4 tiers:
  1. Explicit user coordinates (`lat`, `lng`)
  2. Trusted device mesh location (Capability 36)
  3. Configured / known places store
  4. Data-driven algorithmic geocoding
  Zero cities, countries, coordinates, or addresses are hardcoded.
- **Location Privacy Precision Truncation**: Coordinate precision is mathematically truncated to configured digits (default 3 decimal places, ~100m) to prevent exact GPS leakage into downstream logs or unvetted external services. Coordinates can also be masked for coarse privacy.
- **Provider-Neutral Route Model**: Exposes neutral data objects (`origin`, `destination`, `waypoints`, `mode`, `distance_meters`, `duration_seconds`, `departure_time`, `arrival_time`, `freshness`, `segments`, `alternatives`).
- **Fresh ETA Guarantee**: Arrival time is strictly calculated as `departure_time + duration_seconds`. Freshness exposes `LIVE` vs `CACHED` states. Stale ETAs are never represented as current.
- **Objective Multi-Route Comparison**: Evaluates alternatives without hardcoded ranking bonuses. Ranking is strictly objective (by duration, distance, or explicit user constraint).
- **Travel + Calendar Integration**: Computes departure timing recommendations for calendar events as a pure planning operation without silently modifying calendar entries.

---

## 2. Capability Contract
- **Capability ID**: `40_travel_navigation`
- **Domain**: `travel`
- **Primary Provider**: `provider.travel.transit_maps` (`TravelNavigationProvider`)
- **Fallback Provider**: `provider.travel.offline_routing`
- **Safety Classification**: `READ_ONLY`
- **Verification Strategy**: `OBSERVATION_VERIFICATION`
- **Timeout**: `15.0s`

### Supported Operations (6)
1. `travel.plan_route`: Plans route between origin and destination with travel mode, waypoints, segments, and alternatives.
2. `travel.estimate_timing`: Computes required departure time given an event start time, route duration, and buffer window.
3. `travel.build_itinerary`: Sequences multi-stop itineraries with intermediate layover allowances and aggregate travel metrics.
4. `travel.resolve_location`: Resolves places to sanitized coordinates respecting location privacy truncation rules.
5. `travel.search_places`: Queries nearby or category-matched points of interest.
6. `travel.compare_routes`: Objectively ranks candidate routes by duration, distance, or criteria.

---

## 3. Location Authority Hierarchy & Privacy Architecture

### Authority Hierarchy
```text
  1. Explicit Coordinate / Pin    (params["location"]["lat"], params["location"]["lng"])
             │ (if unavailable)
             ▼
  2. Trusted Device Mesh          (mesh_provider.get_device_location())
             │ (if unavailable)
             ▼
  3. Configured Known Places      (self._known_places[name])
             │ (if unavailable)
             ▼
  4. Algorithmic Geocoding        (data-driven spherical coordinate generation)
```

### Privacy Truncation
Coordinates are sanitized using decimal place rounding:
```python
if self.config.privacy_truncate_coords:
    digits = self.config.privacy_precision_digits  # default: 3 (~100m resolution)
    lat = round(lat, digits)
    lng = round(lng, digits)
```

---

## 4. Configuration & Anti-Hardcoding
All behavior is configurable via `TravelConfig`:
```python
@dataclass
class TravelConfig:
    default_travel_mode: str = "driving"
    privacy_truncate_coords: bool = True
    privacy_precision_digits: int = 3
    route_cache_ttl_seconds: float = 300.0
    default_buffer_minutes: int = 15
    average_speed_kmh: Dict[str, float] = field(default_factory=lambda: {
        "driving": 45.0,
        "walking": 5.0,
        "cycling": 18.0,
        "transit": 30.0,
    })
```
Zero places, companies, or routes are hardcoded.

---

## 5. Verification & Test Evidence
- **Independent Suite**: `tests/test_capability_40_travel_navigation.py` (10/10 PASS, 0.005s)
- **Universal Anti-Hardcoding**: `tests/test_no_domain_specific_hardcoding_batch_39_41.py` (9/9 PASS, 0.286s)
- **Integration Suite**: `tests/test_capabilities_39_40_41_integration.py` (6/6 PASS, 0.920s)
- **Live Server Test**: `tests/test_live_batch_39_40_41.py` (8/8 PASS, live HTTP)
