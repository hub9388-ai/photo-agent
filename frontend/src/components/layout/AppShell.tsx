import { TopNav } from "./TopNav"
import { Toaster } from "@/components/ui/toaster"

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
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
