export function ViewShell({
  label,
  title,
  sub,
}: {
  label: string;
  title: string;
  sub: string;
}) {
  return (
    <section
      data-screen-label={label}
      className="mx-auto max-w-[1180px] px-[34px] pb-16 pt-[30px]"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            {title}
          </h1>
          <p className="max-w-[64ch] text-ink-2 text-[13.5px]">{sub}</p>
        </div>
      </header>
      <p className="font-mono mt-8 text-ink-3 text-[11px] uppercase tracking-[0.08em]">
        Arrives in M1
      </p>
    </section>
  );
}
