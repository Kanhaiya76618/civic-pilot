# Skill Note: Modern Frontend UI, Leaflet OSM & Reconnecting SSE Client

## Overview & Architecture
The frontend provides a fast, unified citizen, admin, and public accountability interface built on TypeScript, Tailwind CSS, Framer Motion animations, and Leaflet mapping.
Key principles:
1. **Zero-API-Key Geospatial Mapping**: Direct OpenStreetMap (OSM) tile rendering (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`) without Google Maps or Mapbox keys.
2. **Resilient Real-time Streaming**: An SSE client that automatically reconnects on network drops, tracks the last received event ID, and dispatches updates to local component state.
3. **Transparent Accountability Visuals**: Live status badges, Leaflet severity pin clusters, and Recharts performance breakdown.

---

## 1. Patterns
- **Leaflet in Single-Page Apps**: Leaflet requires access to the `window` object and CSS imported upfront. In React, initialize the map inside a `useEffect` hook attached to a dedicated container ref or use `@react-leaflet`.
- **Draggable Geolocation Pin**: Let citizens drag a pin or click on the map to set exact lat/lon coordinates, while auto-filling via HTML5 `navigator.geolocation`.
- **Reconnecting EventSource**: Wrap standard `EventSource` with an exponential backoff reconnect loop that appends `?after={lastSeq}` so dropped connections resume without losing event history.
- **Accessible State Badges**: Use high-contrast color tokens and ARIA attributes for municipal ticket lifecycle stages (`SUBMITTED` → `TRIAGED` → `ACKNOWLEDGED` → `ASSIGNED` → `IN_PROGRESS` → `RESOLVED`).

---

## 2. Common Pitfalls
1. **Leaflet Container Re-initialization**: Calling `L.map('map-id')` multiple times without calling `map.remove()` on component unmount causes "Map container is already initialized" runtime crashes.
2. **Missing Leaflet Icon Assets**: Default Leaflet marker images fail to resolve in modern bundlers (Vite/Webpack) unless explicit image URLs are supplied for `L.icon`.
3. **Memory Leaks from Unclosed EventSource**: Failing to invoke `eventSource.close()` inside the `useEffect` cleanup return leads to runaway background connections.

---

## 3. Minimal Working Code Skeleton

```tsx
import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// 1. Resilient SSE Hook with Reconnect
export function useEventStream(url: string, onEvent: (data: any) => void) {
  useEffect(() => {
    let es: EventSource | null = null;
    let timer: NodeJS.Timeout;

    function connect() {
      es = new EventSource(url);
      es.onmessage = (e) => {
        try {
          const parsed = JSON.parse(e.data);
          onEvent(parsed);
        } catch {
          onEvent(e.data);
        }
      };
      es.onerror = () => {
        es?.close();
        timer = setTimeout(connect, 3000); // 3s backoff
      };
    }

    connect();
    return () => {
      clearTimeout(timer);
      es?.close();
    };
  }, [url]);
}

// 2. Leaflet Map Component with OSM Tiles
export function CivicMap({ lat = 12.9716, lon = 77.5946, onLocationChange }: { lat?: number; lon?: number; onLocationChange?: (lat: number, lon: number) => void }) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);

  useEffect(() => {
    if (!mapContainer.current) return;

    const map = L.map(mapContainer.current).setView([lat, lon], 14);
    mapInstance.current = map;

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    const marker = L.marker([lat, lon], { draggable: !!onLocationChange }).addTo(map);
    markerRef.current = marker;

    if (onLocationChange) {
      marker.on("dragend", () => {
        const pos = marker.getLatLng();
        onLocationChange(pos.lat, pos.lng);
      });
      map.on("click", (e: L.LeafletMouseEvent) => {
        marker.setLatLng(e.latlng);
        onLocationChange(e.latlng.lat, e.latlng.lng);
      });
    }

    return () => {
      map.remove();
      mapInstance.current = null;
    };
  }, []);

  return <div ref={mapContainer} style={{ width: "100%", height: "350px", borderRadius: "12px" }} />;
}
```

---

## 4. Verified Source Links
- Leaflet Quick Start & API: https://leafletjs.com/examples/quick-start/
- MDN Using Server-Sent Events: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
- OpenStreetMap Tile Usage Policy: https://operations.osmfoundation.org/policies/tiles/
