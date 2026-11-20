import Link from "next/link";
import { Banner } from "./Banner";

export function PageShell({
  title,
  urdu,
  note,
}: {
  title: string;
  urdu: string;
  note: string;
}) {
  return (
    <>
      <Banner />
      <main className="mx-auto w-full max-w-xl flex-1 p-4">
        <Link href="/" className="text-sm underline">
          ← Home / ہوم
        </Link>
        <h1 className="mt-4 text-3xl font-bold">{title}</h1>
        <p dir="rtl" lang="ur" className="mt-1 text-2xl">
          {urdu}
        </p>
        <p className="mt-6 rounded border border-dashed p-4 text-sm opacity-80">{note}</p>
      </main>
    </>
  );
}
