// ============================================================
// SPECULA — Config views: Profiles (lenses), Candidate, Targeting
// ============================================================

function TagEditor({ tags, kind, onChange }) {
  const [adding, setAdding] = useState(false);
  const [val, setVal] = useState("");
  const add = () => { if (val.trim()) { onChange([...tags, val.trim()]); } setVal(""); setAdding(false); };
  return (
    <div className="taglist">
      {tags.map((t, i) => (
        <span className={"tagchip" + (kind ? " " + kind : "")} key={t + i}>
          {t}<span className="tagchip-x" onClick={() => onChange(tags.filter((_, n) => n !== i))}>✕</span>
        </span>
      ))}
      {adding
        ? <input autoFocus className="input" style={{ width: 140, padding: "5px 9px", fontSize: 12.5 }} value={val}
            onChange={(e) => setVal(e.target.value)} onBlur={add} onKeyDown={(e) => e.key === "Enter" && add()} />
        : <button className="tag-add" onClick={() => setAdding(true)}>+ add</button>}
    </div>
  );
}

function ProfilesView() {
  const [lenses, setLenses] = useState(SPECULA.lenses);
  const toggle = (id) => setLenses((ls) => ls.map((l) => l.id === id ? { ...l, active: !l.active } : l));
  const pool = SPECULA.jobs.filter((j) => j.status !== "Dismissed");
  const cnt = (id) => SPECULA.filterByLens(pool, id);
  return (
    <div className="view">
      <div className="vhead">
        <div className="vhead-l">
          <h1 className="vtitle">Search profiles</h1>
          <p className="vsub">Named lenses over one shared pool. Each <b>owns geography &amp; work mode entirely</b> — location scope, allowed modes, and HQ-origin rule — layered over your global targeting baseline. A role can match several at once; switching a lens re-scopes the Jobs view and re-scores it on location.</p>
        </div>
        <div className="vhead-stat">
          <div><b>{lenses.filter((l) => l.active).length}</b> <span className="mono"> active</span></div>
          <span className="vstat-sep" />
          <div><b>{lenses.length}</b> <span className="mono"> total</span></div>
        </div>
      </div>
      <div className="lens-cards">
        {lenses.filter((l) => l.id !== "all").map((l) => (
          <div className={"lcard" + (l.active ? "" : " off")} key={l.id}>
            <div className="lcard-top">
              <span className="lcard-name">{l.name}</span>
              <span className="lcard-badge">{cnt(l.id).length} roles · {cnt(l.id).filter((j) => j.isNew).length} new</span>
              <button className={"toggle" + (l.active ? " on" : "")} style={{ marginLeft: "auto" }} onClick={() => toggle(l.id)} />
            </div>
            <div className="lcard-rules">
              <div className="rule-item"><div className="rule-k">Location scope · hard</div><div className="rule-v">{l.scope}</div></div>
              <div className="rule-item"><div className="rule-k">Work mode · hard</div><div className="rule-v">{l.modes.join(" / ")}</div></div>
              <div className="rule-item"><div className="rule-k">Origin rule · hard</div><div className="rule-v">{l.origin}</div></div>
            </div>
            <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div className="rule-item"><div className="rule-k">Focus · soft signal</div><div className="rule-v" style={{ color: "var(--ink-2)" }}>{l.focus || "—"}</div></div>
              <div className="rule-item">
                <div className="rule-k">Discovery seeds · auto</div>
                <div className="seeds">{l.seeds.map((s) => <span className="seed" key={s}>{s}</span>)}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
      <button className="btn" style={{ marginTop: 16 }}>+ New profile</button>
    </div>
  );
}

function CandidateView() {
  const c = SPECULA.candidate;
  const [skills, setSkills] = useState(c.skills);
  return (
    <div className="view">
      <div className="vhead">
        <div className="vhead-l">
          <h1 className="vtitle">Candidate profile</h1>
          <p className="vsub">Who you are — fed to the model so every match reflects fit between you and the role. Kept explicit (a form, not a parsed CV) so you control exactly what you match against. Also powers skills-gap.</p>
        </div>
        <div className="vhead-stat">
          <div className="me-av" style={{ width: 40, height: 40 }}>{c.initials}</div>
        </div>
      </div>
      <div className="form-grid">
        <div>
          <div className="field">
            <label className="field-l">Headline</label>
            <input className="input" defaultValue={c.title} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field"><label className="field-l">Location</label><input className="input" defaultValue={c.location} /></div>
            <div className="field"><label className="field-l">Work mode</label><input className="input" defaultValue={c.workMode} /></div>
            <div className="field"><label className="field-l">Years experience</label><input className="input" defaultValue={c.years + " years"} /></div>
            <div className="field"><label className="field-l">Visa</label><input className="input" defaultValue={c.visa} /></div>
          </div>
          <div className="field">
            <label className="field-l">Skills · matched against required_skills</label>
            <TagEditor tags={skills} onChange={setSkills} />
          </div>
          <div className="field">
            <label className="field-l">Projects</label>
            {c.projects.map((p) => (
              <div className="tagchip" key={p.name} style={{ display: "block", marginBottom: 8, background: "var(--card)", borderColor: "var(--rule-2)" }}>
                <b>{p.name}</b> <span style={{ color: "var(--ink-2)" }}>— {p.note}</span>
              </div>
            ))}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <label className="field-l">Experience</label>
              {c.experience.map((e) => <div className="tagchip" key={e.org} style={{ display: "block", marginBottom: 8 }}><b>{e.role}</b> · {e.org} <span className="mono" style={{ color: "var(--ink-2)", fontSize: 11 }}>{e.period}</span></div>)}
            </div>
            <div className="field">
              <label className="field-l">Education & languages</label>
              <div className="tagchip" style={{ display: "block", marginBottom: 8 }}>{c.education}</div>
              <div className="taglist">{c.languages.map((l) => <span className="tagchip" key={l}>{l}</span>)}</div>
            </div>
          </div>
        </div>

        <div className="gap-panel">
          <div className="panel">
            <div className="panel-h"><span className="panel-t">Skills gap</span><span className="panel-s">vs target roles</span></div>
            <p className="appr-why" style={{ marginBottom: 6 }}>Most-demanded skills across your target roles that aren't on your profile:</p>
            {SPECULA.skillsGap.map((g) => (
              <div className="gap-item" key={g.skill}>
                <span className="gap-bar">{[40, 70, 55].map((h, i) => <i key={i} style={{ height: h + "%" }} />)}</span>
                <div><div className="gap-k">{g.skill}</div><div className="gap-c">{g.note}</div></div>
                <span className="gap-n">{g.roles}×</span>
              </div>
            ))}
            <button className="btn" style={{ width: "100%", justifyContent: "center", marginTop: 16 }}>✎ Draft a tailored CV bullet</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function TargetingView() {
  const t = SPECULA.targeting;
  const [titles, setTitles] = useState(t.roleTitles);
  const [must, setMust] = useState(t.mustHaves);
  const [avoid, setAvoid] = useState(t.avoid);
  return (
    <div className="view">
      <div className="vhead">
        <div className="vhead-l">
          <h1 className="vtitle">Targeting</h1>
          <p className="vsub">Your global baseline — <b>who you are and what you want</b>: role identity, seniority, and values. Shared across every lens; drives discovery and the role &amp; skill match factors. <b>Geography and work mode live in Search profiles</b>, not here.</p>
        </div>
      </div>
      <div style={{ marginTop: 24, maxWidth: 760 }}>
        <div className="field">
          <label className="field-l">Role titles · synonyms (the field uses many names)</label>
          <TagEditor tags={titles} kind="syn" onChange={setTitles} />
        </div>
        <div className="field">
          <label className="field-l">Seniority</label>
          <div className="taglist">{t.seniority.map((s) => <span className="tagchip" key={s}>{s}</span>)}</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
          <div className="field">
            <label className="field-l">Must-haves</label>
            <TagEditor tags={must} onChange={setMust} />
          </div>
          <div className="field">
            <label className="field-l">Avoid</label>
            <TagEditor tags={avoid} kind="avoid" onChange={setAvoid} />
          </div>
        </div>
        <div className="field">
          <label className="field-l">Free-text preferences · fed to the model as soft signal</label>
          <textarea className="textarea" rows="4" defaultValue={t.preferences} />
        </div>
        <div className="deadline-banner" style={{ background: "var(--accent-bg)", borderColor: "var(--accent)", color: "var(--accent-ink)" }}>
          ⓘ <span>No geography here, by design — location, work mode and HQ-origin rules belong to <b>Search profiles</b> (lenses), so one identity can be viewed through many regional searches. Salary is likewise never a rule or signal; it's shown only when an ad states it.</span>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ProfilesView, CandidateView, TargetingView });
