"use client";
import { useSyncExternalStore } from "react";
import { Icon } from "./Icon";

function subscribe(cb: () => void) {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}

/** Weak-signal honesty: say so when the phone is offline, and that saved work is safe. */
export function OnlineBadge() {
  const online = useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
  if (online) return null;
  return (
    <div role="status" className="flex items-center justify-center gap-2 bg-bad-700 px-4 py-1.5 text-center text-sm font-bold text-white">
      <Icon name="wifiOff" size={16} />
      No signal: your answers are saved on this phone. · <span dir="rtl" lang="ur">سگنل نہیں: آپ کے جوابات فون پر محفوظ ہیں</span>
    </div>
  );
}
