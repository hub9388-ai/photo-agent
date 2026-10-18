"use client"

import { useSyncExternalStore } from "react"
import { controls, neutral, type Adjustments } from "./case"

export type Snapshot = { rounded: boolean; adjustments: Adjustments }
export type DemoState = {
  analyzed: boolean
  current: Snapshot
  undo: Snapshot[]
  saved: Snapshot | null
  practiced: boolean
  planned: boolean
}
const KEY = "photoai.public-demo.v1"
export const initialState: DemoState = {
  analyzed: false, current: { rounded: false, adjustments: neutral }, undo: [],
  saved: null, practiced: false, planned: false,
}
function snapshot(value: unknown): Snapshot | null {
  if (!value || typeof value !== "object") return null
  const v = value as Snapshot
  if (typeof v.rounded !== "boolean" || !v.adjustments) return null
  if (!controls.every(c => Number.isFinite(v.adjustments[c.key]) && v.adjustments[c.key] >= c.min && v.adjustments[c.key] <= c.max)) return null
  return { rounded: v.rounded, adjustments: { brightness: v.adjustments.brightness, contrast: v.adjustments.contrast, saturation: v.adjustments.saturation } }
}
export function restoreState(value: unknown): DemoState {
  if (!value || typeof value !== "object") return initialState
  const v = value as DemoState
  return {
    analyzed: v.analyzed === true, current: snapshot(v.current) ?? initialState.current,
    saved: snapshot(v.saved), undo: Array.isArray(v.undo) ? v.undo.map(snapshot).filter((s): s is Snapshot => s !== null).slice(-8) : [],
    practiced: v.practiced === true, planned: v.planned === true,
  }
}
const serverSnapshot = { state: initialState, ready: false, persistent: true }
let cached: typeof serverSnapshot | undefined
const listeners = new Set<() => void>()
function getSnapshot() {
  if (cached) return cached
  try { cached = { state: restoreState(JSON.parse(localStorage.getItem(KEY) ?? "null")), ready: true, persistent: true } }
  catch { cached = { state: initialState, ready: true, persistent: false } }
  return cached
}
function subscribe(listener: () => void) {
  listeners.add(listener)
  const onStorage = (event: StorageEvent) => {
    if (event.key === KEY || event.key === null) { cached = undefined; listener() }
  }
  window.addEventListener("storage", onStorage)
  return () => { listeners.delete(listener); window.removeEventListener("storage", onStorage) }
}
function setState(next: DemoState | ((previous: DemoState) => DemoState)) {
  const previous = getSnapshot()
  const state = typeof next === "function" ? next(previous.state) : next
  let persistent = previous.persistent
  try { localStorage.setItem(KEY, JSON.stringify(state)) }
  catch { persistent = false }
  cached = { state, ready: true, persistent }
  listeners.forEach(listener => listener())
}
export function useDemoState() {
  const { state, ready, persistent } = useSyncExternalStore(subscribe, getSnapshot, () => serverSnapshot)
  function apply(current: Snapshot) {
    setState(previous => ({ ...previous, current, undo: [...previous.undo, previous.current].slice(-8) }))
  }
  function undo() {
    setState(previous => previous.undo.length ? { ...previous, current: previous.undo[previous.undo.length - 1], undo: previous.undo.slice(0, -1) } : previous)
  }
  return { state, setState, ready, persistent, apply, undo, reset: () => setState(initialState) }
}
export type DemoSession = ReturnType<typeof useDemoState>
