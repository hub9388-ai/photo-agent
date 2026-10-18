import { TopNav } from "./TopNav"
import { Toaster } from "@/components/ui/toaster"
import { DEMO_MODE } from "@/lib/demo/config"
import { DemoBanner } from "@/components/demo/DemoBanner"

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-slate-50">
      <TopNav />
      {DEMO_MODE && <DemoBanner />}
      <main className="flex-1">
        {children}
      </main>
      <Toaster />
    </div>
  )
}
