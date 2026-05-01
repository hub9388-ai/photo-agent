interface TimelineSpot {
  time: string
  title: string
  description: string
  position: string
  lighting: string
  method: string
}

interface PlanTimelineProps {
  spots: TimelineSpot[]
}

const gradients = [
  "from-orange-400 via-yellow-200 to-slate-700",
  "from-blue-200 via-amber-500 to-green-800",
  "from-blue-100 via-slate-500 to-slate-900",
]

export function PlanTimeline({ spots }: PlanTimelineProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-[#CBD5E1] bg-white">
      {spots.map((spot, index) => (
        <div key={`${spot.time}-${spot.title}-${index}`}>
          <div className="flex items-stretch px-3 py-3">
            <div className="mr-4 flex w-5 shrink-0 flex-col items-center">
              <div className="z-10 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full bg-[#2563EB] text-xs font-extrabold text-white">
                {index + 1}
              </div>
              {index < spots.length - 1 && (
                <div className="my-0.5 w-px flex-1 bg-[#93C5FD]" />
              )}
            </div>

            <div className="min-w-0 flex-1 py-1">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="text-base font-extrabold text-[#0F172A]">
                    {spot.time}
                  </p>
                  <p className="text-base font-extrabold text-[#0F172A]">
                    {spot.title}
                  </p>
                  <p className="text-[13px] text-[#64748B]">
                    {spot.description}
                  </p>
                  <div className="mt-2 space-y-1.5 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-[#64748B]">
                    <p className="break-words">
                      <span className="font-bold text-[#334155]">机位：</span>
                      {spot.position || "现场确认安全站位与前景关系。"}
                    </p>
                    <p className="break-words">
                      <span className="font-bold text-[#334155]">光线：</span>
                      {spot.lighting || "根据现场云量、太阳方向和人流情况微调。"}
                    </p>
                    <p className="break-words">
                      <span className="font-bold text-[#334155]">拍法：</span>
                      {spot.method || "先拍环境建立氛围，再补主体半身、细节和备选构图。"}
                    </p>
                  </div>
                </div>

                <div
                  className={`h-14 w-[92px] shrink-0 rounded-md bg-gradient-to-br ${gradients[index % gradients.length]}`}
                />
              </div>
            </div>
          </div>
          {index < spots.length - 1 && (
            <div className="mx-3 h-px bg-[#E2E8F0]" />
          )}
        </div>
      ))}
    </div>
  )
}

export type { TimelineSpot }
