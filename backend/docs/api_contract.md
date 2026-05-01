# Backend API Contract

## Scope

This document records the MVP API contract for frontend integration. The backend currently supports media upload, job creation, job history, SSE event replay, result retrieval, post/coach agent retry, asset indexing, and explicit planning jobs.

## Endpoints

- `GET /api/health`
- `POST /api/media/upload`
- `POST /api/jobs`
- `GET /api/jobs?media_id={mediaId}`
- `GET /api/jobs/{jobId}`
- `GET /api/jobs/{jobId}/events`
- `GET /api/jobs/{jobId}/results`
- `POST /api/jobs/{jobId}/agents/{agent}/retry`
- `POST /api/agents/plan/run`
- `POST /api/projects/{projectId}/assets/import`
- `GET /api/projects/{projectId}/assets?job_id={jobId}&grade={grade}`
- `POST /api/handoff`

## Naming Convention

MVP request bodies use Python-style `snake_case` field names. This keeps the API close to the current backend schemas and legacy integration layer during early backend stabilization.

Response JSON uses frontend-friendly `camelCase` aliases. For example:

- request: `media_ids`, `user_goal`, `source_job_id`
- response: `mediaId`, `jobId`, `eventsUrl`, `resultsUrl`, `completedAgents`

Frontend clients should send `snake_case` request bodies for the MVP. The backend may add camelCase request aliases later if frontend integration shows a clear need.

## Asset Indexing

`POST /api/projects/{projectId}/assets/import` starts an explicit background asset-indexing job. Asset indexing is not triggered by single-photo upload.

The import request must provide a local `project_root`. For safety, the directory must be under an allowed import root:

- default: backend `media_root`
- configurable: `PHOTO_ASSET_IMPORT_ROOTS`, separated by the platform path separator

The asset result is saved independently under `agent="asset"`. `GET /api/projects/{projectId}/assets` reads the latest persisted asset index and supports grade filtering with `A`, `B`, `C`, or `Reject`.

## Skills / MCP Boundary

Stage 8.5 keeps Skills and MCP as optional, backend-internal capabilities. The frontend must not call Skills or MCP tools directly.

MVP behavior:

- no standalone `SkillRegistry`
- no MCP Server
- no external photography knowledge MCP resource
- legacy local Skills loading is preserved
- missing or failed local Skills loading degrades to no extra Skills knowledge and returns a warning in agent results

## Planning

`POST /api/agents/plan/run` starts an explicit `trip_planning` job with `agents=["plan"]`. Planning is not triggered by media upload and is not part of the default post/coach review flow.

中文说明：`/api/agents/plan/run` 不是独立执行器，而是 `trip_planning` job 的便捷入口。它会创建普通 Job，并继续使用同一套 JobStore、EventStore、ResultStore、EventBus、SSE 与 results API。前端可以根据场景选择：

- 通用任务入口：`POST /api/jobs`
- 语义化规划入口：`POST /api/agents/plan/run`

两种入口都应返回 `jobId`、`eventsUrl`、`resultsUrl`，前端后续仍通过 `/api/jobs/{jobId}/events` 和 `/api/jobs/{jobId}/results` 订阅事件和读取结果。

The request may include `city`, `target_location`, `shoot_date`, `time_window`, `subject`, `style_keywords`, `gear`, `budget`, `constraints`, and optional `reference_media_ids`. Missing planning information should produce a clarification-style agent result/event instead of silently running a default photo review.

Provider data uses the legacy `photo_provider_adapter.py` path for MVP. Weather/place provider failures should degrade into provider notes and warnings when possible; they must not fabricate realtime facts.

## Job Flow

The stage 5 MVP flow is:

1. Upload media and receive `mediaId`.
2. Create a `photo_review` job with `agents=["post", "coach"]`.
3. Subscribe to `/api/jobs/{jobId}/events` for SSE progress.
4. Read `/api/jobs/{jobId}/results` for latest persisted agent results.

`agent.delta` is stream-only and is not persisted to SQLite. SSE replay restores persisted events only.

## Job Results

`GET /api/jobs/{jobId}/results` returns latest result per agent:

- `completedAgents`
- `failedAgents`
- `pendingAgents`
- `results`

When one agent fails and another succeeds, the job status is `partial_completed`. Failed agent results include an `error` field.

## Retry

`POST /api/jobs/{jobId}/agents/{agent}/retry` retries one existing job agent.

MVP retry support is limited to:

- `post`
- `coach`

Retry does not create a new job. It appends new agent events and stores a new latest result for that agent.

## Error Codes

Structured error responses use:

- `MEDIA_INVALID_TYPE`
- `MEDIA_TOO_LARGE`
- `MEDIA_PROCESSING_FAILED`
- `MODEL_TIMEOUT`
- `MODEL_RATE_LIMIT`
- `MODEL_AUTH_FAILED`
- `AGENT_FAILED`
- `JOB_NOT_FOUND`
- `PROVIDER_UNAVAILABLE`
- `HANDOFF_REJECTED`
- `VALIDATION_ERROR`

Error responses use `ErrorResponse`:

```json
{
  "errorCode": "JOB_NOT_FOUND",
  "message": "Job not found.",
  "detail": {}
}
```

User-visible messages should stay generic for model authentication failures. Internal debug details must not expose API keys, auth tokens, or full provider credentials.
