import { ClipboardList } from "lucide-react"
import { PhotoFeedbackItem, type PhotoFeedback } from "./PhotoFeedbackItem"

interface PhotoFeedbackListProps {
  feedbacks: PhotoFeedback[]
}

export function PhotoFeedbackList({ feedbacks }: PhotoFeedbackListProps) {
  return (
    <div className="flex-1 space-y-3.5 rounded-[10px] border border-[#E2E8F0] bg-white p-[18px]">
      <div className="flex items-center gap-2.5">
        <ClipboardList className="w-5 h-5 text-[#0F172A]" />
        <h2 className="text-lg font-extrabold text-[#0F172A]">近期照片评估</h2>
      </div>
      <div className="max-h-[324px] space-y-2.5 overflow-y-auto pr-1">
        {feedbacks.map((feedback, index) => (
          <PhotoFeedbackItem key={feedback.id} feedback={feedback} index={index} />
        ))}
      </div>
    </div>
  )
}
