export function tradeAge(timestamp: string | undefined, now: number): { label: string; stale: boolean } {
  const seconds = timestamp ? (now - Date.parse(timestamp)) / 1000 : NaN;
  if (!Number.isFinite(seconds) || seconds < -60) return { label: "Trade time unavailable", stale: true };
  const age = Math.max(0, Math.floor(seconds));
  const label = age < 60 ? `${age}s` : age < 3600 ? `${Math.floor(age / 60)}m` : `${Math.floor(age / 3600)}h ${Math.floor(age % 3600 / 60)}m`;
  return { label: `Last trade ${label} ago`, stale: age > 90 };
}
