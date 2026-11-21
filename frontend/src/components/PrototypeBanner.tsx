import { Icon } from "./Icon";

/** Required on every page: this is a prototype and all data is simulated. */
export function PrototypeBanner() {
  return (
    <div role="note" className="w-full bg-saffron-300 px-4 py-1.5 text-center text-[13px] font-bold text-on-accent">
      <span className="inline-flex items-center gap-2">
        <Icon name="flask" size={15} />
        PROTOTYPE - simulated data <span aria-hidden>·</span> <span dir="rtl" lang="ur">نمونہ - فرضی ڈیٹا</span>
      </span>
    </div>
  );
}
