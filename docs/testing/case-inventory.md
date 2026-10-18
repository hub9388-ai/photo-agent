# 全量测试用例索引

验证日期：2026-10-18（Asia/Shanghai）。

共 **197 条自动化用例**，覆盖 **10 个模块、39 个测试文件**。
结果：{'passed': 197}；另有 11 个子场景，不重复计入总数。

统计来源为运行报告，不是函数名或 assert 数量。[阅读测试方法与结论](README.md)；[机器可读快照](results.json)。

| 模块 | 用例数 | 通过 |
| --- | ---: | ---: |
| Agent 协作与上下文 | 33 | 33 |
| 模型与外部服务接入 | 21 | 21 |
| 输出协议与界面文案 | 26 | 26 |
| 后端 API、任务与媒体 | 20 | 20 |
| 素材、规划与数据存储 | 21 | 21 |
| 事件日志与部署保护 | 8 | 8 |
| 后期建议转换与原图传递 | 22 | 22 |
| 人物保护、笔刷与修图执行 | 32 | 32 |
| Agent 执行语义评测判定器 | 6 | 6 |
| 浏览器产品流程 | 8 | 8 |

## Agent 协作与上下文

### [test_entrypoints.py](../../tests/test_entrypoints.py)

意图路由、统一入口与分支选择。

本次 12 条；passed 12。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_entrypoints.EntrypointTests::test_asset_handoff_selection_builds_post_media_request` — passed
- `tests.test_entrypoints.EntrypointTests::test_entry_module_override_prefers_asset_for_media_requests` — passed
- `tests.test_entrypoints.EntrypointTests::test_entry_module_override_prefers_post_for_promptless_media` — passed
- `tests.test_entrypoints.EntrypointTests::test_entry_module_override_respects_explicit_prompt` — passed
- `tests.test_entrypoints.EntrypointTests::test_photo_v1_main_delegates_to_unified_entry` — passed
- `tests.test_entrypoints.EntrypointTests::test_photo_v2_main_delegates_to_unified_entry` — passed
- `tests.test_entrypoints.EntrypointTests::test_photo_v3_main_delegates_to_unified_entry` — passed
- `tests.test_entrypoints.EntrypointTests::test_photo_v4_main_delegates_to_unified_entry` — passed
- `tests.test_entrypoints.EntrypointTests::test_promptless_defaults_do_not_override_explicit_prompt` — passed
- `tests.test_entrypoints.EntrypointTests::test_promptless_single_directory_defaults_to_asset` — passed
- `tests.test_entrypoints.EntrypointTests::test_promptless_single_image_defaults_to_post` — passed
- `tests.test_entrypoints.EntrypointTests::test_rule_routing_covers_all_modules` — passed

</details>

### [test_handoff.py](../../tests/test_handoff.py)

模块交接、素材选择与非法选择处理。

本次 6 条；passed 6。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_handoff.SharedUtilsTests::test_asset_fallback_prefers_handoff_over_grade_view` — passed
- `tests.test_handoff.SharedUtilsTests::test_normalize_string_list_deduplicates_and_trims` — passed
- `tests.test_handoff.SharedUtilsTests::test_resolve_asset_intent_prefers_explicit_grade_command` — passed
- `tests.test_handoff.HandoffOrchestrationTests::test_consume_pending_handoff_accepts_selected_assets` — passed
- `tests.test_handoff.HandoffOrchestrationTests::test_consume_pending_handoff_reports_invalid_selection` — passed
- `tests.test_handoff.HandoffOrchestrationTests::test_handoff_selection_response_uses_grade_labels` — passed

</details>

### [test_end_to_end.py](../../tests/test_end_to_end.py)

合成照片导入、素材到 Post 的完整入口流程。

本次 2 条；passed 2。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_end_to_end.UnifiedEntryEndToEndTests::test_main_completes_asset_to_post_handoff_and_reuses_current_image_context` — passed
- `tests.test_end_to_end.UnifiedEntryEndToEndTests::test_main_imports_project_and_renders_index_summary` — passed

</details>

### [test_asset_recovery.py](../../tests/test_asset_recovery.py)

素材焦点恢复、失败后的上下文恢复。

本次 3 条；passed 3。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_asset_recovery.AssetRecoveryTests::test_asset_search_single_result_becomes_current_focus` — passed
- `tests.test_asset_recovery.AssetRecoveryTests::test_main_restores_handoff_selection_after_post_read_failure` — passed
- `tests.test_asset_recovery.AssetRecoveryTests::test_main_reuses_single_search_result_for_asset_followup_post` — passed

