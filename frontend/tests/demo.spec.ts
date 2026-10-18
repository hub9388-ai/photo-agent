import { expect, test, type Page } from "@playwright/test"
import { readFile } from "node:fs/promises"

const failures = new WeakMap<Page, string[]>()
test.beforeEach(async ({ page }) => {
  const problems: string[] = []
  failures.set(page, problems)
  page.on("pageerror", error => problems.push(error.message))
  page.on("request", request => {
    const url = new URL(request.url())
    if (url.origin !== "http://127.0.0.1:4175" || url.pathname.startsWith("/api/") || !["GET", "HEAD"].includes(request.method())) problems.push(`${request.method()} ${url.origin}${url.pathname}`)
  })
})
test.afterEach(async ({ page }) => {
  expect(failures.get(page), "No backend/model requests or uncaught browser errors").toEqual([])
})

test("cat analysis → retouch → saved asset → learning, with reload persistence", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("link", { name: "开始照片分析" }).click()
  await page.getByRole("button", { name: "开始分析演示" }).click()
  await expect(page.getByRole("link", { name: "带建议进入修图" })).toBeVisible()
  await page.getByRole("tab", { name: "Coach · 学习反馈" }).click()
  await expect(page.getByText("下次左右移动半步", { exact: false })).toBeVisible()
  await page.getByRole("link", { name: "带建议进入修图" }).click()
  await page.getByRole("button", { name: "载入 Post 建议" }).click()
  await expect(page.getByRole("slider", { name: "亮度", exact: true })).toHaveValue("4")
  await page.getByRole("button", { name: "应用调色" }).click()
  await page.getByRole("button", { name: "查看圆润效果" }).click()
  await expect(page.getByRole("heading", { name: "圆润效果", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "查看原图对比" }).click()
  await expect(page.getByRole("heading", { name: "原图", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "返回编辑效果" }).click()
  await page.getByAltText("三花猫圆润后的预置生成效果").first().evaluate(async element => { await (element as HTMLImageElement).decode() })
  await page.screenshot({ path: "../.test_artifacts/frontend-demo/desktop-retouch.png", fullPage: true })
  await page.getByRole("button", { name: "保存到素材库" }).click()
  await page.getByRole("link", { name: "查看素材库" }).click()
  await expect(page.getByRole("heading", { name: "圆润版本 · 已保存" })).toBeVisible()
  await page.reload()
  await expect(page.getByRole("heading", { name: "圆润版本 · 已保存" })).toBeVisible()
  await page.getByRole("link", { name: "把反馈变成下一次练习" }).click()
  await page.getByRole("checkbox").check()
  await page.getByRole("link", { name: "历史", exact: true }).click()
  await expect(page.getByText("已体验", { exact: true })).toHaveCount(4)
})

test("export contains applied filter, undo does not overwrite saved snapshot", async ({ page }) => {
  await page.goto("/retouch/")
  await page.getByRole("slider", { name: "亮度", exact: true }).fill("20")
  await expect(page.getByRole("button", { name: "导出 PNG" })).toBeDisabled()
  await page.getByRole("button", { name: "应用调色" }).click()
  await page.getByRole("button", { name: "保存到素材库" }).click()
  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: "导出 PNG" }).click()
  const download = await downloadPromise
  const data = await readFile((await download.path())!)
  expect(data.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a")
  const pixels = await page.evaluate(async base64 => {
    const sample = async (src: string) => {
      const image = new Image(); image.src = src; await image.decode()
      const canvas = document.createElement("canvas"); canvas.width = 768; canvas.height = 1024
      const context = canvas.getContext("2d")!; context.drawImage(image, 0, 0)
      return [...context.getImageData(600, 700, 1, 1).data]
    }
    return { original: await sample("/demo/cat-original.png"), exported: await sample(`data:image/png;base64,${base64}`) }
  }, data.toString("base64"))
  for (let i = 0; i < 3; i++) expect(pixels.exported[i]).toBeGreaterThan(pixels.original[i])
  await page.getByRole("button", { name: "撤销", exact: true }).click()
  await expect(page.getByRole("slider", { name: "亮度", exact: true })).toHaveValue("0")
  await page.getByRole("link", { name: "查看素材库" }).click()
  await expect(page.getByAltText("街角三花猫原图").last()).toHaveAttribute("style", /brightness\(1.2\)/)
})

test("planning supports fixed West Lake case, other prompts don't pretend to generate", async ({ page }) => {
  await page.goto("/planning/")
  await page.getByRole("textbox").fill("去北京两天")
  await page.getByRole("button", { name: "展示示例规划" }).click()
  await expect(page.getByRole("alert").filter({ hasText: "仅支持西湖一日游案例" })).toBeVisible()
  await page.getByRole("textbox").fill("去杭州西湖游玩一天")
  await page.getByRole("button", { name: "展示示例规划" }).click()
  await expect(page.getByRole("heading", { name: "断桥 → 白堤" })).toBeVisible()
  await page.reload()
  await expect(page.getByRole("heading", { name: "断桥 → 白堤" })).toBeVisible()
})

test("all demo pages work as direct static links on mobile, without overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const route of ["/", "/analysis/", "/analysis/demo-cat/", "/retouch/", "/assets/", "/learning/", "/planning/", "/history/"]) {
    const response = await page.goto(route)
    expect(response?.status()).toBe(200)
    await expect(page.getByRole("button", { name: "重置体验" })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.goto("/retouch/")
  await page.locator("img").evaluateAll(async images => {
    await Promise.all(images.map(async element => { const image = element as HTMLImageElement; image.loading = "eager"; await image.decode() }))
  })
  await page.screenshot({ path: "../.test_artifacts/frontend-demo/mobile-retouch.png", fullPage: true })
})

test("reset clears the complete workflow", async ({ page }) => {
  await page.goto("/retouch/")
  await page.getByRole("button", { name: "查看圆润效果" }).click()
  await page.getByRole("button", { name: "保存到素材库" }).click()
  page.once("dialog", dialog => dialog.accept())
  await page.getByRole("button", { name: "重置体验" }).click()
  await page.getByRole("link", { name: "查看素材库" }).click()
  await expect(page.getByText("还没有保存编辑版本。", { exact: true })).toBeVisible()
})
