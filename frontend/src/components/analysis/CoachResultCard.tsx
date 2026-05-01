import { Check, AlertCircle, MapPin, Star } from "lucide-react"
import { Badge } from "@/components/ui/badge"

export interface CoachSection {
  title: string
  icon: "check" | "alert" | "map" | "star"
  items: string[]
}

export interface CoachPracticeTask {
  title: string
  description: string
  isChallenge?: boolean
}

export interface CoachResultCardProps {
  sections: CoachSection[]
  practiceTask?: CoachPracticeTask
}

const iconMap = {
  check: Check,
  alert: AlertCircle,
  map: MapPin,
  star: Star,
}

const iconColorMap = {
  check: "text-green-500",
  alert: "text-orange-500",
  map: "text-blue-500",
  star: "text-purple-500",
}

export function CoachResultCard({ sections, practiceTask }: CoachResultCardProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {sections.map((section, index) => {
          const Icon = iconMap[section.icon]
          return (
            <div key={index} className="flex items-start gap-2">
              <Icon className={`w-4 h-4 ${iconColorMap[section.icon]} mt-0.5`} />
              <div>
                <p className="font-medium text-sm">{section.title}</p>
                <ul className="text-xs text-slate-500 mt-1 space-y-1">
                  {section.items.map((item, idx) => (
                    <li key={idx}>• {item}</li>
                  ))}
                </ul>
              </div>
            </div>
          )
        })}
      </div>

      {practiceTask && (
        <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Star className="w-4 h-4 text-purple-500" />
            <p className="font-medium text-sm">{practiceTask.title}</p>
            {practiceTask.isChallenge && (
              <Badge variant="outline" className="text-xs">挑战</Badge>
            )}
          </div>
          <p className="text-xs text-slate-600">{practiceTask.description}</p>
        </div>
      )}
    </div>
  )
}
