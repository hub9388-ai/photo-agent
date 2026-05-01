import { Badge } from "@/components/ui/badge"

interface GradeBadgeProps {
  grade: "A" | "B" | "C" | "rejected" | "duplicate" | string
  className?: string
}

export function GradeBadge({ grade, className }: GradeBadgeProps) {
  const styles: Record<string, string> = {
    A: "bg-green-100 text-green-700 border-green-300",
    B: "bg-blue-100 text-blue-700 border-blue-300",
    C: "bg-orange-100 text-orange-700 border-orange-300",
    rejected: "bg-red-100 text-red-700 border-red-300",
    duplicate: "bg-purple-100 text-purple-700 border-purple-300",
  }

  const labels: Record<string, string> = {
    A: "A档",
    B: "B档",
    C: "C档",
    rejected: "淘汰",
    duplicate: "重复",
  }

  return (
    <Badge variant="outline" className={`${styles[grade] || styles.C} ${className || ""}`}>
      {labels[grade] || grade}
    </Badge>
  )
}
