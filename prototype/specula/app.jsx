// ============================================================
// SPECULA — app shell: sidebar nav, routing, tweaks
// ============================================================

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "mstyle": "bars",
  "layout": "rows",
  "density": "comfortable",
  "accent": "#2E7D4F",
  "font": "Spectral"
}/*EDITMODE-END*/;

const NAV = [
  { sec: "Pipeline" },
  { id: "jobs", label: "Jobs", icon: "jobs" },
  { id: "approvals", label: "Approval queue", icon: "approvals", alert: SPECULA.approvals.length },
  { id: "companies", label: "Companies", icon: "companies", count: SPECULA.companies.length },
  { sec: "Intelligence" },
  { id: "insights", label: "Insights", icon: "insights" },
  { sec: "Configure" },
  { id: "profiles", label: "Search profiles", icon: "profiles", count: SPECULA.lenses.length },
  { id: "targeting", label: "Targeting", icon: "targeting" },
];

function Sidebar({ view, setView, onRefresh, spinning, synced }) {
  const c = SPECULA.candidate;
  return (
    <aside className="side">
      <div className="side-top">
        <div className="side-brand">
          <span className="side-logo">Specula</span>
          <span className="side-tag">role ledger</span>
        </div>
        <div className="side-sync">
          <div className="sync-row"><span className="sync-dot" /> synced <b>{synced}</b> · <b>11</b> new</div>
          <button className={"refresh-btn" + (spinning ? " spinning" : "")} onClick={onRefresh}>
            <span className="rb-ico">↻</span> {spinning ? "Refreshing…" : "Refresh now"}
          </button>
        </div>
      </div>
      <nav className="nav">
        {NAV.map((n, i) => n.sec
          ? <div className="nav-sec" key={"s" + i}>{n.sec}</div>
          : (
            <button key={n.id} className={"nav-item" + (view === n.id ? " on" : "")} onClick={() => setView(n.id)}>
              <span className="nav-ico"><Icon name={n.icon} /></span>
              <span className="nav-label">{n.label}</span>
              {n.alert ? <span className="nav-count alert">{n.alert}</span> : n.count ? <span className="nav-count">{n.count}</span> : null}
            </button>
          ))}
      </nav>
      <div className="side-me">
        <button className={"me-card" + (view === "candidate" ? " on" : "")} onClick={() => setView("candidate")} style={view === "candidate" ? { background: "var(--panel-2)", borderColor: "var(--rule)" } : {}}>
          <span className="me-av">{c.initials}</span>
          <span><div className="me-name">{c.name}</div><div className="me-sub">{c.title}</div></span>
        </button>
      </div>
    </aside>
  );
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [view, setView] = useState("jobs");
  const [spinning, setSpinning] = useState(false);
  const [synced, setSynced] = useState("2d ago");
  const [intro, setIntro] = useState(() => { try { return !sessionStorage.getItem("specula_intro"); } catch (e) { return true; } });

  // apply tweaks to root
  useEffect(() => {
    const r = document.documentElement;
    r.style.setProperty("--accent", t.accent);
    r.style.setProperty("--accent-bg", `color-mix(in srgb, ${t.accent} 15%, var(--paper))`);
    r.style.setProperty("--accent-ink", `color-mix(in srgb, ${t.accent} 70%, #000)`);
    r.style.setProperty("--font-display", `'${t.font}', serif`);
    r.setAttribute("data-density", t.density === "compact" ? "compact" : "regular");
    r.setAttribute("data-layout", t.layout);
  }, [t.accent, t.font, t.density, t.layout]);

  const refresh = () => {
    if (spinning) return;
    setSpinning(true);
    setTimeout(() => { setSpinning(false); setSynced("just now"); }, 1400);
  };

  const views = {
    jobs: <JobsView tweaks={t} />,
    approvals: <ApprovalsView />,
    companies: <CompaniesView />,
    insights: <InsightsView />,
    profiles: <ProfilesView />,
    targeting: <TargetingView />,
    candidate: <CandidateView />,
  };

  return (
    <>
      {intro && <IntroOverlay onDone={() => { setIntro(false); try { sessionStorage.setItem("specula_intro", "1"); } catch (e) {} }} />}
      <div className="app">
        <Sidebar view={view} setView={setView} onRefresh={refresh} spinning={spinning} synced={synced} />
        <main className="main" key={view}>
          {views[view]}
        </main>

        <TweaksPanel>
          <TweakSection label="Signature" />
          <TweakRadio label="Match score" value={t.mstyle} options={["bars", "figure", "ring"]} onChange={(v) => setTweak("mstyle", v)} />
          <TweakRadio label="Job layout" value={t.layout} options={["rows", "cards"]} onChange={(v) => setTweak("layout", v)} />
          <TweakSection label="Type & color" />
          <TweakSelect label="Display font" value={t.font} options={["Spectral", "Newsreader", "Source Serif 4"]} onChange={(v) => setTweak("font", v)} />
          <TweakColor label="Accent" value={t.accent} options={["#2E7D4F", "#2D5BBF", "#9A7A18", "#7A4FB0"]} onChange={(v) => setTweak("accent", v)} />
          <TweakSection label="Density" />
          <TweakRadio label="Spacing" value={t.density} options={["comfortable", "compact"]} onChange={(v) => setTweak("density", v)} />
        </TweaksPanel>
      </div>
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
