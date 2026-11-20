"use client";
import { useRouter } from "next/navigation";
import { logout, useSession } from "@/lib/auth";

export function SessionBar() {
  const session = useSession();
  const router = useRouter();
  if (!session) return null;
  return (
    <div className="mt-1 flex items-center justify-between gap-2 text-sm">
      <span>
        {session.name} · <span className="font-semibold">{session.role}</span>
      </span>
      <button
        type="button"
        className="min-h-[44px] rounded-lg border px-3"
        onClick={() => {
          logout();
          router.replace("/login");
        }}
      >
        Log out · لاگ آؤٹ
      </button>
    </div>
  );
}
