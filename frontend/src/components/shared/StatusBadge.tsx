import { Badge } from "@/components/ui/badge"

interface StatusBadgeProps {
  status: "completed" | "running" | "failed" | "pending" | string
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const styles: Record<string, string> = {
    completed: "bg-green-100 text-green-700",
    running: "bg-blue-100 text-blue-700",
    failed: "bg-red-100 text-red-700",
    pending: "bg-yellow-100 text-yellow-700",
  }

  const labels: Record<string, string> = {
    completed: "已完成",
    running: "进行中",
    failed: "失败",
    pending: "待处理",
  }

  return (
    <Badge className={`${styles[status] || styles.pending} ${className || ""}`}>
      {labels[status] || status}
    </Badge>
  )
}
