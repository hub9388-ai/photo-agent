/**
 * API Client 基础封装
 * 支持 mock/real 模式切换
 */

import type { ApiResponse } from "@/types/api"

// API 配置
const API_MODE = process.env.NEXT_PUBLIC_API_MODE || "mock"
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"

export const isMockMode = () => API_MODE === "mock"
export const getApiBaseUrl = () => API_BASE_URL

// 请求配置选项
interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>
}

// 构建完整 URL
function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const baseUrl = isMockMode() ? "" : API_BASE_URL
  const url = new URL(path, baseUrl || window.location.origin)

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.set(key, String(value))
      }
    })
  }

  return url.toString()
}

export function buildApiUrl(
  path: string,
  params?: Record<string, string | number | boolean | undefined>
): string {
  return buildUrl(path, params)
}

// 通用请求函数
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { params, ...fetchOptions } = options
  const url = buildUrl(path, params)

  // 默认配置
  const config: RequestInit = {
    headers: {
      "Content-Type": "application/json",
      ...fetchOptions.headers,
    },
    ...fetchOptions,
  }

  // 添加认证 token（如果有）
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null
  if (token) {
    config.headers = {
      ...config.headers,
      Authorization: `Bearer ${token}`,
    }
  }

  const response = await fetch(url, config)

  // 处理 HTTP 错误
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: "Unknown error" }))
    throw new ApiError(response.status, error.message || `HTTP ${response.status}`)
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return request<T>(path, options)
}

export async function uploadForm<T>(path: string, formData: FormData): Promise<T> {
  const url = buildUrl(path)
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: "Upload failed" }))
    throw new ApiError(response.status, error.message || `HTTP ${response.status}`, error.code)
  }

  return response.json() as Promise<T>
}

// API 错误类
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string
  ) {
    super(message)
    this.name = "ApiError"
  }
}

// API Client 对象
export const apiClient = {
  // GET 请求
  get: <T>(path: string, options?: RequestOptions) =>
    request<ApiResponse<T>>(path, { ...options, method: "GET" }),

  // POST 请求
  post: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<ApiResponse<T>>(path, {
      ...options,
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    }),

  // PUT 请求
  put: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<ApiResponse<T>>(path, {
      ...options,
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
    }),

  // PATCH 请求
  patch: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<ApiResponse<T>>(path, {
      ...options,
      method: "PATCH",
      body: data ? JSON.stringify(data) : undefined,
    }),

  // DELETE 请求
  delete: <T>(path: string, options?: RequestOptions) =>
    request<ApiResponse<T>>(path, { ...options, method: "DELETE" }),

  // 文件上传
  upload: async <T>(path: string, files: File[], options?: RequestOptions) => {
    const formData = new FormData()
    files.forEach((file) => formData.append("files", file))

    const url = buildUrl(path)
    const response = await fetch(url, {
      method: "POST",
      body: formData,
      headers: {
        ...(options?.headers || {}),
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: "Upload failed" }))
      throw new ApiError(response.status, error.message)
    }

    return response.json() as Promise<ApiResponse<T>>
  },
}

// 延迟函数（用于 mock 模式模拟网络延迟）
export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// 模拟 API 响应（用于 mock 模式）
export function mockResponse<T>(data: T, delayMs: number = 500): Promise<ApiResponse<T>> {
  return delay(delayMs).then(() => ({
    success: true,
    data,
  }))
}

// 模拟错误响应
export function mockError(message: string, code: string = "MOCK_ERROR", delayMs: number = 500): Promise<never> {
  return delay(delayMs).then(() => {
    throw new ApiError(400, message, code)
  })
}
