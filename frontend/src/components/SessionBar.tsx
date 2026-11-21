"use client";
import { useRouter } from "next/navigation";
import { logout, useSession } from "@/lib/auth";
import { Icon } from "./Icon";

/** Who is signed in + log out. Never wraps: the name chip appears from md, the log-out label from lg. */
export function SessionBar() {
  const session = useSession();
  const router = useRouter();
  if (!session) return null;
  const initial = session.name.trim().charAt(0).toUpperCase();
  return (
    <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
      <div className="hidden items-center gap-2 whitespace-nowrap rounded-full border border-line bg-surface py-1 pl-1 pr-4 md:flex">
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-teal-700 text-sm font-extrabold text-white">{initial}</span>
        <span className="flex flex-col leading-tight">
          <span className="max-w-[11rem] truncate text-sm font-bold">{session.name}</span>
          <span className="text-xs font-semibold capitalize text-saffron-600">{session.role}</span>
        </span>
      </div>
      <button
        type="button"
        aria-label="Log out"
        className="flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-full border border-line bg-surface px-3 text-sm font-bold text-ink-soft hover:border-bad-700 hover:text-bad-ink"
        onClick={() => {
          logout();
          router.replace("/login");
        }}
      >
        <Icon name="logout" size={20} />
        <span className="hidden lg:inline">
          Log out · <span dir="rtl" lang="ur">لاگ آؤٹ</span>
        </span>
      </button>
    </div>
  );
}