</details>

### [test_post_chat.py](../../tests/test_post_chat.py)

流式回复回退与重试边界。

本次 3 条；passed 3。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_post_chat.ChatStreamingFallbackTests::test_chat_streaming_preserves_non_thinking_bad_request` — passed
- `tests.test_post_chat.ChatStreamingFallbackTests::test_chat_streaming_retries_rate_limit_once` — passed
- `tests.test_post_chat.ChatStreamingFallbackTests::test_chat_streaming_retries_without_thinking_on_budget_error` — passed

</details>

### [test_plan_followup.py](../../tests/test_plan_followup.py)

规划追问及多轮上下文延续。

本次 4 条；passed 4。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_plan_followup.PlanningFollowupStateTests::test_should_not_resume_planning_followup_for_explicit_post_switch` — passed
- `tests.test_plan_followup.PlanningFollowupStateTests::test_should_resume_planning_followup_for_plan_choice` — passed
- `tests.test_plan_followup.UnifiedEntryPlanningFollowupTests::test_main_keeps_plan_followup_inside_planning_module` — passed
- `tests.test_plan_followup.UnifiedEntryPlanningFollowupTests::test_non_plan_switch_clears_pending_plan_followup` — passed

</details>

### [test_coach_lifecycle.py](../../tests/test_coach_lifecycle.py)

练习任务从分配到完成的历史状态更新。

本次 1 条；passed 1。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_coach_lifecycle.CoachLifecycleTests::test_lesson_history_moves_from_assigned_to_completed` — passed

</details>

### [test_agent_services_stage5.py](../../backend/tests/test_agent_services_stage5.py)

Post / Coach API 请求到 Agent 服务的映射。

本次 2 条；passed 2。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_agent_services_stage5::test_post_agent_service_maps_request_to_legacy_call` — passed
- `backend.tests.test_agent_services_stage5::test_coach_agent_service_maps_request_to_legacy_call` — passed

</details>


## 模型与外部服务接入

### [test_runtime.py](../../tests/test_runtime.py)

配置读取、凭据缺失和模型客户端初始化。

本次 9 条；passed 9。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_runtime.RuntimeTests::test_create_anthropic_client_prefers_auth_token_mode` — passed
- `tests.test_runtime.RuntimeTests::test_deepseek_ignores_legacy_endpoint_model_and_auth` — passed
- `tests.test_runtime.RuntimeTests::test_deepseek_model_override` — passed
- `tests.test_runtime.RuntimeTests::test_deepseek_rejects_incompatible_or_untrusted_endpoints` — passed
- `tests.test_runtime.RuntimeTests::test_deepseek_request_does_not_send_stale_or_empty_bearer_header` — passed
- `tests.test_runtime.RuntimeTests::test_ensure_anthropic_credentials_accepts_auth_token` — passed
- `tests.test_runtime.RuntimeTests::test_ensure_required_env_exits_early_when_missing` — passed
- `tests.test_runtime.RuntimeTests::test_explicit_deepseek_never_falls_back_to_legacy_key` — passed
- `tests.test_runtime.RuntimeTests::test_resolve_env_value_falls_back_to_persistent_env` — passed

</details>

### [test_provider_adapter.py](../../tests/test_provider_adapter.py)

参考链接检索与高德 POI 响应适配。

本次 2 条；passed 2。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_provider_adapter.ProviderAdapterTests::test_search_places_normalizes_amap_payload` — passed
- `tests.test_provider_adapter.ProviderAdapterTests::test_search_reference_links_parses_html_results` — passed

</details>

### [test_qwen_image_config.py](../../tests/test_qwen_image_config.py)

Key / URL 选择、歧义配置及不可信目标拦截。

