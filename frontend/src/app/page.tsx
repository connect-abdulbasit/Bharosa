import Link from "next/link";
import { Banner } from "@/components/Banner";

export default function Home() {
  return (
    <>
      <Banner />
      <main className="mx-auto w-full max-w-xl flex-1 p-4">
        <h1 className="text-4xl font-bold">Bharosa</h1>
        <p dir="rtl" lang="ur" className="text-3xl">بھروسہ</p>
        <p className="mt-2 opacity-80">
          A trusted assistance layer between citizens and public services. Not an official service.
        </p>
        <ul className="mt-6 space-y-2">
          <li key="login"><Link className="block rounded border p-3 text-lg underline" href="/login">Login · لاگ ان</Link></li>
          <li key="citizen"><Link className="block rounded border p-3 text-lg underline" href="/citizen">My Bharosa · میرا بھروسہ</Link></li>
          <li key="citizen/check"><Link className="block rounded border p-3 text-lg underline" href="/citizen/check">Check a message · پیغام چیک کریں</Link></li>
          <li key="citizen/claim"><Link className="block rounded border p-3 text-lg underline" href="/citizen/claim">Make a claim · دعویٰ کریں</Link></li>
          <li key="citizen/data"><Link className="block rounded border p-3 text-lg underline" href="/citizen/data">My data & consent · میرا ڈیٹا اور رضامندی</Link></li>
          <li key="helper"><Link className="block rounded border p-3 text-lg underline" href="/helper">Helper Mode · مددگار موڈ</Link></li>
          <li key="officer"><Link className="block rounded border p-3 text-lg underline" href="/officer">Officer review queue · افسر کی قطار</Link></li>
          <li key="admin/rules"><Link className="block rounded border p-3 text-lg underline" href="/admin/rules">Rule editor · اصول ایڈیٹر</Link></li>
          <li key="admin/chaos"><Link className="block rounded border p-3 text-lg underline" href="/admin/chaos">Chaos Panel · افراتفری پینل</Link></li>
          <li key="auditor"><Link className="block rounded border p-3 text-lg underline" href="/auditor">Audit log · آڈٹ لاگ</Link></li>
          <li key="eval"><Link className="block rounded border p-3 text-lg underline" href="/eval">Evaluation · جائزہ</Link></li>
        </ul>
      </main>
    </>
  );
}
