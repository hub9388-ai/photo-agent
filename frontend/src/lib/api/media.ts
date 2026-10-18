/**
 * 媒体/素材相关 API
 * 包含上传、获取、删除等操作
 */

import type {
  Asset,
  AssetStats,
  AssetProject,
  UploadMediaResponse,
  PaginatedResponse,
} from "@/types/api"
import { apiClient, apiRequest, buildApiUrl, isMockMode, mockResponse, delay, uploadForm } from "./client"

export async function getMedia(mediaId: string): Promise<UploadMediaResponse> {
  return apiRequest<UploadMediaResponse>(`/api/media/${encodeURIComponent(mediaId)}`)
}
import {
  mockAssets,
  mockAssetStats,
  mockAssetProjects,
} from "@/mocks"

// 上传单个媒体文件，匹配后端 POST /api/media/upload
export async function uploadMedia(file: File): Promise<UploadMediaResponse> {
  if (isMockMode()) {
    await delay(600)
    const mediaId = `media_${Date.now()}`
    const previewUrl =
      typeof URL !== "undefined" ? URL.createObjectURL(file) : `/mock/media/${file.name}`

    return {
      mediaId,
      previewUrl,
      fileName: file.name,
      mimeType: file.type || "application/octet-stream",
      storageUri: `media/originals/${mediaId}_${file.name}`,
      metadata: {
        size: file.size,
        lastModified: file.lastModified,
      },
    }
  }

  const formData = new FormData()
  formData.append("file", file)
  return uploadForm<UploadMediaResponse>("/api/media/upload", formData)
}

export type UploadManyMediaItemResult = {
  file: File
  response?: UploadMediaResponse
  error?: string
}

export async function uploadManyMedia(
  files: File[],
  onItemSettled?: (result: UploadManyMediaItemResult, index: number) => void
): Promise<UploadManyMediaItemResult[]> {
  const results = await Promise.all(
    files.map(async (file, index) => {
      try {
        const response = await uploadMedia(file)
        const result = { file, response } satisfies UploadManyMediaItemResult
        onItemSettled?.(result, index)
        return result
      } catch (error) {
        const result = {
          file,
          error: error instanceof Error ? error.message : "Upload failed",
        } satisfies UploadManyMediaItemResult
        onItemSettled?.(result, index)
        return result
      }
    })
  )
  return results
}

// 获取素材列表
export async function getAssets(params?: {
  projectId?: string
  grade?: string
  search?: string
  page?: number
  pageSize?: number
}): Promise<PaginatedResponse<Asset>> {
  if (isMockMode()) {
    await delay(500)
    const page = params?.page || 1
    const pageSize = params?.pageSize || 20
    const start = (page - 1) * pageSize
    const end = start + pageSize
    const items = mockAssets.slice(start, end)

    return {
      items,
      pagination: {
        page,
        pageSize,
        total: mockAssets.length,
        totalPages: Math.ceil(mockAssets.length / pageSize),
      },
    }
  }

  const response = await apiClient.get<PaginatedResponse<Asset>>("/api/assets", {
    params,
  })
  return response.data!
}

// 获取素材统计
export async function getAssetStats(): Promise<AssetStats> {
  if (isMockMode()) {
    return mockResponse(mockAssetStats, 300).then(r => r.data!)
  }

  const response = await apiClient.get<AssetStats>("/api/assets/stats")
  return response.data!
}

// 获取项目/文件夹列表
export async function getAssetProjects(): Promise<AssetProject[]> {
  if (isMockMode()) {
    return mockResponse(mockAssetProjects, 300).then(r => r.data!)
  }

  const response = await apiClient.get<AssetProject[]>("/api/assets/projects")
  return response.data!
}

// 获取单个素材详情
export async function getAsset(id: string): Promise<Asset> {
  if (isMockMode()) {
    const asset = mockAssets.find(a => a.id === id)
    if (!asset) {
      throw new Error("Asset not found")
    }
    return mockResponse(asset, 300).then(r => r.data!)
  }

  const response = await apiClient.get<Asset>(`/api/assets/${id}`)
  return response.data!
}

// 上传素材
export async function uploadAssets(
  files: File[],
  projectId?: string,
  onProgress?: (progress: number) => void
): Promise<Asset[]> {
  if (isMockMode()) {
    // 模拟上传进度
    for (let i = 0; i <= 100; i += 10) {
      await delay(100)
      onProgress?.(i)
    }
    return mockResponse(mockAssets.slice(0, files.length), 500).then(r => r.data!)
  }

  // 真实上传使用 XMLHttpRequest 以支持进度
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const formData = new FormData()
    files.forEach(file => formData.append("files", file))
    if (projectId) {
      formData.append("projectId", projectId)
    }

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        const progress = Math.round((e.loaded / e.total) * 100)
        onProgress?.(progress)
      }
    })

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const response = JSON.parse(xhr.responseText)
        resolve(response.data)
      } else {
        reject(new Error(xhr.statusText))
      }
    })

    xhr.addEventListener("error", () => reject(new Error("Upload failed")))

    xhr.open("POST", buildApiUrl("/api/assets/upload"))
    xhr.send(formData)
  })
}

// 删除素材
export async function deleteAsset(id: string): Promise<void> {
  if (isMockMode()) {
    await delay(300)
    return
  }

  await apiClient.delete(`/api/assets/${id}`)
}

// 批量删除
export async function batchDeleteAssets(ids: string[]): Promise<void> {
  if (isMockMode()) {
    await delay(500)
    return
  }

  await apiClient.post("/api/assets/batch-delete", { ids })
}

// 更新素材等级
export async function updateAssetGrade(id: string, grade: string): Promise<Asset> {
  if (isMockMode()) {
    await delay(300)
    const asset = mockAssets.find(a => a.id === id)
    if (!asset) {
      throw new Error("Asset not found")
    }
    return { ...asset, grade: grade as Asset["grade"] }
  }

  const response = await apiClient.patch<Asset>(`/api/assets/${id}/grade`, { grade })
  return response.data!
}

// 发送到 Agent
export async function sendToAgent(
  assetIds: string[],
  agentType: "post" | "coach"
): Promise<{ jobId: string }> {
  if (isMockMode()) {
    await delay(500)
    return { jobId: `job_${Date.now()}` }
  }

  const response = await apiClient.post<{ jobId: string }>("/api/assets/send-to-agent", {
    assetIds,
    agentType,
  })
  return response.data!
}
