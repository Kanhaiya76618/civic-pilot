# Skill Note: Geospatial GIS Routing, 50m Spatial Dedup & Nominatim Etiquette

## Overview & Architecture
Accurate municipal grievance routing depends on three core geospatial operations:
1. **Ward Resolution**: Shapely Point-in-Polygon (PIP) spatial test mapping `(lat, lon)` coordinates to administrative ward boundaries (BBMP Bangalore, PMC Pune, etc.).
2. **50m Spatial Deduplication**: Clustered complaints within 50 meters of an active hazard are merged into an upvote counter ("4 citizens reported this") to prevent duplicate contractor billing.
3. **Critical POI Vulnerability Multiplier**: Multiplies severity by $1.2\times$ to $1.6\times$ if within 150m of schools, hospitals, or transit stations.
4. **Nominatim Reverse Geocoding**: Resolves human-readable street addresses while strictly obeying OpenStreetMap's usage policy.

---

## 1. Patterns
- **Point-in-Polygon Indexing**: Bounding-box pre-filtering (`geom.bounds`) followed by `polygon.contains(Point(lon, lat))` gives sub-millisecond ward resolution.
- **Honest Fallback State**: If GPS coordinates fall outside mapped boundaries, state honestly: `"Unmapped area — nearest mapped jurisdiction: {nearest_city}"`. Never fabricate fake ward IDs like `GPS-1234`.
- **Haversine Distance**:
  $$d = 2r \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$
  Flag any ticket within 50m with identical category as a duplicate candidate.
- **Nominatim Caching & 1 req/s Throttling**: OSM Nominatim requires an identifiable `User-Agent: CivicPilot-Hackathon/1.0 (contact@example.com)`. Cache responses rounded to 4 decimal places (~11m resolution) to eliminate duplicate external requests.

---

## 2. Common Pitfalls
1. **Latitude / Longitude Inversion**: In GeoJSON and Shapely, coordinates are stored as `(longitude, latitude)` / `(x, y)`. Passing `Point(latitude, longitude)` causes lookups to land in the Indian Ocean or Antarctica.
2. **Missing User-Agent on Nominatim**: Nominatim rejects requests with generic Python/httpx User-Agents with HTTP 403 Forbidden.
3. **High-Precision Cache Keys**: Caching by exact 8-decimal float GPS misses cache hits from identical locations with minor GPS jitter. Round coordinates to 4 decimal places.

---

## 3. Minimal Working Code Skeleton

```python
import math
import time
from typing import Optional, List, Dict
from shapely.geometry import Point, shape
import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
GEO_CACHE: Dict[str, str] = {}
LAST_REQ_TIME = 0.0

def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0 # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def find_spatial_duplicate(lat: float, lon: float, category: str, active_tickets: List[dict], threshold_m: float = 50.0) -> Optional[dict]:
    """Finds existing ticket within 50 meters in the same category."""
    for ticket in active_tickets:
        if ticket.get("category") == category:
            dist = haversine_meters(lat, lon, ticket["lat"], ticket["lon"])
            if dist <= threshold_m:
                return {**ticket, "distance_m": round(dist, 1)}
    return None

def resolve_ward(lat: float, lon: float, wards: List[dict]) -> dict:
    """Shapely Point-in-Polygon check. Point takes (x, y) = (lon, lat)."""
    pt = Point(lon, lat)
    for ward in wards:
        minx, miny, maxx, maxy = ward["bounds"]
        if minx <= lon <= maxx and miny <= lat <= maxy:
            if ward["geometry"].contains(pt):
                return {"mapped": True, "ward_name": ward["ward_name"], "ward_no": ward["ward_no"]}
                
    return {"mapped": False, "status": "Unmapped area — outside municipal boundaries"}

async def reverse_geocode_nominatim(lat: float, lon: float) -> str:
    """Honest cached Nominatim reverse geocode obeying 1 req/s rate limit."""
    global LAST_REQ_TIME
    cache_key = f"{lat:.4f},{lon:.4f}"
    if cache_key in GEO_CACHE:
        return GEO_CACHE[cache_key]
        
    now = time.time()
    elapsed = now - LAST_REQ_TIME
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
        
    headers = {"User-Agent": "CivicPilot-GovernancePlatform/1.0 (hackathon-demo@civicpilot.local)"}
    params = {"format": "jsonv2", "lat": lat, "lon": lon}
    async with httpx.AsyncClient(timeout=4) as client:
        r = await client.get(NOMINATIM_URL, params=params, headers=headers)
        LAST_REQ_TIME = time.time()
        if r.status_code == 200:
            addr = r.json().get("display_name", f"{lat:.4f}, {lon:.4f}")
            GEO_CACHE[cache_key] = addr
            return addr
    return f"{lat:.4f}, {lon:.4f}"
```

---

## 4. Verified Source Links
- Shapely Geometric Objects Documentation: https://shapely.readthedocs.io/en/stable/geometry.html
- OpenStreetMap Nominatim Usage Policy: https://operations.osmfoundation.org/policies/nominatim/
- Haversine Formula Standard: https://en.wikipedia.org/wiki/Haversine_formula
