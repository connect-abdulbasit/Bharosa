/** The decision rule at a glance: 0 ... ask_more_min ... auto_handle_min ... 1 as three coloured zones. */
export function ThresholdBar({ askMore, autoHandle }: { askMore: number; autoHandle: number }) {
  const a = Math.max(0, Math.min(1, askMore)) * 100;
  const b = Math.max(a / 100, Math.min(1, autoHandle)) * 100;
  return (
    <div>
      <div className="flex h-10 w-full overflow-hidden rounded-2xl text-xs font-extrabold text-white" role="img" aria-label={`Send to human below ${a}%, ask for more from ${a}% to ${b}%, auto handle from ${b}%`}>
        <div className="flex items-center justify-center bg-bad-700" style={{ width: `${a}%` }}>{a >= 18 && "Send to human"}</div>
        <div className="flex items-center justify-center bg-saffron-500 text-on-accent" style={{ width: `${b - a}%` }}>{b - a >= 14 && "Ask more"}</div>
        <div className="flex items-center justify-center bg-ok-700" style={{ width: `${100 - b}%` }}>{100 - b >= 12 && "Auto"}</div>
      </div>
      <div className="relative mt-1 h-5 text-xs font-bold text-ink-soft">
        {a >= 8 && <span className="absolute left-0">0%</span>}
        <span className="absolute -translate-x-1/2" style={{ left: `${a}%` }}>{Math.round(a)}%</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${b}%` }}>{Math.round(b)}%</span>
        {b <= 84 && <span className="absolute right-0">100%</span>}
      </div>
    </div>
  );
}
