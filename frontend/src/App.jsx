import React, { useRef, useState, useCallback } from "react";
import MapView from "./components/MapView.jsx";
import CalculationsPanel from "./components/CalculationsPanel.jsx";
import { BACKEND_HTTP, BACKEND_WS, NOMINATIM_URL } from "./config.js";
import { formatDuration } from "./utils.js";
import { authHeader, getToken } from "./authApi.js";

const MODES = { EMERGENCY: "emergency", AMBULANCE: "ambulance" };

export default function App({ user, onLogout }) {
  const mapRef = useRef(null);
  const wsRef = useRef(null);
  const junctionQueueStateRef = useRef({}); // { [junctionIndex]: { greenStartElapsed, cleared } }

  const [mode, setMode] = useState(MODES.EMERGENCY);
  const [source, setSource] = useState(null); // {lat, lon}
  const [destination, setDestination] = useState(null);
  const [severity, setSeverity] = useState(null);
  const [emergencyText, setEmergencyText] = useState("");
  const [matchedSpecialty, setMatchedSpecialty] = useState(null);
  const [sourceText, setSourceText] = useState("");
  const [destText, setDestText] = useState("");

  const [route, setRoute] = useState(null); // {geometry, junctions, duration_seconds, distance_meters}
  const [selectedHospital, setSelectedHospital] = useState(null);

  const [isSimulating, setIsSimulating] = useState(false);
  const [calcVisible, setCalcVisible] = useState(false);
  const [calcData, setCalcData] = useState({});
  const [error, setError] = useState(null);

  const showError = (msg) => {
    setError(msg);
    setTimeout(() => setError(null), 4000);
  };

  // ---------- Geocoding (Nominatim / OpenStreetMap) for the text search boxes ----------

  const geocode = async (query) => {
    // viewbox + bounded=1 restricts results to the Bangalore bounding box
    const url =
      `${NOMINATIM_URL}?q=${encodeURIComponent(query)}` +
      `&format=json&limit=1&viewbox=77.35,13.20,77.85,12.75&bounded=1`;
    const res = await fetch(url, {
      headers: { "Accept-Language": "en" },
    });
    const data = await res.json();
    if (!data.length) throw new Error("Location not found in Bangalore");
    return { lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon) };
  };

  const handleSourceSearch = async () => {
    if (!sourceText.trim()) return;
    try {
      const pt = await geocode(sourceText);
      setSource(pt);
      mapRef.current.setSourceMarker(pt.lat, pt.lon);
      mapRef.current.flyTo(pt.lat, pt.lon);
    } catch (e) {
      showError(e.message);
    }
  };

  const handleDestSearch = async () => {
    if (!destText.trim()) return;
    try {
      const pt = await geocode(destText);
      setDestination(pt);
      mapRef.current.setDestMarker(pt.lat, pt.lon);
    } catch (e) {
      showError(e.message);
    }
  };

  // ---------- Map double-click handling ----------

  const handleMapDoubleClick = useCallback(
    (pt) => {
      if (mode === MODES.AMBULANCE) {
        setSource(pt);
        setDestination(null);
        setSelectedHospital(null);
        setMatchedSpecialty(null);
        mapRef.current.setSourceMarker(pt.lat, pt.lon);
        return;
      }
      // Emergency mode: first click = source, second = destination
      if (!source) {
        setSource(pt);
        mapRef.current.setSourceMarker(pt.lat, pt.lon);
      } else if (!destination) {
        setDestination(pt);
        mapRef.current.setDestMarker(pt.lat, pt.lon);
      } else {
        // reset and start over
        setSource(pt);
        setDestination(null);
        setRoute(null);
        mapRef.current.clearMarkers();
        mapRef.current.setSourceMarker(pt.lat, pt.lon);
      }
    },
    [mode, source, destination]
  );

  // ---------- Route calculation ----------

  const calculateRoute = async (dest) => {
    if (!source || !dest) return;
    try {
      const res = await fetch(`${BACKEND_HTTP}/route`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify({ source, destination: dest }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Routing failed");
      const data = await res.json();
      setRoute(data);
      mapRef.current.drawRoute(data.geometry);
      mapRef.current.setJunctions(
        data.junctions.map((j, i) => ({ lat: j[0], lon: j[1], index: i }))
      );
    } catch (e) {
      showError(e.message);
    }
  };

  // Auto-calculate for emergency mode once both points are set
  React.useEffect(() => {
    if (mode === MODES.EMERGENCY && source && destination) {
      calculateRoute(destination);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, destination, mode]);

  // ---------- Ambulance mode: severity selection -> nearest hospital ----------

  const runHospitalSearch = async (level) => {
    if (!source) {
      showError("Pick a source location first (double-click the map or search)");
      return;
    }
    setSeverity(level);
    try {
      const res = await fetch(`${BACKEND_HTTP}/nearest-hospital`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify({
          source,
          severity: level,
          emergency_text: emergencyText.trim() || null,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Hospital selection failed");
      const hospital = await res.json();
      setSelectedHospital(hospital);
      setMatchedSpecialty(hospital.matched_specialty || null);
      mapRef.current.setDestMarker(hospital.lat, hospital.lon);
      setRoute(hospital.route);
      mapRef.current.drawRoute(hospital.route.geometry);
      mapRef.current.setJunctions(
        hospital.route.junctions.map((j, i) => ({ lat: j[0], lon: j[1], index: i }))
      );
    } catch (e) {
      showError(e.message);
    }
  };

  const handleSeverityPick = (level) => runHospitalSearch(level);

  const handleEmergencyTextSubmit = () => {
    if (!severity) {
      showError("Pick a severity level first, then describe the emergency");
      return;
    }
    runHospitalSearch(severity);
  };

  // ---------- Mode toggle ----------

  const switchMode = (newMode) => {
    setMode(newMode);
    setSource(null);
    setDestination(null);
    setSeverity(null);
    setEmergencyText("");
    setMatchedSpecialty(null);
    setSelectedHospital(null);
    setRoute(null);
    setSourceText("");
    setDestText("");
    setIsSimulating(false);
    wsRef.current?.close();
    mapRef.current.clearMarkers();
  };

  // ---------- Simulation ----------

  const startSimulation = () => {
    if (!route) {
      showError("Calculate a route first");
      return;
    }
    setIsSimulating(true);
    setCalcVisible(true);
    junctionQueueStateRef.current = {};
    mapRef.current.clearJunctionQueues();

    const ws = new WebSocket(`${BACKEND_WS}/ws/simulate?token=${encodeURIComponent(getToken() || "")}`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          geometry: route.geometry,
          junctions: route.junctions.map((j) => j),
          speed_kmh: 45,
        })
      );
    };

    ws.onmessage = (event) => {
      const state = JSON.parse(event.data);
      if (state.error) {
        showError(state.error);
        return;
      }
      mapRef.current.updateAmbulancePosition(state.ambulance.lat, state.ambulance.lon);

      let nextJunction = null;
      let nextJunctionFraction = 1;
      state.junctions.forEach((j, i) => {
        mapRef.current.updateJunctionColor(i, j.signal_color);

        // ---- standing-vehicle queue visualization ----
        const qState = junctionQueueStateRef.current[i] || {
          greenStartElapsed: null,
          cleared: false,
          fraction: 1,
        };
        if (!qState.cleared) {
          if (!mapRef.current.hasJunctionQueue(i) && j.vehicle_count > 0) {
            mapRef.current.createJunctionQueue(i, j.lat, j.lon, j.vehicle_count);
          }
          if (j.signal_color === "green") {
            if (qState.greenStartElapsed === null) qState.greenStartElapsed = state.elapsed_s;
            const elapsedSinceGreen = state.elapsed_s - qState.greenStartElapsed;
            const fraction = 1 - elapsedSinceGreen / Math.max(j.clear_time_s, 0.5);
            qState.fraction = Math.max(0, Math.min(1, fraction));
            mapRef.current.updateJunctionQueueFraction(i, fraction);
            if (fraction <= 0) {
              qState.cleared = true;
              qState.fraction = 0;
              mapRef.current.removeJunctionQueue(i);
            }
          } else {
            qState.fraction = 1;
            mapRef.current.updateJunctionQueueFraction(i, 1);
          }
        }
        junctionQueueStateRef.current[i] = qState;
      });

      // The "next junction" for the calc panel is the first not-yet-cleared junction
      // in route order (junctions are already ordered source -> destination), not
      // just whichever happens to be closest by straight-line distance. This makes
      // the panel advance cleanly the moment the ambulance actually clears a junction,
      // and fall back to "--" once every junction on the route has been passed.
      for (let i = 0; i < state.junctions.length; i++) {
        const qState = junctionQueueStateRef.current[i];
        if (!qState || !qState.cleared) {
          nextJunction = state.junctions[i];
          nextJunctionFraction = qState ? qState.fraction : 1;
          break;
        }
      }

      setCalcData({
        nextJunctionEta: nextJunction ? nextJunction.eat_seconds : null,
        vehicleCount: nextJunction
          ? Math.round(nextJunction.vehicle_count * nextJunctionFraction)
          : null,
        clearTime: nextJunction ? nextJunction.clear_time_s : null,
        signalOpensIn: nextJunction ? nextJunction.signal_opens_in_s : null,
        distanceRemaining: state.distance_remaining_m,
        elapsed: state.elapsed_s,
        avgSpeed: state.avg_speed_kmh,
      });

      if (state.arrived) {
        setIsSimulating(false);
        ws.close();
        wsRef.current = null;
      }
    };

    ws.onerror = () => showError("Simulation connection error");

    ws.onclose = (event) => {
      if (event.code === 4401) {
        showError("Session expired - please sign in again");
        onLogout();
      }
    };
  };

  const stopSimulation = () => {
    wsRef.current?.close();
    wsRef.current = null;
    setIsSimulating(false);
    junctionQueueStateRef.current = {};
    mapRef.current.clearJunctionQueues();
    setCalcData({});

    // Reset the map back to a ready-for-next-turn state: ambulance back at the
    // source, all junctions back to red.
    if (route && source) {
      mapRef.current.updateAmbulancePosition(source.lat, source.lon);
      mapRef.current.setJunctions(
        route.junctions.map((j, i) => ({ lat: j[0], lon: j[1], index: i }))
      );
    }
  };

  const startLive = () => {
    // Placeholder for real GPS-based tracking. In simulate mode above we already
    // demonstrate the full calculation pipeline; wiring actual device GPS just
    // means feeding navigator.geolocation.watchPosition() into the same state
    // updates used by the simulator.
    showError("Live GPS mode: wire navigator.geolocation.watchPosition() here for a real device demo");
  };

  return (
    <div className="app">
      <MapView ref={mapRef} onMapDoubleClick={handleMapDoubleClick} />

      {error && <div className="error-toast">{error}</div>}

      <div className="user-badge">
        <span>{user?.name || user?.email}</span>
        <button className="logout-btn" onClick={onLogout}>
          Log out
        </button>
      </div>

      <div className="control-panel">
        <div className="mode-label">
          <span className={`mode-dot ${mode === MODES.AMBULANCE ? "ambulance" : ""}`} />
          {mode === MODES.AMBULANCE ? "Ambulance Dispatch" : "Emergency Vehicle Routing"}
        </div>

        <div className="field">
          <label>Source</label>
          <input
            placeholder="Search or double-click map"
            value={sourceText}
            onChange={(e) => setSourceText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSourceSearch()}
          />
        </div>

        {mode === MODES.EMERGENCY && (
          <div className="field">
            <label>Destination</label>
            <input
              placeholder="Search or double-click map"
              value={destText}
              onChange={(e) => setDestText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleDestSearch()}
            />
          </div>
        )}

        {mode === MODES.AMBULANCE && (
          <div className="field">
            <label>Emergency severity</label>
            <div className="severity-row">
              {["primary", "secondary", "tertiary"].map((lvl) => (
                <button
                  key={lvl}
                  className={`severity-btn ${severity === lvl ? `active ${lvl}` : ""}`}
                  onClick={() => handleSeverityPick(lvl)}
                >
                  {lvl}
                </button>
              ))}
            </div>
          </div>
        )}

        {mode === MODES.AMBULANCE && (
          <div className="field">
            <label>Describe the emergency (optional)</label>
            <input
              placeholder="e.g. eye injury, chest pain, broken leg..."
              value={emergencyText}
              onChange={(e) => setEmergencyText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleEmergencyTextSubmit()}
            />
            {matchedSpecialty && (
              <div className="specialty-match">
                Matched: <strong>{matchedSpecialty.replace(/_/g, " ")}</strong>
              </div>
            )}
          </div>
        )}

        <div className="hint">
          {mode === MODES.EMERGENCY
            ? "Double-click to set source, double-click again to set destination."
            : "Double-click the map to set the ambulance location, then choose severity."}
        </div>

        {route && (
          <div className="route-summary">
            ETA: <strong>{formatDuration(route.duration_seconds)}</strong> &nbsp;|&nbsp; Distance:{" "}
            <strong>{(route.distance_meters / 1000).toFixed(2)} km</strong>
            {selectedHospital && (
              <div style={{ marginTop: 4 }}>
                Hospital: <strong>{selectedHospital.name}</strong> ({selectedHospital.type})
              </div>
            )}
          </div>
        )}

        <div className="btn-row">
          <button className="btn-primary" onClick={startLive} disabled={!route || isSimulating}>
            Start
          </button>
          <button
            className="btn-danger"
            onClick={isSimulating ? stopSimulation : startSimulation}
            disabled={!route}
          >
            {isSimulating ? "Stop" : "Simulate"}
          </button>
        </div>
      </div>

      <div className="mode-toggle">
        <button className={mode === MODES.EMERGENCY ? "active" : ""} onClick={() => switchMode(MODES.EMERGENCY)}>
          Emergency
        </button>
        <button className={mode === MODES.AMBULANCE ? "active" : ""} onClick={() => switchMode(MODES.AMBULANCE)}>
          Ambulance
        </button>
      </div>

      {route && (
        <button className="calc-toggle-btn" onClick={() => setCalcVisible((v) => !v)}>
          {calcVisible ? "Hide calculations" : "Show calculations"}
        </button>
      )}

      <CalculationsPanel visible={calcVisible} data={calcData} />

      {isSimulating && (
        <div className="status-readout">
          <div>Elapsed</div>
          <div className="big">{calcData.elapsed != null ? formatDuration(calcData.elapsed) : "0.0s"}</div>
        </div>
      )}
    </div>
  );
}
