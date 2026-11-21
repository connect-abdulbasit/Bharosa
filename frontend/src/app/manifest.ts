import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Bharosa · بھروسہ (prototype)",
    short_name: "Bharosa",
    description: "Trusted assistance for public services. PROTOTYPE - simulated data.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#fbf6ec",
    theme_color: "#0f766e",
    lang: "en",
    categories: ["government", "utilities"],
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Check a message", short_name: "Check", url: "/citizen/check" },
      { name: "Claim help", short_name: "Claim", url: "/citizen/claim" },
      { name: "Where is my claim?", short_name: "Status", url: "/citizen/status" },
    ],
  };
}
