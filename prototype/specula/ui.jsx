// ============================================================
// SPECULA — shared UI: match meter (3 styles), icons, helpers
// ============================================================
const { useState, useEffect, useRef, useMemo, useLayoutEffect } = React;

function matchColor(job) {
  if (job.redFlag) return "var(--warn)";
  if (job.match >= 85) return "var(--accent)";
  return "var(--ink)";
}

// The signature: renders bars / figure / ring depending on `mstyle`.
// replay: changing it re-runs the sweep (used for lens re-sort).
// reveal: drawer "scoring…" reveal. countUp: count the number up.
function MatchMeter({ job, mstyle = "bars", replay, reveal = false, countUp = false }) {
  const f = job.factors;
  const col = matchColor(job);
  const segs = [["ROLE", f.role], ["SKILL", f.skill], ["LOC", f.loc]];
  const [shown, setShown] = useState(false);
  const [done, setDone] = useState(false);
  useEffect(() => {
    setShown(false); setDone(false);
    const t = setTimeout(() => setShown(true), reveal ? 320 : 40);
    return () => clearTimeout(t);
  }, [replay]);
  useEffect(() => {
    if (!shown) return;
    const t = setTimeout(() => setDone(true), reveal ? 820 : 0);
    return () => clearTimeout(t);
  }, [shown, reveal]);
  const counting = countUp || reveal;
  const num = useCountUp(job.match, shown && counting, reveal ? 780 : 640);
  const display = counting ? num : job.match;
  const ringDeg = (shown ? job.match : 0) * 3.6;
  return (
    <div className="meter" data-style={mstyle}>
      <div className="meter-top">
        <span className="meter-num" style={{ color: col }}>{display}</span>
        <span className="meter-of">/100</span>
        <span className="meter-lab">{reveal && !done ? "scoring…" : <>match<br />index</>}</span>
      </div>
      <div className="bars">
        {segs.map(([k, v]) => (
          <div className="bar-row" key={k}>
            <span className="bar-k">{k}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: (shown ? v : 0) + "%", background: v < 50 ? "var(--warn)" : col }} />
            </span>
            <span className="bar-v">{v}</span>
          </div>
        ))}
      </div>
      <div className="ring-wrap">
        <div className="ring" style={{ background: `conic-gradient(${col} ${ringDeg}deg, var(--panel-2) 0)`, transition: "background .9s cubic-bezier(.3,1,.3,1)" }}>
          <div className="ring-in">
            <span className="ring-num" style={{ color: col }}>{display}</span>
            <span className="ring-lab">{reveal && !done ? "···" : "match"}</span>
          </div>
        </div>
        <div className="ring-fac">
          {segs.map(([k, v]) => <span key={k}>{k[0]}·{v}</span>)}
        </div>
      </div>
    </div>
  );
}

// Small skill-overlap inline bar
function OverlapBar({ overlap }) {
  const low = overlap[0] / overlap[1] < 0.4;
  return (
    <span className={"jov" + (low ? " low" : "")}>
      <span className="jov-bar"><span style={{ width: (overlap[0] / overlap[1] * 100) + "%" }} /></span>
      [{overlap[0]}/{overlap[1]}] req. skills
    </span>
  );
}

// Icon set — minimal geometric line icons
const I = {
  jobs: 'M2 3h12M2 8h12M2 13h8',
  approvals: 'M3 8l3.5 3.5L13 4',
  companies: 'M2.5 14V5l5-2.5L12.5 5v9M5.5 8h0.5M5.5 11h0.5M9.5 8h0.5M9.5 11h0.5',
  insights: 'M2 14V2M2 14h12M5 11l3-4 2 2 3-5',
  profiles: 'M3 4h10M5 8h8M7 12h6',
  candidate: 'M8 8.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM3 14c0-2.5 2.2-4 5-4s5 1.5 5 4',
  targeting: 'M8 14A6 6 0 108 2a6 6 0 000 12zM8 11a3 3 0 100-6 3 3 0 000 6zM8 8h0.01',
};
function Icon({ name }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d={I[name]} />
    </svg>
  );
}

// count-up hook
function useCountUp(target, run, dur = 900) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!run) { setV(0); return; }
    let raf, start;
    const step = (t) => {
      if (!start) start = t;
      const p = Math.min((t - start) / dur, 1);
      const e = 1 - Math.pow(1 - p, 3);
      setV(Math.round(target * e));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, run, dur]);
  return v;
}

Object.assign(window, { MatchMeter, OverlapBar, Icon, matchColor, useCountUp,
  useState, useEffect, useRef, useMemo, useLayoutEffect });
