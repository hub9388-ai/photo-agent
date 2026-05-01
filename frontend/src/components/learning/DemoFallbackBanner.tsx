import { Info } from "lucide-react"

interface DemoFallbackBannerProps {
  message: string
  actionLabel?: string
  onAction?: () => void
}

export function DemoFallbackBanner({ message, actionLabel, onAction }: DemoFallbackBannerProps) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      <div className="flex items-center gap-2">
        <Info className="h-4 w-4 shrink-0" />
        <span className="font-medium">{message}</span>
      </div>
      {actionLabel && onAction ? (
        <button
          type="button"
          onClick={onAction}
          className="shrink-0 rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-bold text-amber-800 hover:bg-amber-100"
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  )
}
