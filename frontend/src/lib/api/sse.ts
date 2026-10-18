/**
 * SSE (Server-Sent Events) 订阅逻辑
 * 支持 mock 模式（模拟 SSE）和真实 SSE 连接
 */

import type { AgentEventMessage, SSEEvent } from "@/types/api"
import { buildApiUrl, isMockMode, delay } from "./client"
import { mockAgentEvents, mockSSEEvents } from "@/mocks"
import { DEMO_MODE } from "@/lib/demo/config"
import { subscribeDemoJob } from "@/lib/demo/api"

// SSE 连接配置
const SSE_URL = process.env.NEXT_PUBLIC_SSE_URL || "/api/jobs"

// SSE 回调类型
interface SSECallbacks {
  onMessage?: (event: SSEEvent) => void
  onError?: (error: Error) => void
  onOpen?: () => void
  onClose?: () => void
}

export interface JobEventHandlers {
  onEvent?: (event: AgentEventMessage) => void
  onOpen?: () => void
  onError?: (error: Error) => void
  onClose?: () => void
}

export function subscribeJobEvents(
  jobId: string,
  handlers: JobEventHandlers = {}
): () => void {
  if (DEMO_MODE) {
    handlers.onOpen?.()
    return subscribeDemoJob(jobId, event => { handlers.onEvent?.(event); if (event.type === "job.completed") handlers.onClose?.() })
  }
  if (isMockMode()) {
    let eventIndex = 0
    let closed = false
    let timer: NodeJS.Timeout | null = null

    delay(200).then(() => {
      if (closed) return
      handlers.onOpen?.()

      timer = setInterval(() => {
        if (closed) return
        if (eventIndex >= mockAgentEvents.length) {
          if (timer) clearInterval(timer)
          handlers.onClose?.()
          return
        }

        handlers.onEvent?.({
          ...mockAgentEvents[eventIndex],
          jobId,
        })
        eventIndex += 1
      }, 600)
    })

    return () => {
      closed = true
      if (timer) clearInterval(timer)
      handlers.onClose?.()
    }
  }

  const eventSource = new EventSource(buildApiUrl(`/api/jobs/${jobId}/events`))

  eventSource.onopen = () => {
    handlers.onOpen?.()
  }

  eventSource.onmessage = (message) => {
    try {
      handlers.onEvent?.(JSON.parse(message.data) as AgentEventMessage)
    } catch (error) {
      handlers.onError?.(error as Error)
    }
  }

  const eventTypes = [
    "job.created",
    "job.started",
    "agent.started",
    "agent.progress",
    "agent.delta",
    "agent.result",
    "agent.error",
    "job.completed",
    "job.partial_completed",
    "job.failed",
  ]

  eventTypes.forEach((eventType) => {
    eventSource.addEventListener(eventType, (message) => {
      try {
        handlers.onEvent?.(JSON.parse(message.data) as AgentEventMessage)
      } catch (error) {
        handlers.onError?.(error as Error)
      }
    })
  })

  eventSource.onerror = () => {
    handlers.onError?.(new Error("SSE connection error"))
  }

  return () => {
    eventSource.close()
    handlers.onClose?.()
  }
}

// SSE 连接管理器
export class SSEConnection {
  private eventSource: EventSource | null = null
  private callbacks: SSECallbacks
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private url: string
  private isMock: boolean
  private mockInterval: NodeJS.Timeout | null = null

  constructor(url: string = SSE_URL, callbacks: SSECallbacks = {}) {
    this.url = url
    this.callbacks = callbacks
    this.isMock = isMockMode()
  }

  // 建立连接
  connect(): void {
    if (this.isMock) {
      this.startMockConnection()
    } else {
      this.startRealConnection()
    }
  }

  // 断开连接
  disconnect(): void {
    if (this.mockInterval) {
      clearInterval(this.mockInterval)
      this.mockInterval = null
    }

    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }

    this.callbacks.onClose?.()
  }

  // 真实 SSE 连接
  private startRealConnection(): void {
    try {
      this.eventSource = new EventSource(this.url)

      this.eventSource.onopen = () => {
        console.log("[SSE] Connected")
        this.reconnectAttempts = 0
        this.callbacks.onOpen?.()
      }

      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as SSEEvent
          this.callbacks.onMessage?.(data)
        } catch (error) {
          console.error("[SSE] Failed to parse message:", error)
        }
      }

      this.eventSource.onerror = (error) => {
        console.error("[SSE] Error:", error)
        this.callbacks.onError?.(new Error("SSE connection error"))
        this.handleReconnect()
      }
    } catch (error) {
      console.error("[SSE] Failed to connect:", error)
      this.callbacks.onError?.(error as Error)
    }
  }

  // 模拟 SSE 连接
  private startMockConnection(): void {
    console.log("[SSE] Mock mode - simulating SSE connection")

    let eventIndex = 0
    const events = [...mockSSEEvents]

    // 模拟连接建立
    delay(300).then(() => {
      this.callbacks.onOpen?.()

      // 发送初始事件
      if (events.length > 0) {
        this.callbacks.onMessage?.(events[0])
        eventIndex = 1
      }
    })

    // 定期发送事件
    this.mockInterval = setInterval(() => {
      if (eventIndex < events.length) {
        this.callbacks.onMessage?.(events[eventIndex])
        eventIndex++
      } else {
        // 循环播放或停止
        eventIndex = 0
      }
    }, 2000)
  }

  // 重连逻辑
  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("[SSE] Max reconnect attempts reached")
      this.callbacks.onError?.(new Error("Max reconnect attempts reached"))
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * this.reconnectAttempts

    console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)

    setTimeout(() => {
      this.connect()
    }, delay)
  }
}

// 创建 Job 特定的 SSE 连接
export function connectToJobSSE(
  jobId: string,
  callbacks: SSECallbacks
): SSEConnection {
  const url = isMockMode() ? "" : `${SSE_URL}/jobs/${jobId}`
  const connection = new SSEConnection(url, callbacks)
  connection.connect()
  return connection
}

// React Hook 风格的 SSE 订阅（简化版）
export function subscribeToSSE(
  callbacks: SSECallbacks
): () => void {
  const connection = new SSEConnection(SSE_URL, callbacks)
  connection.connect()

  // 返回清理函数
  return () => {
    connection.disconnect()
  }
}

// 模拟 SSE 事件流（用于测试）
export async function* mockSSEStream(): AsyncGenerator<SSEEvent, void, unknown> {
  for (const event of mockSSEEvents) {
    await delay(1000)
    yield event
  }
}
