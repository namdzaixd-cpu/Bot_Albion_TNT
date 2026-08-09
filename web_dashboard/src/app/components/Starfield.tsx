"use client";

// Seeded star positions to avoid SSR/CSR hydration mismatch
const STARS = Array.from({ length: 90 }, (_, i) => {
  // deterministic pseudo-random based on index
  const a = Math.sin(i * 12.9898) * 43758.5453;
  const b = Math.sin(i * 78.233) * 12543.123;
  const x = Number((((a - Math.floor(a)) * 100)).toFixed(4));
  const y = Number((((b - Math.floor(b)) * 100)).toFixed(4));
  const s = 1 + ((i * 7) % 3); // 1-3px
  const tw = 2.5 + ((i * 3) % 5); // 2.5-6.5s
  const delay = (i % 7) * 0.4;
  return { x, y, s, tw, delay };
});

// Big Dipper (Ursa Major) — 7 stars with connecting lines (relative coords 0-100)
const DIPPER = {
  stars: [
    [12, 78], [30, 70], [46, 74], [58, 60], [74, 50], [82, 34], [66, 26],
  ],
  lines: [
    [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 3],
  ],
};

export default function Starfield() {
  return (
    <>
      <div className="sky" />
      <div className="grid-overlay" />
      <div className="starfield" aria-hidden>
        {STARS.map((st, i) => (
          <span
            key={i}
            className="star"
            style={{
              left: `${st.x}%`,
              top: `${st.y}%`,
              width: st.s,
              height: st.s,
              ["--tw" as any]: `${st.tw}s`,
              animationDelay: `${st.delay}s`,
            }}
          />
        ))}
      </div>

      {/* Northern Constellation — Big Dipper */}
      <div className="constellation" aria-hidden>
        <svg viewBox="0 0 100 100">
          {DIPPER.lines.map(([a, b], i) => (
            <line
              key={i}
              className="line"
              x1={DIPPER.stars[a][0]}
              y1={DIPPER.stars[a][1]}
              x2={DIPPER.stars[b][0]}
              y2={DIPPER.stars[b][1]}
            />
          ))}
          {DIPPER.stars.map(([x, y], i) => (
            <circle
              key={i}
              className="cstar"
              cx={x}
              cy={y}
              r={3}
              style={{ animationDelay: `${i * 0.4}s` }}
            />
          ))}
        </svg>
      </div>
    </>
  );
}
