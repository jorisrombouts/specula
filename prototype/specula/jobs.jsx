// ============================================================
// SPECULA — Jobs view + detail drawer (interactive core)
// ============================================================

const LIFECYCLE = ["Saved", "Applied", "Interviewing", "Offer"];
const DISMISS_REASONS = ["Too junior", "Wrong location", "Comp", "Stack mismatch", "Not my field"];

function candidateHas(skill) {
  const cs = SPECULA.candidate.skills.map((s) => s.toLowerCase());
  const t = skill.toLowerCase();
  return cs.some((c) => c === t || c.includes(t) || t.includes(c.split(" ")[0]));
}

function JobRow({ job, i, mstyle, onOpen, dismissing, replay, exit, style }) {
  const ref = useRef(null);
  const open = () => {
    if (exit) return;
    const root = ref.current;
    const rect = (el) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { left: r.left, top: r.top, width: r.width, height: r.height, fontSize: parseFloat(getComputedStyle(el).fontSize) };
    };
    onOpen(job, { title: rect(root.querySelector(".jtitle")), meter: rect(root.querySelector(".meter")) });
  };
  return (
    <article ref={ref} data-fid={job.id} className={"jrow" + (dismissing ? " dismissing" : "") + (exit ? " jrow-exit" : "")}
      style={exit ? style : { animationDelay: (i * 45) + "ms" }}
      onClick={open}>
      <div className="jidx">{String(i + 1).padStart(2, "0")}</div>
      <div className="jbody">
        <div className="jline1">
          <h3 className="jtitle">{job.title}</h3>
          {job.isNew && <span className="tag-new">NEW</span>}
          {job.status && job.status !== "Dismissed" && <span className="tag-status">{job.status}</span>}
        </div>
        <div className="jline2">
          <span className="jco"><span className="jco-logo">{job.logo}</span>{job.company}</span>
          <span className="jsep">/</span><span className="jfact">{job.flag} {job.city}</span>
          {!job.city.includes("Remote") && <><span className="jsep">/</span><span className="jfact">{job.mode}</span></>}
          <span className="jsep">/</span><span className="jfact">{job.seniority}</span>
          {job.salary && <><span className="jsep">/</span><span className="jsal">{job.salary}</span></>}
        </div>
        <p className="jrat">{job.rationale}</p>
        <div className="jline3">
          <OverlapBar overlap={job.overlap} />
          <span className="jstack">{job.stack.slice(0, 5).join(" · ")}</span>
          <span className={"jdl" + (job.deadlineDays <= 7 ? " soon" : "")}>↳ closes {job.deadlineDays}d</span>
          {job.redFlag && <span className="tag-flag">⚑ {job.redFlag}</span>}
          {!job.originVerified && <span className="tag-flag">⚐ origin unverified</span>}
        </div>
      </div>
      <MatchMeter job={job} mstyle={mstyle} replay={replay} countUp={!exit} />
    </article>
  );
}

function InsightRecord({ job }) {
  const lowConf = job.confidence < 75;
  const rows = [
    ["role family", job.title.split("—")[0].trim()],
    ["seniority", job.seniority],
    ["experience", "3–6 yrs (inferred)"],
    ["education", job.edu],
    ["work mode", job.mode],
    ["location", `${job.flag} ${job.city}`],
    ["geo", job.geo],
    ["visa", job.visa],
    ["languages", job.langs.join(", ")],
    ["salary", job.salary || "not stated in ad"],
    ["contract", job.contract],
    ["deadline", `in ${job.deadlineDays} days`],
    ["posted", job.posted],
    ["still open", job.stillOpen ? "likely open" : "likely closed"],
  ];
  return (
    <dl className="kv">
      {rows.map(([k, v]) => (
        <React.Fragment key={k}><dt>{k}</dt><dd>{v}</dd></React.Fragment>
      ))}
      <dt>extraction</dt>
      <dd className={lowConf ? "lowconf" : ""}>{job.confidence}% confidence{lowConf ? " — surfaced, not trusted" : ""}</dd>
    </dl>
  );
}

