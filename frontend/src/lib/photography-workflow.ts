import { Camera, FolderOpen, GraduationCap, MapPin, Paintbrush } from "lucide-react"

// Product order only; routes and handoff parameters stay unchanged.
export const photographyWorkflow = [
  { path: "/planning", label: "拍摄规划", title: "拍摄规划", icon: MapPin, color: "orange" as const,
    tags: "路线、机位、时段", description: "出发前明确拍摄目标，安排路线与拍摄时段。", step: "明确去哪拍、拍什么" },
  { path: "/assets", label: "素材库", title: "素材筛选", icon: FolderOpen, color: "green" as const,
    tags: "评分、分档、去重", description: "整理拍摄素材，筛选值得分析与保留的照片。", step: "从一批照片中挑选目标" },
  { path: "/analysis", label: "照片分析", title: "照片分析", icon: Camera, color: "blue" as const,
    tags: "后期建议、拍摄反馈", description: "了解曝光、色彩与构图问题，获得调整与学习建议。", step: "理解问题与优化方向" },
  { path: "/retouch", label: "修图", title: "修图调整", icon: Paintbrush, color: "blue" as const,
    tags: "预览、微调、导出", description: "带建议进入编辑，或直接选择照片调色与修图。", step: "预览微调并保存结果" },
  { path: "/learning", label: "学习复盘", title: "学习复盘", icon: GraduationCap, color: "purple" as const,
    tags: "反馈、练习、复盘", description: "查看 Coach 反馈与练习任务，为下一次拍摄做准备。", step: "把拍摄反馈变成练习" },
]
