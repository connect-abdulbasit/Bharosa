import { Icon, type IconName } from "./Icon";

export type TimelineStep = {
  key: string;
  icon: IconName;
  en: string;
  ur: string;
  time?: string | null;
  state: "done" | "current" | "todo";
};

export function formatTime(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

/** Vertical timeline: icon, label (English + Urdu) and time per step. */
export function StatusTimeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol>
      {steps.map((s, i) => (
        <li key={s.key} className="flex gap-4" aria-current={s.state === "current" ? "step" : undefined}>
          <div className="flex flex-col items-center">
            <span
              className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full border-2 ${
                s.state === "done"
                  ? "border-ok-700 bg-ok-700 text-white"
                  : s.state === "current"
                    ? "border-saffron-500 bg-saffron-300 text-on-accent ring-4 ring-saffron-100"
                    : "border-line bg-cream-2 text-ink-soft opacity-70"
              }`}
            >
              <Icon name={s.state === "done" ? "check" : s.icon} size={28} />
            </span>
            {i < steps.length - 1 && <span className={`my-1 min-h-6 w-1 flex-1 rounded-full ${s.state === "done" ? "bg-ok-700" : "bg-line"}`} />}
          </div>
          <div className="pb-6 pt-1.5">
            <p className={`text-xl font-extrabold leading-tight ${s.state === "todo" ? "text-ink-soft" : "text-heading"}`}>{s.en}</p>
            <p dir="rtl" lang="ur" className={`text-left text-xl font-bold ${s.state === "todo" ? "text-ink-soft" : "text-saffron-600"}`}>{s.ur}</p>
            {s.time && <p className="text-sm text-ink-soft">{formatTime(s.time)}</p>}
            {s.state === "current" && (
              <p className="mt-1 inline-block rounded-full bg-saffron-300 px-3 py-0.5 text-sm font-extrabold text-on-accent">
                We are here · <span dir="rtl" lang="ur">ہم یہاں ہیں</span>
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
