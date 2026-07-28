import React, { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { BANGALORE_BOUNDS, BANGALORE_CENTER } from "../config.js";

// Leaflet's default marker icons reference image files that don't resolve correctly
// under bundlers like Vite - we use plain colored divIcons instead, so no icon
// asset fixup is needed here.

const PER_VEHICLE_M = 6;      // approx length a standing vehicle + gap occupies on the road
const MAX_QUEUE_M = 200;      // cap so a huge vehicle count doesn't draw an absurdly long queue

function coloredDivIcon(color, size = 18) {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:50%;
      background:${color};border:3px solid white;
      box-shadow:0 0 6px rgba(0,0,0,0.5);
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function junctionDivIcon(color) {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:14px;height:14px;border-radius:50%;
      background:${color};border:2px solid white;
    "></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

function haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function nearestGeometryIndex(geometry, lat, lon) {
  let best = 0;
  let bestDist = Infinity;
  geometry.forEach((p, i) => {
    const d = haversineM(p[0], p[1], lat, lon);
    if (d < bestDist) {
      bestDist = d;
      best = i;
    }
  });
  return best;
}

// Walks backward from the junction (towards the source) along the route geometry,
// collecting points + cumulative distance until `queueLenM` of road length is covered.
// coords[0] is the junction itself; later points move upstream. cumDist[i] is the
// distance from the junction to coords[i]. Storing real distances (not just array
// indices) lets us later shrink the queue smoothly by interpolating an exact point
// along the path, instead of only being able to jump between sparse vertices.
function computeQueueCoords(geometry, junctionLat, junctionLon, queueLenM) {
  const idx = nearestGeometryIndex(geometry, junctionLat, junctionLon);
  const coords = [geometry[idx]];
  const cumDist = [0];
  let accumulated = 0;
  for (let i = idx; i > 0; i--) {
    const d = haversineM(geometry[i][0], geometry[i][1], geometry[i - 1][0], geometry[i - 1][1]);
    accumulated += d;
    coords.push(geometry[i - 1]);
    cumDist.push(accumulated);
    if (accumulated >= queueLenM) break;
  }
  return { coords, cumDist, totalLen: accumulated };
}

const MapView = forwardRef(function MapView({ onMapDoubleClick }, ref) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const routeLineRef = useRef(null);
  const sourceMarkerRef = useRef(null);
  const destMarkerRef = useRef(null);
  const ambulanceMarkerRef = useRef(null);
  const junctionMarkersRef = useRef([]);
  const geometryRef = useRef([]);
  const queueLayersRef = useRef({}); // { [junctionIndex]: { layer, coords, cumDist, totalLen } }

  // Keep a ref to the latest click handler so the dblclick listener (registered once,
  // below) always calls the current version instead of the stale one it closed over
  // when the map first mounted.
  const onMapDoubleClickRef = useRef(onMapDoubleClick);
  useEffect(() => {
    onMapDoubleClickRef.current = onMapDoubleClick;
  }, [onMapDoubleClick]);

  useEffect(() => {
    const map = L.map(containerRef.current, {
      center: BANGALORE_CENTER,
      zoom: 12,
      minZoom: 10,
      maxBounds: BANGALORE_BOUNDS,
      maxBoundsViscosity: 1.0,
      doubleClickZoom: false, // we use double-click for source/destination selection instead
    });

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(map);

    map.on("dblclick", (e) => {
      onMapDoubleClickRef.current && onMapDoubleClickRef.current({ lat: e.latlng.lat, lon: e.latlng.lng });
    });

    mapRef.current = map;
    return () => map.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useImperativeHandle(ref, () => ({
    setSourceMarker(lat, lon) {
      if (sourceMarkerRef.current) mapRef.current.removeLayer(sourceMarkerRef.current);
      sourceMarkerRef.current = L.marker([lat, lon], { icon: coloredDivIcon("#22c55e") }).addTo(mapRef.current);
    },
    setDestMarker(lat, lon) {
      if (destMarkerRef.current) mapRef.current.removeLayer(destMarkerRef.current);
      destMarkerRef.current = L.marker([lat, lon], { icon: coloredDivIcon("#ef4444") }).addTo(mapRef.current);
    },
    clearMarkers() {
      [sourceMarkerRef, destMarkerRef, ambulanceMarkerRef].forEach((r) => {
        if (r.current) mapRef.current.removeLayer(r.current);
        r.current = null;
      });
      junctionMarkersRef.current.forEach((m) => mapRef.current.removeLayer(m));
      junctionMarkersRef.current = [];
      if (routeLineRef.current) {
        mapRef.current.removeLayer(routeLineRef.current);
        routeLineRef.current = null;
      }
      Object.values(queueLayersRef.current).forEach((entry) => mapRef.current.removeLayer(entry.layer));
      queueLayersRef.current = {};
      geometryRef.current = [];
    },
    drawRoute(geometryLatLon) {
      geometryRef.current = geometryLatLon;
      if (routeLineRef.current) {
        mapRef.current.removeLayer(routeLineRef.current);
      }
      routeLineRef.current = L.polyline(geometryLatLon, {
        color: "#3b82f6",
        weight: 5,
        opacity: 0.9,
      }).addTo(mapRef.current);

      if (geometryLatLon.length) {
        mapRef.current.fitBounds(routeLineRef.current.getBounds(), { padding: [80, 80] });
      }
    },
    setJunctions(junctions) {
      junctionMarkersRef.current.forEach((m) => mapRef.current.removeLayer(m));
      junctionMarkersRef.current = junctions.map((j) =>
        L.marker([j.lat, j.lon], { icon: junctionDivIcon("#ef4444") }).addTo(mapRef.current)
      );
    },
    updateJunctionColor(index, color) {
      const marker = junctionMarkersRef.current[index];
      if (marker) {
        marker.setIcon(junctionDivIcon(color === "green" ? "#22c55e" : "#ef4444"));
      }
    },
    updateAmbulancePosition(lat, lon) {
      if (!ambulanceMarkerRef.current) {
        ambulanceMarkerRef.current = L.marker([lat, lon], { icon: coloredDivIcon("#3b82f6", 20) }).addTo(
          mapRef.current
        );
      } else {
        ambulanceMarkerRef.current.setLatLng([lat, lon]);
      }
    },
    flyTo(lat, lon) {
      mapRef.current.flyTo([lat, lon], 14);
    },

    // ---------- Standing-vehicle queue visualization ----------

    hasJunctionQueue(index) {
      return !!queueLayersRef.current[index];
    },
    createJunctionQueue(index, lat, lon, vehicleCount) {
      const geometry = geometryRef.current;
      if (!geometry.length || vehicleCount <= 0) return;
      const queueLenM = Math.min(vehicleCount * PER_VEHICLE_M, MAX_QUEUE_M);
      const { coords, cumDist, totalLen } = computeQueueCoords(geometry, lat, lon, queueLenM);
      if (coords.length < 2 || totalLen <= 0) return;
      const layer = L.polyline(coords, {
        color: "#ef4444",
        weight: 7,
        opacity: 0.9,
        lineCap: "round",
      }).addTo(mapRef.current);
      queueLayersRef.current[index] = { layer, coords, cumDist, totalLen };
    },
    updateJunctionQueueFraction(index, fraction) {
      const entry = queueLayersRef.current[index];
      if (!entry) return;
      const { layer, coords, cumDist, totalLen } = entry;
      const clamped = Math.max(0, Math.min(1, fraction));
      const remainingLen = clamped * totalLen;

      if (remainingLen <= 0.001) {
        layer.setLatLngs([]);
        return;
      }
      if (remainingLen >= totalLen) {
        layer.setLatLngs(coords);
        return;
      }

      // The junction end (coords[0]) always stays put; we keep only the portion of
      // the queue from the junction out to `remainingLen` metres upstream, then
      // interpolate the exact cut point so the tail (ambulance side) recedes
      // smoothly toward the junction rather than jumping between sparse vertices.
      let segIdx = 0;
      for (let i = 0; i < cumDist.length - 1; i++) {
        if (cumDist[i] <= remainingLen && remainingLen <= cumDist[i + 1]) {
          segIdx = i;
          break;
        }
        segIdx = i;
      }
      const segStartDist = cumDist[segIdx];
      const segEndDist = cumDist[segIdx + 1] ?? segStartDist + 1;
      const segLen = segEndDist - segStartDist || 1;
      const t = (remainingLen - segStartDist) / segLen;
      const p1 = coords[segIdx];
      const p2 = coords[segIdx + 1] ?? p1;
      const interpLat = p1[0] + (p2[0] - p1[0]) * t;
      const interpLon = p1[1] + (p2[1] - p1[1]) * t;

      const remaining = [...coords.slice(0, segIdx + 1), [interpLat, interpLon]];
      layer.setLatLngs(remaining);
    },
    removeJunctionQueue(index) {
      const entry = queueLayersRef.current[index];
      if (entry) {
        mapRef.current.removeLayer(entry.layer);
        delete queueLayersRef.current[index];
      }
    },
    clearJunctionQueues() {
      Object.values(queueLayersRef.current).forEach((entry) => mapRef.current.removeLayer(entry.layer));
      queueLayersRef.current = {};
    },
  }));

  return <div ref={containerRef} className="map-container" />;
});

export default MapView;
