import React from "react";
import { formatDuration } from "../utils.js";

export default function CalculationsPanel({ visible, data }) {
  if (!visible) return null;

  const rows = [
    ["Next junction in", data.nextJunctionEta != null ? formatDuration(data.nextJunctionEta) : "--"],
    ["Vehicles in junction", data.vehicleCount != null ? data.vehicleCount : "--"],
    ["Time to clear junction", data.clearTime != null ? formatDuration(data.clearTime) : "--"],
    ["Signal opens in", data.signalOpensIn != null ? formatDuration(data.signalOpensIn) : "--"],
    ["Average speed", data.avgSpeed != null ? `${data.avgSpeed.toFixed(1)} km/h` : "--"],
    ["Distance remaining", data.distanceRemaining != null ? `${(data.distanceRemaining / 1000).toFixed(2)} km` : "--"],
    ["Elapsed time", data.elapsed != null ? formatDuration(data.elapsed) : "--"],
  ];

  return (
    <div className="calc-panel">
      {rows.map(([k, v]) => (
        <div className="calc-row" key={k}>
          <span className="k">{k}</span>
          <span className="v">{v}</span>
        </div>
      ))}
    </div>
  );
}
