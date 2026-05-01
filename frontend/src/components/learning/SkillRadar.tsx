import { BadgeCheck, Sun, ScanLine, Palette, WandSparkles, ChevronRight } from "lucide-react"

interface Skill {
  name: string
  score: number
  color: string
  icon?: string
}

interface SkillRadarProps {
  skills: Skill[]
  sourceNote?: string
}

const iconMap: Record<string, React.ReactNode> = {
  sun: <Sun className="w-[19px] h-[19px] text-[#475569]" />,
  "scan-line": <ScanLine className="w-[19px] h-[19px] text-[#475569]" />,
  palette: <Palette className="w-[19px] h-[19px] text-[#475569]" />,
  "wand-sparkles": <WandSparkles className="w-[19px] h-[19px] text-[#475569]" />,
}

const colorMap: Record<string, string> = {
  blue: "bg-[#2563EB]",
  orange: "bg-[#F97316]",
  green: "bg-[#22C55E]",
  purple: "bg-[#A855F7]",
}

export function SkillRadar({ skills, sourceNote = "基于 Coach 历史反馈估算，非完整能力测评。" }: SkillRadarProps) {
  return (
    <div className="rounded-[10px] border border-[#E2E8F0] bg-white p-[22px] space-y-[18px] flex-1">
      <div className="flex items-center gap-2.5">
        <BadgeCheck className="w-5 h-5 text-[#0F172A]" />
        <h2 className="text-lg font-extrabold text-[#0F172A]">技能雷达 / 技能画像</h2>
      </div>
      <div className="space-y-1">
        <p className="text-sm text-[#64748B]">能力评分由历史反馈自动归纳</p>
        <p className="text-xs text-[#94A3B8]">{sourceNote}</p>
      </div>

      <div className="space-y-4">
        {skills.map((skill) => (
          <div key={skill.name} className="flex items-center gap-3.5">
            {iconMap[skill.icon || ""] || (
              <div className="w-[19px] h-[19px]" />
            )}
            <span className="text-[15px] text-[#334155] w-20">{skill.name}</span>
            <div className="flex-1 h-[7px] rounded bg-[#E2E8F0] overflow-hidden">
              <div
                className={`h-full rounded ${colorMap[skill.color] || "bg-[#2563EB]"}`}
                style={{ width: `${skill.score}%` }}
              />
            </div>
            <span className="text-sm text-[#64748B] w-10 text-right">{skill.score}%</span>
          </div>
        ))}
      </div>

      <div className="h-px bg-[#E2E8F0]" />

      <div className="text-center">
        <span className="text-sm text-[#475569] cursor-pointer hover:text-[#0F172A] transition-colors">
          查看能力解析与提升建议 <ChevronRight className="w-4 h-4 inline" />
        </span>
      </div>
    </div>
  )
}

export type { Skill }