function Lifecycle({ status, onSet, note, onNote }) {
  const idx = LIFECYCLE.indexOf(status);
  return (
    <div>
      <div className="life">
        {LIFECYCLE.map((s, n) => (
          <button key={s} className={"life-step" + (n < idx ? " done" : n === idx ? " active" : "")} onClick={() => onSet(s)}>
            <span className="life-dot">{n <= idx ? "✓" : ""}</span>
            <span className="life-lab">{s}</span>
          </button>
        ))}
      </div>
      <textarea className="life-note" rows="2" placeholder="Add a note (e.g. referred by Anna, recruiter call Tue)…" value={note} onChange={(e) => onNote(e.target.value)} />
    </div>
  );
}

function Feedback({ onLike, onDismiss }) {
  const [state, setState] = useState(null); // null | 'yes' | 'no'
  const [reason, setReason] = useState(null);
  return (
    <div>
      <div className="fb-row">
        <button className={"fb-btn yes" + (state === "yes" ? " on" : "")} onClick={() => { setState("yes"); onLike(); }}>
          ↑ Good match
        </button>
        <button className={"fb-btn no" + (state === "no" ? " on" : "")} onClick={() => setState("no")}>
          ↓ Not for me
        </button>
      </div>
      {state === "no" && (
        <div className="reasons fade-up">
          {DISMISS_REASONS.map((r) => (
            <button key={r} className={"reason" + (reason === r ? " on" : "")} onClick={() => { setReason(r); setTimeout(() => onDismiss(r), 380); }}>{r}</button>
          ))}
        </div>
      )}
      {state === "yes" && <p className="appr-why fade-up" style={{ marginTop: 12, color: "var(--accent-ink)" }}>Logged as a positive example — recent likes steer your scoring toward this kind of role.</p>}
    </div>
  );
}

