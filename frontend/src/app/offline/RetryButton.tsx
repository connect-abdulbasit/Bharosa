"use client";
import { Button } from "@/components/ui";

export function RetryButton() {
  return <Button size="lg" icon="refresh" en="Try again" ur="دوبارہ کوشش کریں" onClick={() => window.location.reload()} />;
}
