// ============================================================
// SPECULA — Insights / personal market intelligence
// ============================================================

function DemandTrend({ trend }) {
  const totals = trend.weeks.map((_, wi) => trend.series.reduce((s, ser) => s + ser.data[wi], 0));
  const max = Math.max(...totals);
  return (
    <div>
      <div className="trend">
        {trend.weeks.map((wk, wi) => (
          <div className="trend-col" key={wk}>
            <div className="trend-stack">
              {trend.series.map((ser) => (
                <div key={ser.name} className="trend-seg"
                  style={{ background: ser.color, height: (ser.data[wi] / max * 130) + "px" }} />
              ))}
            </div>
            <span className="trend-x">{wk}</span>
          </div>
        ))}
      </div>
      <div className="legend">
        {trend.series.map((s) => <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>)}
      </div>
    </div>
  );
}

function InsightsView() {
  const ins = SPECULA.insights;
  const [run, setRun] = useState(false);
  useEffect(() => { const t = setTimeout(() => setRun(true), 80); return () => clearTimeout(t); }, []);
  const analysed = useCountUp(ins.totalAnalysed, run);
  const seniorMax = Math.max(...ins.seniorityMix.map((s) => s.v));

  return (
    <div className="view">
      <div className="vhead">
        <div className="vhead-l">
          <h1 className="vtitle">Insights</h1>
          <p className="vsub">Personal market intelligence — aggregates over every structured posting you've collected. Most trackers can't show this because they never parse the ads. Low-confidence extractions are excluded.</p>
        </div>
        <div className="vhead-stat">
          <select className="sortsel" defaultValue="8w" style={{ fontSize: 12 }}>
            <option value="4w">Last 4 weeks</option>
            <option value="8w">Last 8 weeks</option>
            <option value="q">This quarter</option>
          </select>
          <span className="vstat-sep" />
          <div><b>{analysed}</b> <span className="mono"> analysed</span></div>
        </div>
      </div>

      <p className="appr-why" style={{ marginTop: 16 }}>⚐ {ins.lowConfExcluded} low-confidence extractions excluded from every aggregate below. Treat trends as directional.</p>

      <div className="ins-grid">
        <div className="panel">
          <div className="panel-h"><span className="panel-t">Skill demand</span><span className="panel-s">% of postings · Δ vs 8w ago</span></div>
          <div className="demand">
            {ins.skillDemand.map((s) => (
              <div className="demand-row" key={s.skill}>
                <span className="demand-k">{s.skill}{s.gap && <span className="tag-flag" style={{ marginLeft: 6, fontSize: 9 }}>gap</span>}</span>
                <span className="demand-track"><span className={"demand-fill" + (s.up ? " up" : "")} style={{ width: (run ? s.pct : 0) + "%" }} /></span>
                <span className={"demand-d " + (s.delta >= 0 ? "up" : "down")}>{s.delta >= 0 ? "▲" : "▼"} {Math.abs(s.delta)}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-h"><span className="panel-t">Demand drift</span><span className="panel-s">stacked, weekly</span></div>
          <DemandTrend trend={ins.trend} />
        </div>

        <div className="panel">
          <div className="panel-h"><span className="panel-t">Seniority mix</span><span className="panel-s">% of pool</span></div>
          <div className="demand">
            {ins.seniorityMix.map((s) => (
              <div className="demand-row" key={s.k}>
                <span className="demand-k">{s.k}</span>
                <span className="demand-track"><span className="demand-fill" style={{ width: (run ? s.v / seniorMax * 100 : 0) + "%", background: s.k === "Senior" ? "var(--accent)" : "var(--ink)" }} /></span>
                <span className="demand-d mono">{s.v}%</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-h"><span className="panel-t">Work-mode mix</span><span className="panel-s">& its drift</span></div>
          <div className="mixbar">
            {ins.modeMix.map((m) => (
              <div key={m.k} style={{ flex: run ? m.v : 1, background: m.color }}>{m.v}%</div>
            ))}
          </div>
          <div className="legend">
            {ins.modeMix.map((m) => <span key={m.k}><i style={{ background: m.color }} />{m.k}</span>)}
          </div>
          <p className="appr-why" style={{ marginTop: 14 }}>Remote share is up <b style={{ color: "var(--accent-ink)" }}>+5pts</b> over 8 weeks — good news for your remote-EU lens.</p>
        </div>

        <div className="panel">
          <div className="panel-h"><span className="panel-t">Salary distribution</span><span className="panel-s">where listed · informational</span></div>
          <div className="salary-rows">
            {ins.salary.map((s) => (
              <div className="sal-row" key={s.band}>
                <span className="mono" style={{ fontSize: 12 }}>{s.band}</span>
                <span className="sal-bar"><span style={{ left: s.lo + "%", width: (run ? (s.hi - s.lo) : 0) + "%" }} /></span>
              </div>
            ))}
          </div>
          <p className="appr-why" style={{ marginTop: 14 }}>Only ~38% of ads list pay. Never used to rank or filter — shown for context only.</p>
        </div>

        <div className="panel">
          <div className="panel-h"><span className="panel-t">Most-active companies</span><span className="panel-s">postings, 8w</span></div>
          <div className="demand">
            {ins.activeCompanies.map((c, i) => (
              <div className="demand-row" key={c.name} style={{ gridTemplateColumns: "120px 1fr 30px" }}>
                <span className="demand-k">{c.name}</span>
                <span className="demand-track"><span className="demand-fill" style={{ width: (run ? c.n / 12 * 100 : 0) + "%", background: i === 0 ? "var(--accent)" : "var(--ink)" }} /></span>
                <span className="demand-d mono">{c.n}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

window.InsightsView = InsightsView;
