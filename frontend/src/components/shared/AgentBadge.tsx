import { Badge, type BadgeProps } from "@/components/ui/badge"

interface AgentBadgeProps {
  agent: "post" | "coach" | "plan" | "asset" | string
  className?: string
}

export function AgentBadge({ agent, className }: AgentBadgeProps) {
  const variants: Record<string, { variant: BadgeProps["variant"]; label: string }> = {
    post: { variant: "post", label: "Post" },
    coach: { variant: "coach", label: "Coach" },
    plan: { variant: "plan", label: "Plan" },
    asset: { variant: "asset", label: "Asset" },
  }

  const config = variants[agent] || { variant: "default", label: agent }

  return (
    <Badge variant={config.variant} className={className}>
      {config.label}
    </Badge>
  )
}
