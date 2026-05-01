# Stage 5 Smoke Test

Date: 2026-04-26

## Conclusion

Stage 5 real model flow has been verified manually:

- Media upload succeeded and returned a `mediaId`.
- A `photo_review` job was created successfully.
- `PostAgentService` and `CoachAgentService` ran through the backend job flow.
- SSE events were emitted for `job.created`, `job.started`, `agent.started`, `agent.progress`, `agent.result`, and `job.completed`.
- Both `post` and `coach` results were saved and the job reached `completed`.
- Browser/API raw responses display Chinese text correctly.

## Notes

- PowerShell Chinese mojibake is a local terminal display issue, not a backend response issue.
- The current real model integration uses Anthropic-compatible settings only.
- `MOONSHOT_API_KEY` and `MOONSHOT_BASE_URL` are present in local configuration but are not wired into the backend model provider yet.
- The MVP is still single-process and single-worker. Multi-worker deployment requires a cross-process event system such as Redis.
- `agent.delta` is intentionally streamed only and not persisted to SQLite. This is expected behavior, not a bug.