本次 4 条；passed 4。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_qwen_image_config.QwenConfigurationTests::test_configure_does_not_activate_generation_or_change_database` — passed
- `tests.test_qwen_image_config.QwenConfigurationTests::test_refuses_ambiguous_explicit_keys` — passed
- `tests.test_qwen_image_config.QwenConfigurationTests::test_rejects_untrusted_destination_before_sending_credentials` — passed
- `tests.test_qwen_image_config.QwenConfigurationTests::test_repeated_legacy_variables_do_not_select_relay_or_deepseek_key` — passed

</details>

### [test_settings.py](../../backend/tests/test_settings.py)

后端配置读取。

本次 1 条；passed 1。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_settings::test_candidate_env_files_include_repo_root_before_backend` — passed

</details>

### [test_legacy_imports.py](../../backend/tests/test_legacy_imports.py)

既有 Agent 模块导入兼容。

本次 1 条；passed 1。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_legacy_imports::test_agent_services_import_legacy_modules` — passed

</details>

### [test_skills_mcp_stage85.py](../../backend/tests/test_skills_mcp_stage85.py)

知识加载缺失时降级及 API 暴露边界。

本次 4 条；passed 4。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_skills_mcp_stage85::test_post_agent_degrades_when_legacy_skills_loader_fails` — passed
- `backend.tests.test_skills_mcp_stage85::test_coach_agent_degrades_when_legacy_skills_missing` — passed
- `backend.tests.test_skills_mcp_stage85::test_plan_agent_degrades_when_planning_skills_missing` — passed
- `backend.tests.test_skills_mcp_stage85::test_openapi_does_not_expose_skills_or_mcp_endpoints` — passed

</details>


## 输出协议与界面文案

### [test_protocol.py](../../tests/test_protocol.py)

文本与 JSON 分段、截断恢复与非 JSON 回退。

本次 8 条；passed 8。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_protocol.ProtocolTests::test_split_response_sections_with_delimiter` — passed
- `tests.test_protocol.ProtocolTests::test_split_response_sections_with_json_anchor` — passed
- `tests.test_protocol.ProtocolTests::test_split_response_sections_without_structured_tail` — passed
- `tests.test_protocol.ProtocolTests::test_v1_analysis_payload_parses_tail` — passed
- `tests.test_protocol.ProtocolTests::test_v2_split_and_parse_half_stream_payload` — passed
- `tests.test_protocol.ProtocolTests::test_v3_extract_planning_brief_falls_back_to_user_text_when_model_returns_non_json` — passed
- `tests.test_protocol.ProtocolTests::test_v3_planning_payload_parses_tail` — passed
- `tests.test_protocol.ProtocolTests::test_v3_truncated_payload_salvages_first_complete_plan` — passed

</details>

### [test_cli.py](../../tests/test_cli.py)

中文标题、提示、排序与乱码回归。

本次 9 条；passed 9。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_cli.CLIRenderingTests::test_post_input_tips_render_to_sink` — passed
- `tests.test_cli.CLIRenderingTests::test_unified_entry_banner_renders_to_sink` — passed
- `tests.test_cli.UserFacingTextTests::test_asset_subset_uses_grade_labels_numbering_and_score_sort` — passed
- `tests.test_cli.UserFacingTextTests::test_key_chinese_outputs_do_not_contain_mojibake_fragments` — passed
- `tests.test_cli.UserFacingTextTests::test_scene_preview_puts_grade_breakdown_on_new_line` — passed
- `tests.test_cli.UserFacingTextTests::test_v2_instruction_uses_shared_response_delimiter` — passed
- `tests.test_cli.UserFacingTextTests::test_v2_render_response_uses_clean_chinese_headings` — passed
- `tests.test_cli.UserFacingTextTests::test_v3_planning_headers_are_clean` — passed
- `tests.test_cli.UserFacingTextTests::test_v3_render_planning_response_uses_clean_chinese_headers` — passed

</details>

### [test_agent_request_contract.py](../../backend/tests/test_agent_request_contract.py)

Agent 请求字段与结果保存约定。

本次 5 条；passed 5。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_agent_request_contract::test_agent_request_union_uses_agent_discriminator` — passed
- `backend.tests.test_agent_request_contract::test_agent_requests_do_not_expose_legacy_runtime_fields` — passed
- `backend.tests.test_agent_request_contract::test_post_agent_request_requires_media_ids` — passed
- `backend.tests.test_agent_request_contract::test_coach_photo_feedback_requires_media_ids_but_text_qa_does_not` — passed
- `backend.tests.test_agent_request_contract::test_asset_non_chat_modes_require_project_or_media_input` — passed

</details>

### [test_contract_models.py](../../backend/tests/test_contract_models.py)

契约模型、事件去重与持久化规则。

本次 4 条；passed 4。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_contract_models::test_agent_job_supports_partial_completed_status` — passed
- `backend.tests.test_contract_models::test_model_default_factories_are_not_shared` — passed
- `backend.tests.test_contract_models::test_event_seq_must_be_positive` — passed
- `backend.tests.test_contract_models::test_event_persistence_rules_skip_delta_and_duplicate_progress_step` — passed

