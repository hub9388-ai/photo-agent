import { Check } from "lucide-react"

interface PostSuggestion {
  category: string
  items: string[]
}

interface PostParams {
  exposure: string
  contrast: string
  highlights: string
  shadows: string
}

export interface PostResultCardProps {
  summary: string
  suggestions: PostSuggestion[]
  params?: PostParams
}

export function PostResultCard({ summary, suggestions, params }: PostResultCardProps) {
  return (
    <div className="space-y-4">
      <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
        {summary}
      </div>

      <div className="space-y-3">
        {suggestions.map((suggestion) => (
          <div key={suggestion.category} className="flex items-start gap-2">
            <Check className="w-4 h-4 text-blue-500 mt-0.5" />
            <div>
              <p className="font-medium text-sm">{suggestion.category}</p>
              <ul className="text-xs text-slate-500 mt-1 space-y-1">
                {suggestion.items.map((item, index) => (
                  <li key={index}>• {item}</li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>

      {params && (
        <div className="p-3 bg-slate-50 rounded-lg">
          <p className="font-medium text-sm mb-2">参数建议</p>
          <div className="grid grid-cols-4 gap-2 text-xs">
            <div className="bg-white p-2 rounded text-center">
              <p className="text-slate-400">曝光</p>
              <p className="font-medium">{params.exposure}</p>
            </div>
            <div className="bg-white p-2 rounded text-center">
              <p className="text-slate-400">对比度</p>
              <p className="font-medium">{params.contrast}</p>
            </div>
            <div className="bg-white p-2 rounded text-center">
              <p className="text-slate-400">高光</p>
              <p className="font-medium">{params.highlights}</p>
            </div>
            <div className="bg-white p-2 rounded text-center">
              <p className="text-slate-400">阴影</p>
              <p className="font-medium">{params.shadows}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
