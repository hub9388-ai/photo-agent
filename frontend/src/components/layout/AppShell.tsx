import { TopNav } from "./TopNav"
import { Toaster } from "@/components/ui/toaster"
import { DEMO_MODE } from "@/lib/demo/config"
import { DemoApp } from "@/components/demo/DemoApp"

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  if (DEMO_MODE) return <DemoApp />
  return (
    <div className="min-h-screen bg-slate-50">
      <TopNav />
      <main className="flex-1">
        {children}
      </main>
      <Toaster />
    </div>
  )
}