</details>


## 后端 API、任务与媒体

### [test_api_contract.py](../../backend/tests/test_api_contract.py)

OpenAPI 路由与响应契约。

本次 1 条；passed 1。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_api_contract::test_openapi_exposes_job_and_handoff_contracts` — passed

</details>

### [test_health.py](../../backend/tests/test_health.py)

服务健康检查。

本次 1 条；passed 1。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_health::test_health_returns_ok` — passed

</details>

### [test_job_system.py](../../backend/tests/test_job_system.py)

任务生命周期、事件、重试及结果读取。

本次 8 条；passed 8。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_job_system::test_create_job_runs_post_and_coach_services_in_parallel` — passed
- `backend.tests.test_job_system::test_job_becomes_partial_completed_when_one_agent_fails` — passed
- `backend.tests.test_job_system::test_retry_agent_updates_latest_result_and_job_status` — passed
- `backend.tests.test_job_system::test_list_jobs_can_filter_by_media_id` — passed
- `backend.tests.test_job_system::test_results_api_exposes_finished_agent_before_whole_job_completes` — passed
- `backend.tests.test_job_system::test_job_becomes_failed_when_post_and_coach_both_fail` — passed
- `backend.tests.test_job_system::test_event_store_skips_delta_and_duplicate_progress` — passed
- `backend.tests.test_job_system::test_sse_replays_persisted_events` — passed

</details>

### [test_media_upload.py](../../backend/tests/test_media_upload.py)

上传、媒体读取与错误输入。

本次 4 条；passed 4。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_media_upload::test_upload_media_saves_original_preview_thumbnail_and_record` — passed
- `backend.tests.test_media_upload::test_upload_media_rejects_unsupported_file_type` — passed
- `backend.tests.test_media_upload::test_history_media_lookup_returns_matching_upload_and_missing_is_404` — passed
- `backend.tests.test_media_upload::test_upload_media_rejects_file_over_size_limit` — passed

</details>

### [test_stage6_errors.py](../../backend/tests/test_stage6_errors.py)

缺失媒体、非法任务和交接错误的结构化反馈。

本次 6 条；passed 6。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_stage6_errors::test_job_not_found_uses_structured_error_response` — passed
- `backend.tests.test_stage6_errors::test_validation_error_uses_structured_error_response` — passed
- `backend.tests.test_stage6_errors::test_create_job_rejects_missing_media_id_before_agent_runs` — passed
- `backend.tests.test_stage6_errors::test_create_job_rejects_post_coach_job_without_media_ids` — passed
- `backend.tests.test_stage6_errors::test_media_upload_error_uses_media_error_code` — passed
- `backend.tests.test_stage6_errors::test_handoff_missing_source_job_uses_structured_error_code` — passed

</details>


## 素材、规划与数据存储

### [test_storage.py](../../tests/test_storage.py)

档案迁移、路径脱敏、缓存复用和索引进度。

本次 8 条；passed 8。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_storage.StorageTests::test_asset_index_document_redacts_absolute_paths_and_rehydrates_on_load` — passed
- `tests.test_storage.StorageTests::test_cleanup_json_cache_keeps_latest_files` — passed
- `tests.test_storage.StorageTests::test_migrate_profile_payload_supports_legacy_flat_json` — passed
- `tests.test_storage.StorageTests::test_resolve_asset_index_dir_copies_legacy_cache_files` — passed
- `tests.test_storage.StorageTests::test_resolve_profile_path_copies_legacy_profile_into_user_data_dir` — passed
- `tests.test_storage.AssetIndexSinkTests::test_index_project_assets_reports_progress_to_sink` — passed
- `tests.test_storage.AssetIndexSinkTests::test_index_project_assets_reuses_cached_records_on_second_run` — passed
- `tests.test_storage.AssetIndexSinkTests::test_index_project_assets_uses_parallel_rebuild_for_multiple_files` — passed

