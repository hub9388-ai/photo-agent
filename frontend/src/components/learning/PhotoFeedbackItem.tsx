import Link from "next/link"
import Image from "next/image"

export interface PhotoFeedback {
  id: string
  file: string
  source: string
  sourceJobId?: string
  thumbnailUrl?: string
  status: "pending_review" | "mastered" | string
  statusLabel: string
  comment: string
  suggestion: string
}

interface PhotoFeedbackItemProps {
  feedback: PhotoFeedback
  index: number
}

const gradients = [
  "from-[#F97316] via-[#60A5FA] to-[#0F172A]",
  "from-[#0EA5E9] via-[#1E293B] to-[#F97316]",
  "from-[#FED7AA] via-[#0F172A] to-[#94A3B8]",
]

export function PhotoFeedbackItem({ feedback, index }: PhotoFeedbackItemProps) {
  const statusClass =
    feedback.status === "mastered"
      ? "bg-[#DCFCE7] text-[#16A34A]"
      : "bg-[#FEF3C7] text-[#D97706]"

  return (
    <div className="flex h-[100px] items-center gap-[22px] rounded-lg border border-[#E2E8F0] bg-white px-2.5">
      <div className={`relative h-20 w-[114px] shrink-0 overflow-hidden rounded-md bg-gradient-to-br ${gradients[index % gradients.length]}`}>
        {feedback.thumbnailUrl && <Image src={feedback.thumbnailUrl} alt={feedback.file} fill unoptimized className="object-cover" />}
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex items-center gap-4">
          <p className="text-base font-extrabold text-[#0F172A]">{feedback.file}</p>
          <span className="rounded-[5px] bg-[#F1F5F9] px-2.5 py-1 text-xs text-[#64748B]">
            来源：{feedback.source}
          </span>
          <span className={`rounded-[5px] px-2.5 py-1 text-xs font-extrabold ${statusClass}`}>
            {feedback.statusLabel}
          </span>
          {feedback.sourceJobId ? (
            <Link
              href={`/analysis/${feedback.sourceJobId}`}
              className="ml-auto shrink-0 text-xs font-bold text-[#2563EB] hover:text-[#1D4ED8]"
              onClick={(event) => event.stopPropagation()}
            >
              查看分析记录 〉
            </Link>
          ) : (
            <span className="ml-auto shrink-0 text-xs text-[#94A3B8]">分析记录不可用</span>
          )}
        </div>
        <p className="truncate text-[13px] text-[#475569]">点评：{feedback.comment}</p>
        <p className="truncate text-[13px] font-bold text-[#16A34A]">
          后续拍摄建议：{feedback.suggestion}
        </p>
      </div>
    </div>
  )
}
