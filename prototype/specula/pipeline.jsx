// ============================================================
// SPECULA — Pipeline views: Approval queue + Companies registry
// ============================================================

function ApprovalCard({ c, onDecide }) {
  const [gone, setGone] = useState(false);
  const [decision, setDecision] = useState(null);
  const decide = (d) => { setDecision(d); setGone(true); setTimeout(() => onDecide(c.id, d), 360); };
  return (
    <div className={"appr" + (gone ? " gone" : "")}>
      <div className="appr-top">
        <div className="appr-logo">{c.logo}</div>
        <div style={{ flex: 1 }}>
          <div className="appr-name">{c.name} <span style={{ fontSize: 13 }}>{c.flag}</span></div>
          <div className="appr-dom">{c.domain}</div>
        </div>
        <span className="chip chip-mono">{c.roles} open</span>
      </div>
      <p className="appr-why">{c.why}</p>
      <div className="appr-meta">
        <span className="ats">{c.ats}</span>
        {c.unverified
          ? <span className="tag-flag">⚐ HQ origin unverified</span>
          : <span className="chip chip-mono">HQ {c.hq}</span>}
      </div>
      <div className="appr-q">⌕ found via "{c.query}"</div>
      <div className="appr-acts">
        <button className="btn btn-accent" onClick={() => decide("approve")}>✓ Approve</button>
        <button className="btn" onClick={() => decide("reject")}>✕ Reject</button>
        <button className="btn snooze" onClick={() => decide("snooze")} title="Snooze">☾</button>
      </div>
    </div>
  );
}

function ApprovalsView() {
  const [queue, setQueue] = useState(SPECULA.approvals);
  const [log, setLog] = useState({ approved: 0, rejected: 0, snoozed: 0 });
  const decide = (id, d) => {
    setQueue((q) => q.filter((c) => c.id !== id));
    setLog((l) => ({ ...l, [d === "approve" ? "approved" : d === "reject" ? "rejected" : "snoozed"]: l[d === "approve" ? "approved" : d === "reject" ? "rejected" : "snoozed"] + 1 }));
  };
  return (
    <div className="view">
      <div className="vhead">
        <div className="vhead-l">
          <h1 className="vtitle">Approval queue</h1>
          <p className="vsub">Discovery surfaces candidate companies against your targeting. Approve once — on approval each is enriched (HQ country + confidence, rough comp) and added to the registry. Rejections suppress repeats.</p>
        </div>
        <div className="vhead-stat">
          <div><b>{queue.length}</b> <span className="mono"> pending</span></div>
          <span className="vstat-sep" />
          <div><b>{log.approved}</b> <span className="mono"> approved</span></div>
        </div>
      </div>
      {queue.length === 0
        ? <div className="empty"><div className="empty-ico">✓</div>Queue clear. {log.approved} approved, {log.rejected} rejected, {log.snoozed} snoozed this session — next discovery run is scheduled for Monday.</div>
        : <div className="appr-grid">{queue.map((c) => <ApprovalCard key={c.id} c={c} onDecide={decide} />)}</div>}
    </div>
  );
}

function CompaniesView() {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(Object.fromEntries(SPECULA.companies.map((c) => [c.name, true])));
  const rows = SPECULA.companies.filter((c) => c.name.toLowerCase().includes(q.toLowerCase()) || c.hq.toLowerCase().includes(q.toLowerCase()));
  const totalOpen = SPECULA.companies.reduce((s, c) => s + c.open, 0);
  return (
    <div className="view">
      <div className="vhead">
        <div className="vhead-l">
          <h1 className="vtitle">Companies</h1>
          <p className="vsub">Approved companies in the registry — ATS provider and feed, enriched HQ country with confidence, and a rough comp estimate (informational only). Global across every lens.</p>
        </div>
        <div className="vhead-stat">
          <div><b>{SPECULA.companies.length}</b> <span className="mono"> tracked</span></div>
          <span className="vstat-sep" />
          <div><b>{totalOpen}</b> <span className="mono"> open roles</span></div>
        </div>
      </div>
      <div className="toolbar">
        <input className="input" style={{ maxWidth: 280, padding: "8px 12px" }} placeholder="Filter by name or HQ country…" value={q} onChange={(e) => setQ(e.target.value)} />
        <span>{rows.length} of {SPECULA.companies.length}</span>
      </div>
      <table className="tbl">
        <thead>
          <tr><th>Company</th><th>ATS feed</th><th>HQ country</th><th>HQ confidence</th><th>Open</th><th>Comp est.</th><th>Tracking</th></tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.name}>
              <td>
                <div className="tbl-co">
                  <div className="tbl-logo">{c.logo}</div>
                  <div><div>{c.name}</div><div className="tbl-dom">{c.domain}</div></div>
                </div>
              </td>
              <td><span className="ats">{c.ats}</span></td>
              <td>{c.flag} {c.hq}</td>
              <td>
                <span className={"conf" + (c.conf < 80 ? " low" : "")}>
                  <span className="conf-track"><span style={{ width: c.conf + "%" }} /></span>
                  {c.conf}%{c.conf < 80 ? " ⚐" : ""}
                </span>
              </td>
              <td className="mono">{c.open}</td>
              <td><span className="chip chip-strong">{c.comp}</span></td>
              <td>
                <button className={"toggle" + (active[c.name] ? " on" : "")} onClick={() => setActive((a) => ({ ...a, [c.name]: !a[c.name] }))} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

Object.assign(window, { ApprovalsView, CompaniesView });