</details>

### [test_asset_stage7.py](../../backend/tests/test_asset_stage7.py)

素材导入、索引、筛选及流转。

本次 5 条；passed 5。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_asset_stage7::test_asset_agent_service_maps_import_request_to_legacy_index` — passed
- `backend.tests.test_asset_stage7::test_import_project_assets_creates_asset_job_and_lists_filtered_assets` — passed
- `backend.tests.test_asset_stage7::test_asset_handoff_to_post_creates_target_job_with_registered_media` — passed
- `backend.tests.test_asset_stage7::test_project_import_rejects_directory_outside_allowed_roots` — passed
- `backend.tests.test_asset_stage7::test_sse_replay_contains_asset_events` — passed

</details>

### [test_asset_score_api.py](../../backend/tests/test_asset_score_api.py)

素材评分接口。

本次 2 条；passed 2。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_asset_score_api::test_asset_score_uses_asset_agent_visual_pipeline_and_detects_exact_duplicates` — passed
- `backend.tests.test_asset_score_api::test_asset_score_rejects_missing_media_id` — passed

</details>

### [test_plan_stage8.py](../../backend/tests/test_plan_stage8.py)

规划澄清、约束传递和任务创建边界。

本次 6 条；passed 6。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_plan_stage8::test_plan_service_returns_clarification_without_model_call` — passed
- `backend.tests.test_plan_stage8::test_plan_service_forwards_raw_requirements_and_hard_constraints` — passed
- `backend.tests.test_plan_stage8::test_plan_run_api_creates_explicit_trip_planning_job` — passed
- `backend.tests.test_plan_stage8::test_plan_run_api_is_friendly_wrapper_over_job_system` — passed
- `backend.tests.test_plan_stage8::test_plan_run_rejects_missing_reference_media_id` — passed
- `backend.tests.test_plan_stage8::test_photo_review_job_does_not_trigger_plan_by_default` — passed

</details>


## 事件日志与部署保护

### [test_events.py](../../tests/test_events.py)

事件输出。

本次 1 条；passed 1。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_events.EventTests::test_print_streaming_can_write_into_buffer_sink` — passed

</details>

### [test_trace.py](../../tests/test_trace.py)

JSONL 追踪与用户输入摘要截断。

本次 2 条；passed 2。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_trace.TraceTests::test_trace_event_records_truncated_user_input_summary` — passed
- `tests.test_trace.TraceTests::test_trace_event_writes_jsonl_record` — passed

</details>

### [test_demo_deployment.py](../../tests/test_demo_deployment.py)

并发预算、限额中间件和部署预检。

本次 5 条；passed 5。

<details>
<summary>展开全部用例名称与结果</summary>

- `tests.test_demo_deployment.BudgetTests::test_global_atomic_budget_shared_across_connections` — passed
- `tests.test_demo_deployment.MiddlewareTests::test_counted_attempts_block_but_get_and_brush_still_work` — passed
- `tests.test_demo_deployment.MiddlewareTests::test_database_failure_does_not_permit_paid_calls` — passed
- `tests.test_demo_deployment.PreflightTests::test_template_rejected_and_error_messages_hide_values` — passed
- `tests.test_demo_deployment.PreflightTests::test_valid_synthetic_configuration` — passed

</details>


## 后期建议转换与原图传递

### [test_retouch_advice.py](../../backend/tests/test_retouch_advice.py)

方向、范围、跳过项、来源及照片匹配。

本次 14 条；passed 14。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_retouch_advice::test_shadow_direction_and_no_substitution` — passed
- `backend.tests.test_retouch_advice::test_invalid_values_not_guessed[True]` — passed
- `backend.tests.test_retouch_advice::test_invalid_values_not_guessed[-10]` — passed
- `backend.tests.test_retouch_advice::test_invalid_values_not_guessed[-10 ~ -20]` — passed
- `backend.tests.test_retouch_advice::test_invalid_values_not_guessed[nan]` — passed
- `backend.tests.test_retouch_advice::test_invalid_values_not_guessed[inf]` — passed
- `backend.tests.test_retouch_advice::test_invalid_values_not_guessed[-101]` — passed
- `backend.tests.test_retouch_advice::test_invalid_values_not_guessed[None]` — passed
- `backend.tests.test_retouch_advice::test_neutral_direction_and_explicit_limits` — passed
- `backend.tests.test_retouch_advice::test_saved_result_provenance` — passed
- `backend.tests.test_retouch_advice::test_wrong_photo_batch_failed_or_unstructured_refused[ids0-succeeded-None]` — passed
- `backend.tests.test_retouch_advice::test_wrong_photo_batch_failed_or_unstructured_refused[ids1-succeeded-None]` — passed
- `backend.tests.test_retouch_advice::test_wrong_photo_batch_failed_or_unstructured_refused[ids2-failed-None]` — passed
- `backend.tests.test_retouch_advice::test_wrong_photo_batch_failed_or_unstructured_refused[ids3-succeeded-payload3]` — passed

