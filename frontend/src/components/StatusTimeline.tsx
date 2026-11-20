export type TimelineStep = {
  key: string;
  icon: string;
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
    <ol className="space-y-0">
      {steps.map((s, i) => (
        <li key={s.key} className="flex gap-4" aria-current={s.state === "current" ? "step" : undefined}>
          <div className="flex flex-col items-center">
            <span
              aria-hidden
              className={`flex h-14 w-14 items-center justify-center rounded-full border-2 text-3xl ${
                s.state === "done"
                  ? "border-green-900 bg-green-100"
                  : s.state === "current"
                    ? "border-teal-900 bg-teal-200 ring-4 ring-teal-300"
                    : "border-gray-400 bg-gray-100 opacity-60"
              }`}
            >
              {s.state === "done" ? "✅" : s.icon}
            </span>
            {i < steps.length - 1 && <span className={`my-1 w-1 flex-1 min-h-6 ${s.state === "done" ? "bg-green-700" : "bg-gray-300"}`} />}
          </div>
          <div className="pb-6 pt-2">
            <p className={`text-xl font-bold ${s.state === "todo" ? "opacity-60" : ""}`}>{s.en}</p>
            <p dir="rtl" lang="ur" className={`text-xl ${s.state === "todo" ? "opacity-60" : ""}`}>{s.ur}</p>
            {s.time && <p className="text-sm opacity-70">{formatTime(s.time)}</p>}
            {s.state === "current" && <p className="text-sm font-semibold text-teal-800">We are here · ہم یہاں ہیں</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
