"use client";
import { useEffect } from "react";

/**
 * Run an async loader when `fn` changes (page load, filter change).
 * The call is deferred one microtask so the loader may set "loading" state without cascading renders,
 * and a stale run is ignored if the component unmounts or `fn` changes first.
 */
export function useLoader(fn: () => void | Promise<void>) {
  useEffect(() => {
    let live = true;
    queueMicrotask(() => {
      if (live) void fn();
    });
    return () => {
      live = false;
    };
  }, [fn]);
}
