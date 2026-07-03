export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-[20px]">
      <label className="mb-[9px] block font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
        {label}
      </label>
      {children}
    </div>
  );
}
