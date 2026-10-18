import type { PracticeRecoveryRecord } from "@/types/learning"
import { DEMO_MODE } from "@/lib/demo/config"

const RECOVERY_KEY = DEMO_MODE ? "photoai.demo.practiceRecovery.v2" : "photoai.learning.practiceRecovery.v1"
const MAX_RECOVERY_AGE_MS = 1000 * 60 * 60 * 24

export function loadPracticeRecovery(): PracticeRecoveryRecord | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(RECOVERY_KEY)
    if (!raw) return null
    const record = JSON.parse(raw) as PracticeRecoveryRecord
    const updatedAt = new Date(record.updatedAt).getTime()
    if (!Number.isFinite(updatedAt) || Date.now() - updatedAt > MAX_RECOVERY_AGE_MS) {
      clearPracticeRecovery()
      return null
    }
    return record
  } catch {
    return null
  }
}

export function savePracticeRecovery(record: PracticeRecoveryRecord) {
  if (typeof window === "undefined") return
  window.localStorage.setItem(
    RECOVERY_KEY,
    JSON.stringify({
      ...record,
      updatedAt: new Date().toISOString(),
    })
  )
}

export function clearPracticeRecovery() {
  if (typeof window === "undefined") return
  window.localStorage.removeItem(RECOVERY_KEY)
}
