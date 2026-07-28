// In production (deployed to Vercel/Netlify), set these as build-time env vars:
//   VITE_BACKEND_HTTP=https://your-railway-backend.up.railway.app
//   VITE_BACKEND_WS=wss://your-railway-backend.up.railway.app
//   VITE_GOOGLE_CLIENT_ID=your-google-oauth-client-id.apps.googleusercontent.com
// Locally, these fall back to localhost so `npm run dev` just works without any .env file.

export const BACKEND_HTTP = import.meta.env.VITE_BACKEND_HTTP || "http://localhost:8000";
export const BACKEND_WS = import.meta.env.VITE_BACKEND_WS || "ws://localhost:8000";
export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

// Bangalore bounding box [south, west, north, east] - keeps the map locked to the city
export const BANGALORE_BOUNDS = [
  [12.75, 77.35], // SW (lat, lon)
  [13.2, 77.85],  // NE (lat, lon)
];

export const BANGALORE_CENTER = [12.9716, 77.5946]; // lat, lon

// Nominatim (OpenStreetMap) geocoding - free, no API key required.
// Nominatim's usage policy asks for reasonable request volume and a descriptive
// User-Agent; fine for hackathon-scale use. See README for details.
export const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";