function Drawer({ job, morphFrom, onClose, onStatus, onDismiss, onLike }) {
  const [note, setNote] = useState(job.appNote || "");
  const [closing, setClosing] = useState(false);
  const panelRef = useRef(null);
  const scrimRef = useRef(null);
  const titleRef = useRef(null);
  const meterRef = useRef(null);
  const reduce = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Shared-element morph: the clicked row's title + meter fly into the drawer
  // header, so the row and the drawer read as one continuous object.
  useLayoutEffect(() => {
    const panel = panelRef.current, scrim = scrimRef.current;
    if (!panel) return;
    if (scrim) scrim.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300, easing: "ease" });
    if (reduce) return;

    if (morphFrom) {
      panel.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 240, easing: "ease" });
      const morph = (el, src, useFont, delay) => {
        if (!el || !src) return;
        const d = el.getBoundingClientRect();
        const dx = src.left - d.left, dy = src.top - d.top;
        let s = useFont ? src.fontSize / parseFloat(getComputedStyle(el).fontSize) : src.width / d.width;
        s = Math.max(0.3, Math.min(s, 1.4));
        el.animate(
          [{ transform: `translate(${dx}px, ${dy}px) scale(${s})`, opacity: 0.55 }, { transform: "none", opacity: 1 }],
          { duration: 540, delay, easing: "cubic-bezier(.4,0,.12,1)", fill: "backwards" }
        );
      };
      morph(titleRef.current, morphFrom.title, true, 0);
      morph(meterRef.current, morphFrom.meter, false, 40);
      // supporting content rises in, skipping the morphing meter's section
      const rest = [...panel.querySelectorAll(".dr-head .dr-kicker, .dr-head .dr-sub"),
        ...[...panel.querySelectorAll(".dr-body > .dr-sec")].slice(1),
        panel.querySelector(".dr-body > div:last-child")].filter(Boolean);
      rest.forEach((el, n) => el.animate(
        [{ opacity: 0, transform: "translateY(12px)" }, { opacity: 1, transform: "none" }],
        { duration: 420, delay: 120 + n * 38, easing: "cubic-bezier(.2,.7,.2,1)", fill: "backwards" }));
    } else {
      panel.animate([{ transform: "translateX(100%)" }, { transform: "none" }],
        { duration: 440, easing: "cubic-bezier(.3,.9,.3,1)" });
    }
  }, []);

  const handleClose = () => {
    if (closing) return;
    const panel = panelRef.current, scrim = scrimRef.current;
    if (reduce || !panel) { onClose(); return; }
    setClosing(true);
    if (scrim) scrim.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 260, easing: "ease", fill: "forwards" });
    const a = panel.animate([{ transform: "none", opacity: 1 }, { transform: "translateX(46px)", opacity: 0 }],
      { duration: 300, easing: "cubic-bezier(.4,0,.7,1)", fill: "forwards" });
    let done = false;
    const finish = () => { if (!done) { done = true; onClose(); } };
    a.onfinish = finish;
    setTimeout(finish, 360);
  };

  if (!job) return null;
  const required = job.stack;
  const have = required.filter(candidateHas);
  const miss = required.filter((s) => !candidateHas(s));
  return (
    <>
      <div className="scrim show" ref={scrimRef} onClick={handleClose} />
      <aside className="drawer show" ref={panelRef}>
        <div className="dr-head">
          <button className="dr-close" onClick={handleClose}>✕</button>
          <div className="dr-kicker">
            <span className="jco-logo">{job.logo}</span>{job.company}
            <span className="jsep">/</span>{job.flag} {job.city} · {job.mode}
            {job.isNew && <span className="tag-new" style={{ marginLeft: 4 }}>NEW</span>}
          </div>
          <h2 className="dr-title" ref={titleRef} style={{ transformOrigin: "left top" }}>{job.title}</h2>
          <div className="dr-sub">
            <span>{job.seniority}</span><span className="jsep">·</span>
            <span>{job.contract}</span><span className="jsep">·</span>
            <span className="mono">posted {job.posted}</span>
          </div>
        </div>
        <div className="dr-body">
          <div className="dr-sec">
            <div style={{ display: "flex", gap: 22, alignItems: "flex-start", marginBottom: 16 }}>
              <div ref={meterRef} style={{ transformOrigin: "left top" }}>
                <MatchMeter job={job} mstyle="bars" reveal={!morphFrom} replay={job.id} />
              </div>
            </div>
            <p className="jrat" style={{ maxWidth: "none", fontSize: 13.5 }}>{job.rationale}</p>
            <div className="jline3" style={{ marginTop: 4 }}>
              <OverlapBar overlap={job.overlap} />
              <span className={"jdl" + (job.deadlineDays <= 7 ? " soon" : "")}>↳ closes in {job.deadlineDays} days</span>
            </div>
          </div>

          <div className="dr-sec">
            <div className="dr-sec-h">summary</div>
            <p className="dr-summary">{job.summary}</p>
          </div>

          <div className="dr-sec">
            <div className="dr-sec-h">skills · required vs your profile <span>{job.overlap[0]} of {job.overlap[1]} matched</span></div>
            <div className="skillgap">
              {have.map((s) => <span className="sg have" key={s}><span className="sg-ico">✓</span>{s}</span>)}
              {miss.map((s) => <span className="sg miss" key={s}><span className="sg-ico">+</span>{s}</span>)}
            </div>
            {miss.length > 0 && <p className="appr-why" style={{ marginTop: 12 }}>Gaps highlighted in amber feed your <b>skills-gap</b> view — add them to your profile or use them to tailor a CV bullet.</p>}
          </div>

          <div className="dr-sec">
            <div className="dr-sec-h">insight record <span>extracted · cached</span></div>
            <InsightRecord job={job} />
          </div>

          <div className="dr-sec">
            <div className="dr-sec-h">responsibilities</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5, lineHeight: 1.7, color: "var(--ink)" }}>
              {job.responsibilities.map((r) => <li key={r}>{r}</li>)}
            </ul>
          </div>

          <div className="dr-sec">
            <div className="dr-sec-h">application status</div>
            <Lifecycle status={job.status && job.status !== "Dismissed" ? job.status : null} onSet={(s) => onStatus(job.id, s)} note={note} onNote={setNote} />
          </div>

          <div className="dr-sec">
            <div className="dr-sec-h">feedback <span>steers your recommender</span></div>
            <Feedback onLike={() => onLike(job.id)} onDismiss={(r) => onDismiss(job.id, r)} />
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <button className="btn btn-pri" style={{ flex: 1, justifyContent: "center" }}>↗ Open posting</button>
            <button className="btn" onClick={() => onStatus(job.id, "Saved")}>★ Save</button>
          </div>
        </div>
      </aside>
    </>
  );
}

