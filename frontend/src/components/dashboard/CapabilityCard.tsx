import { Card, CardContent } from "@/components/ui/card"
import { LucideIcon } from "lucide-react"
import Link from "next/link"

interface CapabilityCardProps {
  icon: LucideIcon
  title: string
  tags: string
  description: string
  color: "blue" | "green" | "orange" | "purple"
  href: string
}

const colorMap = {
  blue: {
    border: "border-blue-200",
    bg: "bg-blue-100",
    icon: "text-blue-600",
  },
  green: {
    border: "border-green-200",
    bg: "bg-green-100",
    icon: "text-green-600",
  },
  orange: {
    border: "border-orange-200",
    bg: "bg-orange-100",
    icon: "text-orange-600",
  },
  purple: {
    border: "border-purple-200",
    bg: "bg-purple-100",
    icon: "text-purple-600",
  },
}

export function CapabilityCard({ icon: Icon, title, tags, description, color, href }: CapabilityCardProps) {
  const colors = colorMap[color]

  return (
    <Link href={href} className="block h-full rounded-xl transition-shadow hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-500">
    <Card className={`${colors.border} h-full`}>
      <CardContent className="pt-6">
        <div className={`w-10 h-10 rounded-lg ${colors.bg} flex items-center justify-center mb-3`}>
          <Icon className={`w-5 h-5 ${colors.icon}`} />
        </div>
        <h3 className="font-semibold text-slate-900 mb-1">{title}</h3>
        <p className="text-sm text-slate-500 mb-2">{tags}</p>
        <p className="text-sm leading-6 text-slate-600">{description}</p>
      </CardContent>
    </Card>
    </Link>
  )
}
