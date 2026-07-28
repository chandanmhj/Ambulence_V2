# Bangalore Emergency Vehicle Routing System

Full stack: OSRM (real road routing) + FastAPI backend (hospital selection, ML junction
models, simulation, user auth) + React/Leaflet frontend. No paid API keys required for
local dev - OSRM is self-hosted and the map uses free OpenStreetMap/CARTO tiles.

**The app now requires signing in** (email/password or Google) before any routing
features are usable - every backend endpoint except `/health` and `/auth/*` requires
a valid token. Locally this uses a SQLite file (`backend/local_dev.db`, auto-created)
so you can sign up and test without setting up Postgres. See `DEPLOYMENT.md` for
production deployment (Railway + Vercel) including Postgres and Google OAuth setup.

Everything below is written point-to-point. Follow it in order — later steps assume
earlier ones are done.

---

## 0. Prerequisites

Install these first if you don't have them:

- **Docker Desktop** (includes Docker Compose) — https://www.docker.com/products/docker-desktop/
- **Node.js 18+** — https://nodejs.org/

That's it — no API keys or paid accounts needed. Routing runs on your own OSRM
container and the map uses free OpenStreetMap/CARTO tiles.

---

## 1. Prepare the OSRM routing data (one-time setup)

OSRM needs a preprocessed Bangalore map extract before it can serve routes. This is a
one-time step — the processed files are reused every time you run the project after.

Open a terminal in the project root (`ambulance-system/`) and run:

```bash
mkdir osrm-data
cd osrm-data

# Download the Karnataka extract (includes Bangalore) from Geofabrik
curl -O https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf

# Rename for clarity
mv southern-zone-latest.osm.pbf bangalore.osm.pbf

# Extract, partition, and customize using OSRM's Docker image (car profile, MLD algorithm)
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/bangalore.osm.pbf
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-partition /data/bangalore.osrm
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-customize /data/bangalore.osrm

cd ..
```

**Note:** the southern-zone extract covers a large area (all of Karnataka + neighbors),
so `osrm-extract` can take 5-15 minutes depending on your machine. This is expected —
it only needs to happen once. If you want a smaller/faster extract, you can crop the
`.pbf` to just the Bangalore metro bounding box first using `osmium extract`, but it's
optional.

---

## 2. Add your hospital dataset

The repo ships with `backend/data/hospitals.json` containing ~15 sample Bangalore
hospitals so the project runs out of the box. Replace it with your full classified
dataset (the one we built earlier via the Overpass fetch + classification script):

```bash
cp /path/to/your/hospitals.json backend/data/hospitals.json
```

Keep the same schema: `{"name", "lat", "lon", "type", "emergency", "operator_type", "phone"}`
with `type` being one of `"primary"`, `"secondary"`, `"tertiary"`.

---

## 3. Start the backend + OSRM

From the project root:

```bash
docker compose up --build
```

This builds and starts two containers:
- `ambulance_osrm` — serves routing on `localhost:5000`
- `ambulance_backend` — FastAPI on `localhost:8000` (also trains the two synthetic ML
  models automatically during the image build — you'll see MAE printed in the build logs)

Wait until you see `Uvicorn running on http://0.0.0.0:8000` in the logs. Verify it's
alive:

```bash
curl http://localhost:8000/health
# should return {"status":"ok"}
```

---

## 4. Start the frontend

Open a **second terminal**:

```bash
cd frontend
npm install
npm run dev
```

It'll print a local URL, typically `http://localhost:5173`. Open that in your browser.

---

## 5. Using the app

**Emergency mode (default, blue dot in top-left panel):**
1. Double-click the map to set source, double-click again to set destination
   (or type into the Source/Destination search boxes and press Enter)
2. Route calculates automatically and draws on the map
3. Click **Simulate** to watch the ambulance move and signals turn green as it
   approaches each junction
4. Click **Show calculations** to see the live EAT / vehicle count / clear time /
   signal-open countdown

**Ambulance mode (toggle bottom-right, red dot):**
1. Double-click the map to set the ambulance's current location (or search)
2. Click a severity button: **primary / secondary / tertiary**
3. The backend picks the correct hospital automatically and draws the route
4. Same Start/Simulate/calculations flow as above

**Start vs Simulate:** `Simulate` is fully wired end-to-end (physics-based movement +
live junction signal logic streamed over WebSocket). `Start` is a placeholder stub for
real device GPS — see the comment in `App.jsx` (`startLive`) for the one function call
(`navigator.geolocation.watchPosition`) needed to wire it to a real phone for a live
demo.

---

## Project structure

```
ambulance-system/
├── docker-compose.yml          # OSRM + backend orchestration
├── osrm-data/                  # created in Step 1, holds preprocessed map
├── backend/
│   ├── main.py                 # FastAPI app, all HTTP + WebSocket endpoints
│   ├── routing.py              # OSRM client wrapper
│   ├── hospital_selector.py    # severity-based nearest-hospital algorithm
│   ├── simulation.py           # ambulance movement + junction signal simulation
│   ├── data/hospitals.json     # your hospital dataset (replace the sample)
│   └── ml_models/
│       ├── generate_synthetic_data.py   # synthetic training data for both models
│       ├── train_eat_model.py           # trains junction arrival-time model
│       ├── train_clear_time_model.py    # trains junction clear-time model
│       └── predictor.py                 # inference wrapper used by the API
└── frontend/
    └── src/
        ├── App.jsx              # main UI logic, mode toggle, controls
        ├── config.js            # backend URLs + Nominatim geocoding endpoint
        └── components/
            ├── MapView.jsx           # Leaflet map, markers, route line
            └── CalculationsPanel.jsx # live calc readout panel
```

---

## API reference (for your own testing / Postman)

| Endpoint | Method | Purpose |
|---|---|---|
| `/route` | POST | Shortest-time path between two points |
| `/nearest-hospital` | POST | Severity-based hospital selection + route |
| `/hospitals` | GET | Full hospital dataset |
| `/junction-eta` | POST | Model 1: predict arrival time to a junction |
| `/junction-clear-time` | POST | Model 2: predict time to clear a junction |
| `/ws/simulate` | WS | Streams live simulation state |

---

## Known limitations / things to mention if judges ask

- The two junction ML models are trained on **synthetic but physically-grounded**
  data (physics for EAT, a queueing-discharge formula for clear time), since no real
  Bangalore signal/VAC sensor feed is publicly available. This is disclosed in-code
  (`generate_synthetic_data.py` docstring) — be upfront about it in the demo, it's a
  legitimate and common approach for prototyping traffic-ML without live sensor access.
- "Junctions" along a route come from OSRM's turn/maneuver waypoints (a well-established
  proxy), not a separate curated junction database.
- Hospital classification (primary/secondary/tertiary) came from OSM tags + a
  keyword-based classifier — accurate for major hospitals, approximate for smaller ones.
- `Start` mode (real GPS) is stubbed — `Simulate` is the fully working demo path.
- The search boxes use Nominatim (OpenStreetMap's free geocoder), which has a soft
  rate limit of ~1 request/second. Fine for a live demo where you're typing one
  address at a time; don't hammer it in a loop.
