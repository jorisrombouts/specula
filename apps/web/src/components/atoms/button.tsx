type Variant = "default" | "pri" | "accent" | "ghost";
const cls: Record<Variant, string> = {
  default: "border-rule-2 bg-card text-ink hover:border-ink",
  pri: "border-ink bg-ink text-paper hover:bg-black",
  accent: "border-accent bg-accent text-white",
  ghost:
    "border-transparent bg-transparent text-ink-2 hover:bg-panel hover:text-ink",
};
export function Button({
  variant = "default",
  className = "",
  ...props
}: { variant?: Variant } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`inline-flex items-center gap-[7px] rounded-[7px] border px-[14px] py-2 text-[12.5px] font-medium transition-colors ${cls[variant]} ${className}`}
      {...props}
    />
  );
}
