"use client";
import { useMemo, useSyncExternalStore } from "react";
import { mergeWorkspace, parseWorkspace, WORKSPACE_KEY, type WorkspacePreferences } from "./workspace-preferences";
let memory: string | null = null;
let storageUnavailable = false;
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("workspace-preferences", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("workspace-preferences", callback);
  };
}
function snapshot() {
  if (storageUnavailable) return memory;
  try { return window.localStorage.getItem(WORKSPACE_KEY); } catch { return memory; }
}
const serverSnapshot = () => null;
export function updateWorkspace(patch: Partial<WorkspacePreferences>) {
  memory = JSON.stringify(mergeWorkspace(snapshot(), patch));
  try { window.localStorage.setItem(WORKSPACE_KEY, memory); storageUnavailable = false; }
  catch { storageUnavailable = true; }
  window.dispatchEvent(new Event("workspace-preferences"));
}
export function useWorkspacePreferences() {
  const raw = useSyncExternalStore(subscribe, snapshot, serverSnapshot);
  const preferences = useMemo(() => parseWorkspace(raw), [raw]);
  return [preferences, updateWorkspace] as const;
}