</details>

### [test_retouch_source.py](../../backend/tests/test_retouch_source.py)

原图无重编码传递、预览回退和路径限制。

本次 5 条；passed 5。

<details>
<summary>展开全部用例名称与结果</summary>

- `backend.tests.test_retouch_source::test_retouch_exports_original_without_reencoding` — passed
- `backend.tests.test_retouch_source::test_retouch_falls_back_to_preview_for_unsupported_original` — passed
- `backend.tests.test_retouch_source::test_retouch_does_not_export_paths_outside_media_root` — passed
- `backend.tests.test_retouch_source::test_retouch_rejects_oversized_original` — passed
- `backend.tests.test_retouch_source::test_retouch_rejects_invalid_and_missing_ids` — passed

</details>

### [test_retouch_adjust_draft.py](../../tests/test_retouch_adjust_draft.py)

草稿版本、实际入参及审计字段隔离。

本次 3 条；passed 3。

<details>
<summary>展开全部用例名称与结果</summary>

- `test_retouch_adjust_draft.AdjustDraftTests.test_audit_fields_hidden_from_planner_and_bounded` — passed
- `test_retouch_adjust_draft.AdjustDraftTests.test_provenance_is_audit_only_and_exact_user_values_reach_pixels` — passed
- `test_retouch_adjust_draft.AdjustDraftTests.test_stale_revision_rejected_before_read_or_write` — passed

</details>


## 人物保护、笔刷与修图执行

### [test_retouch_portrait.py](../../tests/test_retouch_portrait.py)

阻止简化拆层、选区确认、原图及选区外像素保护。

本次 9 条；passed 9。

<details>
<summary>展开全部用例名称与结果</summary>

- `test_retouch_portrait.PortraitTests.test_body_intent_and_read_only_check_are_distinct` — passed
- `test_retouch_portrait.PortraitTests.test_corner_and_auto_split_blocked_before_any_processing` — passed
- `test_retouch_portrait.PortraitTests.test_direct_tool_stale_selection_blocks_before_provider` — passed
- `test_retouch_portrait.PortraitTests.test_mask_must_be_local_nonempty_and_current_size` — passed
- `test_retouch_portrait.PortraitTests.test_no_selection_saves_explanation_without_model_or_tool` — passed
- `test_retouch_portrait.PortraitTests.test_original_source_rejects_candidate_split_and_transformed_layers` — passed
- `test_retouch_portrait.PortraitTests.test_selected_body_edit_waits_for_confirmation_without_planner` — passed
- `test_retouch_portrait.PortraitTests.test_strict_composite_preserves_all_unselected_pixels` — passed
- `test_retouch_portrait.PortraitTests.test_transparent_candidate_not_written_or_adopted` — passed

</details>

### [test_retouch_brush.py](../../tests/test_retouch_brush.py)

涂抹 / 套索 / 擦除语义与透明缺口拦截。

本次 6 条；passed 6。

<details>
<summary>展开全部用例名称与结果</summary>

- `test_retouch_brush.BrushTests.test_paint_does_not_fill_unpainted_triangle` — passed
- `test_retouch_brush.BrushTests.test_protocol_defaults_and_invalid_controls` — passed
- `test_retouch_brush.BrushTests.test_resized_candidate_hole_in_selected_region_is_rejected` — passed
- `test_retouch_brush.BrushTests.test_single_click_width_and_empty_eraser` — passed
- `test_retouch_brush.BrushTests.test_subtract_removes_only_brush_and_keeps_base_immutable` — passed
- `test_retouch_brush.BrushTests.test_transparency_outside_selection_is_discarded` — passed

