// Formats a duration in seconds into a human-readable string.
// Under 60s: keeps one decimal place, since short countdowns (junction ETAs,
// signal-open timers) read better with sub-second precision while ticking down.
// 60s and above: switches to whole-number h/m/s, only including hours and
// minutes when they're actually non-zero.
export function formatDuration(totalSeconds) {
  if (totalSeconds == null || Number.isNaN(totalSeconds)) return "--";

  const isNegative = totalSeconds < 0;
  const abs = Math.abs(totalSeconds);

  if (abs < 60) {
    return `${isNegative ? "-" : ""}${abs.toFixed(1)}s`;
  }

  let s = Math.round(abs);
  const h = Math.floor(s / 3600);
  s -= h * 3600;
  const m = Math.floor(s / 60);
  s -= m * 60;

  const parts = [];
  if (h > 0) parts.push(`${h}h`);
  if (h > 0 || m > 0) parts.push(`${h > 0 ? String(m).padStart(2, "0") : m}m`);
  parts.push(`${(h > 0 || m > 0) ? String(s).padStart(2, "0") : s}s`);

  return `${isNegative ? "-" : ""}${parts.join(" ")}`;
}
