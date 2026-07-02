export function Tag({
  variant,
  children,
}: {
  variant: "new" | "status" | "flag";
  children: React.ReactNode;
}) {
  if (variant === "new")
    return (
      <span className="font-mono inline-flex items-center gap-1 text-[9px] tracking-[0.06em] text-accent-ink before:h-[5px] before:w-[5px] before:rounded-full before:bg-accent before:content-['']">
        {children}
      </span>
    );
  if (variant === "flag")
    return (
      <span className="font-mono text-[10.5px] text-warn">{children}</span>
    );
  return (
    <span className="font-mono rounded-[3px] border border-ink-2 px-[7px] py-[2px] text-[9px] uppercase tracking-[0.05em] text-ink">
      {children}
    </span>
  );
}
