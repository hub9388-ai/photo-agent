import Link from "next/link"
import { ArrowRight } from "lucide-react"

export const buttonClass = "inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
export const secondaryClass = "inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
export const panelClass = "rounded-2xl border border-slate-200 bg-white p-5 md:p-6"
export function DemoLink({ href, children, secondary = false }: { href: string; children: React.ReactNode; secondary?: boolean }) {
  return <Link href={href} className={secondary ? secondaryClass : buttonClass}>{children}<ArrowRight className="h-4 w-4" /></Link>
}
export function DemoList({ items }: { items: string[] }) {
  return <ul className="space-y-3 text-sm leading-7 text-slate-600">{items.map(item => <li key={item} className="flex gap-2"><span className="text-blue-500">•</span><span>{item}</span></li>)}</ul>
}