function JobsView({ tweaks }) {
  const [lens, setLens] = useState("all");
  const [sort, setSort] = useState("match");
  const [overrides, setOverrides] = useState({}); // id -> {status, dismissed, note}
  const [selected, setSelected] = useState(null);
  const [morphFrom, setMorphFrom] = useState(null);
  const openJob = (job, rects) => { setSelected(job); setMorphFrom(rects || null); };
  const [dismissingId, setDismissingId] = useState(null);
  const [exiting, setExiting] = useState([]);
  const listRef = useRef(null);
  const flip = useRef({ pos: new Map(), jobs: new Map(), init: false });

  const apply = (job) => ({ ...job, ...(overrides[job.id] || {}) });
  const pool = SPECULA.jobs.map(apply).filter((j) => !j.dismissed && j.status !== "Dismissed");
  let list = SPECULA.filterByLens(pool, lens).map((j) => ({ ...j, ...SPECULA.scoreForLens(j, lens) }));
  list = list.slice().sort((a, b) => sort === "match" ? b.match - a.match : sort === "deadline" ? a.deadlineDays - b.deadlineDays : (b.isNew ? 1 : 0) - (a.isNew ? 1 : 0));

  const lensCounts = (id) => SPECULA.filterByLens(pool, id);

  const setStatus = (id, status) => {
    setOverrides((o) => ({ ...o, [id]: { ...(o[id] || {}), status } }));
    setSelected((s) => s && s.id === id ? { ...s, status } : s);
  };
  const dismiss = (id, reason) => {
    setSelected(null);
    setMorphFrom(null);
    setDismissingId(id);
    setTimeout(() => {
      setOverrides((o) => ({ ...o, [id]: { ...(o[id] || {}), dismissed: true, reason } }));
      setDismissingId(null);
    }, 430);
  };
  const like = (id) => setStatus(id, "Saved");

  const closingSoon = list.filter((j) => j.deadlineDays <= 7 && j.status !== "Applied").length;
  const sig = lens + "|" + sort;

  // FLIP: when the lens/sort changes, fly surviving rows to their new ranked
  // positions, fade out the ones that leave, and re-sweep every match meter.
  useLayoutEffect(() => {
    const cont = listRef.current;
    if (!cont) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const rows = [...cont.querySelectorAll(".jrow[data-fid]:not(.jrow-exit)")];
    const newPos = new Map();
    rows.forEach((n) => newPos.set(n.dataset.fid, { top: n.offsetTop, left: n.offsetLeft, width: n.offsetWidth }));
    const newJobs = new Map(list.map((j) => [j.id, j]));
    if (flip.current.init && !reduce) {
      rows.forEach((n) => {
        const p = flip.current.pos.get(n.dataset.fid);
        const q = newPos.get(n.dataset.fid);
        if (p && (p.top !== q.top || p.left !== q.left)) {
          n.animate(
            [{ transform: `translate(${p.left - q.left}px, ${p.top - q.top}px)` }, { transform: "none" }],
            { duration: 560, easing: "cubic-bezier(.3,.9,.3,1)" }
          );
        }
      });
      const exits = [];
      flip.current.pos.forEach((p, id) => {
        if (!newPos.has(id)) { const j = flip.current.jobs.get(id); if (j) exits.push({ job: j, ...p }); }
      });
      if (exits.length) { setExiting(exits); setTimeout(() => setExiting([]), 480); }
    }
    flip.current.pos = newPos;
    flip.current.jobs = newJobs;
    flip.current.init = true;
  }, [sig]);

  return (
    <div className="view">
      <div className="vhead">
        <div className="vhead-l">
          <h1 className="vtitle">Jobs</h1>
          <p className="vsub">One shared, deduped pool. Role &amp; skill fit are scored against your targeting and candidate profile; the <b>location factor re-scores per lens</b>, so switching a lens genuinely re-ranks the pool — not just filters it.</p>
        </div>
        <div className="vhead-stat">
          <div><b>{pool.length}</b> <span className="mono"> in pool</span></div>
          <span className="vstat-sep" />
          <div><b>{pool.filter((j) => j.isNew).length}</b> <span className="mono"> new</span></div>
        </div>
      </div>

      <div className="lens-bar">
        {SPECULA.lenses.map((l) => {
          const c = lensCounts(l.id);
          const nw = c.filter((j) => j.isNew).length;
          return (
            <button key={l.id} className={"lens" + (lens === l.id ? " on" : "")} onClick={() => setLens(l.id)}>
              <span className="lens-name">{l.short}{nw > 0 && <span className="lens-newdot" />}</span>
              <span className="lens-meta">{c.length} roles · {nw} new</span>
            </button>
          );
        })}
      </div>

      {closingSoon > 0 && (
        <div className="deadline-banner">
          ⏱ <span><b>{closingSoon} {closingSoon === 1 ? "role" : "roles"}</b> in this lens close within 7 days — review before they disappear from the feed.</span>
        </div>
      )}

      <div className="toolbar">
        <div className="toolbar-l">
          <span className="lens-focus">{SPECULA.lenses.find((l) => l.id === lens).scope}</span>
          <span>· {SPECULA.lenses.find((l) => l.id === lens).modes.join(" / ")}</span>
          <span>· {SPECULA.lenses.find((l) => l.id === lens).origin}</span>
          {lens !== "all" && <span style={{ color: "var(--accent-ink)" }}>· ◉ match re-scored for this lens</span>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <span>sort</span>
          <select className="sortsel" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="match">match index ↓</option>
            <option value="deadline">deadline ↑</option>
            <option value="new">newest</option>
          </select>
        </div>
      </div>

      <div className="colhead">
        <span>#</span><span>role / source / facts</span><span>match · role / skill / loc</span>
      </div>

      <div className="jlist" ref={listRef}>
        {list.length === 0 && <div className="empty"><div className="empty-ico">⬚</div>No roles in this lens yet. Discovery runs weekly — or trigger a refresh.</div>}
        {list.map((j, i) => (
          <JobRow key={j.id} job={j} i={i} mstyle={tweaks.mstyle} onOpen={openJob} dismissing={dismissingId === j.id} replay={sig} />
        ))}
        {exiting.map((e) => (
          <JobRow key={"x" + e.job.id} job={e.job} i={0} mstyle={tweaks.mstyle} replay={sig} exit
            style={{ position: "absolute", top: e.top, left: e.left, width: e.width }} />
        ))}
      </div>

      {selected && <Drawer job={selected} morphFrom={morphFrom} onClose={() => { setSelected(null); setMorphFrom(null); }} onStatus={setStatus} onDismiss={dismiss} onLike={like} />}
    </div>
  );
}

window.JobsView = JobsView;
