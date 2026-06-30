// ============================================================
// SPECULA — assembling intro (≈2s, skippable, once per session)
// ============================================================
function IntroOverlay({ onDone }) {
  const [leaving, setLeaving] = useState(false);
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finish = () => {
    setLeaving((was) => {
      if (!was) setTimeout(onDone, reduce ? 0 : 640);
      return true;
    });
  };
  useEffect(() => {
    const t = setTimeout(finish, reduce ? 250 : 2000);
    const onKey = () => finish();
    window.addEventListener("keydown", onKey);
    return () => { clearTimeout(t); window.removeEventListener("keydown", onKey); };
  }, []);
  const roles = useCountUp(47, !reduce, 1500);
  return (
    <div className={"intro" + (leaving ? " intro-leave" : "")} onClick={finish}>
      <div className="intro-inner">
        <div className="intro-mark">Specula</div>
        <div className="intro-rule" />
        <div className="intro-tag">personal role ledger</div>
        <div className="intro-lines">
          {[0, 1, 2, 3, 4].map((i) => <span key={i} style={{ animationDelay: (0.62 + i * 0.1) + "s" }} />)}
        </div>
        <div className="intro-stat">synced · <b>{roles}</b> roles tracked · <b>11</b> new this week</div>
      </div>
      <div className="intro-skip">click anywhere to enter</div>
    </div>
  );
}
window.IntroOverlay = IntroOverlay;
