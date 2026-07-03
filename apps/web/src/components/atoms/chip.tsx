export function Chip({
  children,
  mono = false,
  strong = false,
}: {
  children: React.ReactNode;
  mono?: boolean;
  strong?: boolean;
}) {
  return (
    <span
      className={`rounded-[6px] border bg-paper px-[9px] py-[3px] ${
        strong ? "border-rule-2 text-ink" : "border-rule text-ink-2"
      } ${mono ? "font-mono text-[10.5px]" : "text-[11.5px]"}`}
    >
      {children}
    </span>
  );
}
