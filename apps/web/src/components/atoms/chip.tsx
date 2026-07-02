export function Chip({
  children,
  mono = false,
}: {
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <span
      className={`rounded-[6px] border border-rule bg-paper px-[9px] py-[3px] text-ink-2 ${mono ? "font-mono text-[10.5px]" : "text-[11.5px]"}`}
    >
      {children}
    </span>
  );
}
