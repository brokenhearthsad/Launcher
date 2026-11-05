import type { LiveSnapshot } from "../api/types";

// Lab map is 100x100 with Radiant bottom-left; SVG y axis is flipped.
const LANES: Record<string, [number, number][]> = {
  top: [[12, 12], [10, 22], [10, 90], [78, 90], [88, 88]],
  mid: [[12, 12], [88, 88]],
  bot: [[12, 12], [22, 10], [90, 10], [90, 78], [88, 88]],
};
const y = (v: number) => 100 - v;

export function MiniMap({ snap, highlight }: { snap: LiveSnapshot; highlight?: number | null }) {
  return (
    <svg viewBox="0 0 100 100" className="aspect-square w-full rounded-lg bg-[#0b1220]" data-testid="minimap" role="img" aria-label="Simulator map">
      <defs>
        <radialGradient id="rad" cx="0" cy="1" r="1"><stop offset="0" stopColor="#14532d" stopOpacity="0.6" /><stop offset="1" stopColor="#0b1220" stopOpacity="0" /></radialGradient>
        <radialGradient id="dir" cx="1" cy="0" r="1"><stop offset="0" stopColor="#450a0a" stopOpacity="0.6" /><stop offset="1" stopColor="#0b1220" stopOpacity="0" /></radialGradient>
      </defs>
      <rect width="100" height="100" fill="url(#rad)" />
      <rect width="100" height="100" fill="url(#dir)" />
      <line x1="0" y1="0" x2="100" y2="100" stroke="#1e3a5f" strokeWidth="3" opacity="0.5" />
      {Object.entries(LANES).map(([k, pts]) => (
        <polyline key={k} points={pts.map(([a, b]) => `${a},${y(b)}`).join(" ")} fill="none" stroke="#334155" strokeWidth="1.6" strokeLinecap="round" />
      ))}
      {Object.entries(snap.creeps).map(([lane, c]) => c.front && (
        <circle key={lane} cx={c.front[0]} cy={y(c.front[1])} r={1.4} fill={c.radiant >= c.dire ? "#86efac" : "#fca5a5"} opacity={0.6} />
      ))}
      {snap.wards.map((w, i) => (
        <circle key={i} cx={w.pos[0]} cy={y(w.pos[1])} r={1} fill="none" stroke={w.team === "radiant" ? "#4ade80" : "#f87171"} strokeWidth="0.4" />
      ))}
      {snap.towers.map((t) => (
        <rect key={t.uid} x={t.pos[0] - (t.tier === "ancient" ? 2.2 : 1.2)} y={y(t.pos[1]) - (t.tier === "ancient" ? 2.2 : 1.2)}
          width={t.tier === "ancient" ? 4.4 : 2.4} height={t.tier === "ancient" ? 4.4 : 2.4}
          fill={t.alive ? (t.team === "radiant" ? "#22c55e" : "#ef4444") : "#1f2937"}
          stroke={t.alive ? "#0b1220" : "#374151"} strokeWidth="0.3" opacity={t.alive ? 0.4 + 0.6 * (t.hp / t.max_hp) : 1}>
          <title>{t.uid} {t.alive ? `${t.hp}/${t.max_hp}` : "destroyed"}</title>
        </rect>
      ))}
      <circle cx={38} cy={y(60)} r={2} fill={snap.roshan.alive ? "#a855f7" : "#374151"}><title>Roshan</title></circle>
      {snap.heroes.filter((h) => h.alive).map((h) => (
        <g key={h.player_id}>
          <circle cx={h.pos[0]} cy={y(h.pos[1])} r={highlight === h.player_id ? 2.4 : 1.8}
            fill={h.team === "radiant" ? "#4ade80" : "#f87171"} stroke={h.has_aegis ? "#facc15" : "#0b1220"} strokeWidth="0.6" />
          <text x={h.pos[0]} y={y(h.pos[1]) + 0.9} fontSize="2.2" textAnchor="middle" fill="#0b1220" fontWeight="bold">{h.name.slice(-1)}</text>
          <title>{h.name} ({h.hero_name}) — {h.action}</title>
        </g>
      ))}
    </svg>
  );
}
