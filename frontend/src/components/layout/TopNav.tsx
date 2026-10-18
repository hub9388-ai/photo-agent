"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { DEMO_MODE } from "@/lib/demo/config"
import { photographyWorkflow } from "@/lib/photography-workflow"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Camera,
  Home,
  Clock,
  Search,
  Bell,
  User,
} from "lucide-react"

const navItems = [
  { path: "/", label: "工作台", icon: Home },
  ...photographyWorkflow,
  { path: "/history", label: "历史", icon: Clock },
]

export function TopNav() {
  const pathname = usePathname()

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white">
      <div className="flex min-h-14 flex-wrap items-center gap-y-2 px-4 py-2 md:px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 mr-8">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-900 text-white">
            <Camera className="w-5 h-5" />
          </div>
          <span className="text-lg font-semibold text-slate-900">PhotoAI</span>
        </Link>

        {/* Navigation */}
        <nav aria-label="主导航" className="order-last flex w-full items-center gap-1 overflow-x-auto md:order-none md:w-auto md:flex-1">
          {navItems.map((item) => {
            const isActive = pathname === item.path || pathname.startsWith(`${item.path}/`)
            const Icon = item.icon

            return (
              <Link
                key={item.path}
                href={item.path}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "relative flex shrink-0 items-center gap-2 px-3 py-2 text-sm font-medium rounded-md transition-colors",
                  isActive
                    ? "text-slate-900 bg-slate-100"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                )}
              >
                <Icon className="w-4 h-4" />
                {item.label}
                {isActive && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-blue-500 rounded-full" />
                )}
              </Link>
            )
          })}
        </nav>

        {/* Right Side */}
        <div className="flex items-center gap-3">
          {/* Connection Status */}
          <Badge
            variant="outline"
            className="hidden md:flex items-center gap-1.5 bg-green-50 text-green-700 border-green-200"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
            {DEMO_MODE ? "演示模式" : "已连接"}
          </Badge>

          {!DEMO_MODE && <>
          {/* Search */}
          <Button variant="ghost" size="icon" className="text-slate-600">
            <Search className="w-5 h-5" />
          </Button>

          {/* Notifications */}
          <Button variant="ghost" size="icon" className="text-slate-600 relative">
            <Bell className="w-5 h-5" />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
          </Button>

          {/* User Avatar */}
          <Button variant="ghost" size="icon" className="rounded-full bg-slate-100">
            <User className="w-5 h-5 text-slate-600" />
          </Button>
          </>}
        </div>
      </div>
    </header>
  )
}
