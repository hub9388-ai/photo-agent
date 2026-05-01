import { Card, CardContent } from "@/components/ui/card"
import { TrendingUp, LucideIcon } from "lucide-react"

interface StatsCardProps {
  icon: LucideIcon
  value: string
  label: string
  change: string
  iconColor: string
}

export function StatsCard({ icon: Icon, value, label, change, iconColor }: StatsCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-2 mb-2">
          <Icon className={`w-4 h-4 ${iconColor}`} />
          <span className="text-2xl font-bold text-slate-900">{value}</span>
        </div>
        <p className="text-sm text-slate-600">{label}</p>
        <p className="text-xs text-green-600 flex items-center gap-1 mt-1">
          <TrendingUp className="w-3 h-3" />
          {change}
        </p>
      </CardContent>
    </Card>
  )
}
