import type { Metadata, Viewport } from "next";
import { Noto_Naskh_Arabic, Plus_Jakarta_Sans } from "next/font/google";
import { ServiceWorker } from "@/components/ServiceWorker";
import "./globals.css";

const sans = Plus_Jakarta_Sans({ variable: "--font-sans-latin", subsets: ["latin"], display: "swap" });
const urdu = Noto_Naskh_Arabic({ variable: "--font-urdu-face", subsets: ["arabic"], display: "swap" });

export const metadata: Metadata = {
  title: { default: "Bharosa · بھروسہ", template: "%s · Bharosa" },
  description: "Trusted assistance for public services. PROTOTYPE - simulated data.",
};

export const viewport: Viewport = {
  themeColor: "#0f766e",
  width: "device-width",
  initialScale: 1,
};

// Runs before first paint so there is no light flash for dark-mode users.
const THEME_SCRIPT = `try{var t=localStorage.getItem("bharosa.theme");if(t!=="light"&&t!=="dark"){t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}document.documentElement.dataset.theme=t;var l=localStorage.getItem("bharosa.lite");if(l!=="true"&&l!=="false"){var c=navigator.connection;l=(c&&(c.saveData===true||c.effectiveType==="slow-2g"||c.effectiveType==="2g"))?"true":"false"}document.documentElement.dataset.lite=l;var m=document.querySelector('meta[name="theme-color"]');if(m)m.setAttribute("content",t==="dark"?"#0b1513":"#0f766e")}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning className={`${sans.variable} ${urdu.variable} h-full antialiased`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col">
        {children}
        <ServiceWorker />
      </body>
    </html>
  );
}