</details>

### [test_retouch_live.py](../../tests/test_retouch_live.py)

离线模拟模型请求、超时、事务失败及图像传输适配。

本次 12 条；passed 12。

<details>
<summary>展开全部用例名称与结果</summary>

- `test_retouch_live.LiveAdapterTests.test_invalid_image_fails_before_submission` — passed
- `test_retouch_live.LiveAdapterTests.test_original_jpeg_is_not_mislabeled_as_png` — passed
- `test_retouch_live.LiveAdapterTests.test_oversized_opaque_image_gets_transport_copy_at_same_size` — passed
- `test_retouch_live.LiveAdapterTests.test_oversized_transparent_image_preserves_alpha` — passed
- `test_retouch_live.LiveAdapterTests.test_planner_has_bounded_timeout_and_no_automatic_retry` — passed
- `test_retouch_live.LiveAdapterTests.test_supported_payload_keeps_single_output_and_native_size_syntax` — passed
- `test_retouch_live.LiveAdapterTests.test_unsupported_negative_prompt_rejected_before_network` — passed
- `test_retouch_live.PlannerFailureTests.test_actual_edit_instruction_still_reaches_planner` — passed
- `test_retouch_live.PlannerFailureTests.test_execution_check_does_not_plan_another_edit` — passed
- `test_retouch_live.PlannerFailureTests.test_rollback_does_not_read_expired_record_and_saves_failure` — passed
- `test_retouch_live.PlannerFailureTests.test_unclassified_failure_also_survives_rollback` — passed
- `test_retouch_live.PlannerFailureTests.test_wrapped_provider_errors_and_timeout_are_safe` — passed

</details>

### [test_retouch_output_limits.py](../../tests/test_retouch_output_limits.py)

上传与内部生成结果的不同大小限制。

本次 5 条；passed 5。

<details>
<summary>展开全部用例名称与结果</summary>

- `test_retouch_output_limits.OutputLimitTests.test_internal_limit_and_pixel_guard_still_apply` — passed
- `test_retouch_output_limits.OutputLimitTests.test_internal_lossless_result_keeps_size_bytes_and_alpha` — passed
- `test_retouch_output_limits.OutputLimitTests.test_oversize_upload_never_reaches_storage` — passed
- `test_retouch_output_limits.OutputLimitTests.test_rejected_result_reports_specific_error` — passed
- `test_retouch_output_limits.OutputLimitTests.test_upload_still_rejects_over_20_mib` — passed

</details>


## Agent 执行语义评测判定器

### [test_evaluate.py](../../evaluations/001-shadow-direction/test_evaluate.py)

反向参数、伪解释、擅自替代及非法调用识别。

本次 6 条；passed 6。

<details>
<summary>展开全部用例名称与结果</summary>

- `test_evaluate.EvaluationTests.test_direction_and_neutral_shadow_cannot_pass` — passed
- `test_evaluate.EvaluationTests.test_explanation_without_correct_execution_does_not_pass` — passed
- `test_evaluate.EvaluationTests.test_historical_successful_tool_is_semantic_failure` — passed
- `test_evaluate.EvaluationTests.test_missing_duplicate_unknown_and_out_of_range_calls_fail` — passed
- `test_evaluate.EvaluationTests.test_skipped_without_reason_does_not_pass` — passed
- `test_evaluate.EvaluationTests.test_synthetic_positive_control_is_only_a_judge_test` — passed

</details>


## 浏览器产品流程

### [product-demo.spec.ts](../../frontend/tests/product-demo.spec.ts)

分析、修图、素材、学习、规划、导出与异常反馈。

本次 8 条；passed 8。

<details>
<summary>展开全部用例名称与结果</summary>

- `original three-column analysis → assets → learning → history` — passed
- `original editor sends and confirms round-cat preset, saves into asset library` — passed
- `original planning form generates West Lake variants and supports adoption` — passed
- `unsupported generation shows feedback and preserves canvas` — passed
- `static pages and editor deep link work without backend` — passed
- `original sliders apply to actual pixels, undo and export ZIP work` — passed
- `style selection affects preset advice and reset leaves real-mode caches untouched` — passed
- `unsupported preferences and destinations do not receive unrelated fixture results` — passed

</details>

