import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

import photo_v1
import photo_v4
from photo_events import BufferEventSink
from photo_storage import (
    atomic_write_json,
    build_asset_index_document,
    cleanup_json_cache,
    migrate_asset_index_payload,
    migrate_profile_payload,
    read_json,
    resolve_asset_index_dir,
    resolve_profile_path,
)


def make_workspace_temp_dir() -> Path:
    base_dir = Path.cwd() / ".test_artifacts"
    base_dir.mkdir(exist_ok=True)
    temp_dir = base_dir / uuid4().hex
    temp_dir.mkdir()
    return temp_dir


class StorageTests(unittest.TestCase):
    def test_migrate_profile_payload_supports_legacy_flat_json(self) -> None:
        defaults = {
            "device_info": "",
            "skill_level": "",
            "lesson_history": [],
        }
        payload = {
            "device_info": "Nikon Z30",
            "skill_level": "进阶",
        }

        migrated = migrate_profile_payload(payload, defaults)

        self.assertEqual(migrated["device_info"], "Nikon Z30")
        self.assertEqual(migrated["skill_level"], "进阶")
        self.assertEqual(migrated["lesson_history"], [])

    def test_asset_index_document_redacts_absolute_paths_and_rehydrates_on_load(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            cache_path = temp_dir / "sample.json"
            index = {
                "project_root": r"C:\Users\25320\Pictures\cat",
                "project_name": "cat",
                "assets": [
                    {
                        "file_name": "CAT_1.jpg",
                        "relative_path": "CAT_1.jpg",
                        "absolute_path": r"C:\Users\25320\Pictures\cat\CAT_1.jpg",
                    }
                ],
                "duplicate_groups": [],
                "highlight_ids": [],
                "reject_ids": [],
                "scene_groups": [],
                "stats": {},
                "suggestions": {},
            }

            atomic_write_json(cache_path, build_asset_index_document(index))
            stored_payload = read_json(cache_path)
            loaded_index = migrate_asset_index_payload(stored_payload)

            self.assertIsNotNone(stored_payload)
            self.assertNotIn("absolute_path", stored_payload["index"]["assets"][0])
            self.assertEqual(
                loaded_index["assets"][0]["absolute_path"],
                r"C:\Users\25320\Pictures\cat\CAT_1.jpg",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_cleanup_json_cache_keeps_latest_files(self) -> None:
        temp_path = make_workspace_temp_dir()
        try:
            for idx in range(3):
                file_path = temp_path / f"cache_{idx}.json"
                atomic_write_json(file_path, {"idx": idx})
                file_path.touch()

            cleanup_json_cache(temp_path, keep=2)
            remaining = sorted(path.name for path in temp_path.glob("*.json"))

            self.assertEqual(len(remaining), 2)
        finally:
            shutil.rmtree(temp_path, ignore_errors=True)

    def test_resolve_profile_path_copies_legacy_profile_into_user_data_dir(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            data_dir = temp_dir / "data_home"
            legacy_path = temp_dir / "user_profile.json"
            atomic_write_json(
                legacy_path,
                {"device_info": "Nikon Z30", "skill_level": "进阶"},
            )

            with patch.dict("os.environ", {"PHOTO_AGENT_DATA_DIR": str(data_dir)}, clear=False):
                resolved = resolve_profile_path(legacy_path)

            self.assertEqual(resolved, data_dir / "user_profile.json")
            self.assertTrue(resolved.exists())
            self.assertEqual(read_json(resolved)["device_info"], "Nikon Z30")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_resolve_asset_index_dir_copies_legacy_cache_files(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            data_dir = temp_dir / "data_home"
            legacy_dir = temp_dir / "asset_indexes"
            legacy_dir.mkdir()
            atomic_write_json(legacy_dir / "sample.json", {"project_name": "cat"})

            with patch.dict("os.environ", {"PHOTO_AGENT_DATA_DIR": str(data_dir)}, clear=False):
                resolved = resolve_asset_index_dir(legacy_dir)

            self.assertEqual(resolved, data_dir / "asset_indexes")
            self.assertTrue((resolved / "sample.json").exists())
            self.assertEqual(read_json(resolved / "sample.json")["project_name"], "cat")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class AssetIndexSinkTests(unittest.TestCase):
    def test_index_project_assets_reports_progress_to_sink(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            data_dir = temp_dir / "data_home"
            image_path = temp_dir / "CAT_1.jpg"
            Image.new("RGB", (32, 32), color=(220, 180, 120)).save(image_path)
            sink = BufferEventSink()
            with patch.dict("os.environ", {"PHOTO_AGENT_DATA_DIR": str(data_dir)}, clear=False):
                index = photo_v4.index_project_assets(
                    [image_path],
                    intent={},
                    profile=photo_v4.ensure_asset_profile_fields(dict(photo_v1.DEFAULT_PROFILE)),
                    sink=sink,
                )

            self.assertEqual(index["project_name"], image_path.parent.name)
            self.assertTrue(any("Building project index" in item for item in sink.progress_updates))
            self.assertTrue(any("Rebuild progress: 1/1" in item for item in sink.progress_updates))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_index_project_assets_reuses_cached_records_on_second_run(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            data_dir = temp_dir / "data_home"
            image_paths = []
            for idx in range(2):
                image_path = temp_dir / f"CAT_{idx + 1}.jpg"
                Image.new("RGB", (48, 48), color=(220 - idx * 20, 180, 120)).save(image_path)
                image_paths.append(image_path)

            profile = photo_v4.ensure_asset_profile_fields(dict(photo_v1.DEFAULT_PROFILE))
            with patch.dict("os.environ", {"PHOTO_AGENT_DATA_DIR": str(data_dir)}, clear=False):
                first_index = photo_v4.index_project_assets(
                    image_paths,
                    intent={},
                    profile=profile,
                    sink=BufferEventSink(),
                )
                cache_path = photo_v4.save_project_index(first_index)

                sink = BufferEventSink()
                second_index = photo_v4.index_project_assets(
                    image_paths,
                    intent={},
                    profile=profile,
                    sink=sink,
                )
                rendered = photo_v4.render_index_response(second_index, cache_path)

            self.assertEqual(second_index["stats"]["cache_hit_count"], 2)
            self.assertEqual(second_index["stats"]["rebuilt_asset_count"], 0)
            self.assertEqual(second_index["stats"]["parallel_workers"], 1)
            self.assertTrue(any("Cache reuse: 2/2" in item for item in sink.progress_updates))
            self.assertIn("缓存复用：2", rendered)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_index_project_assets_uses_parallel_rebuild_for_multiple_files(self) -> None:
        temp_dir = make_workspace_temp_dir()
        try:
            data_dir = temp_dir / "data_home"
            image_paths = []
            for idx in range(3):
                image_path = temp_dir / f"CAT_{idx + 1}.jpg"
                Image.new("RGB", (64, 64), color=(120 + idx * 20, 160, 200)).save(image_path)
                image_paths.append(image_path)

            sink = BufferEventSink()
            with patch.dict("os.environ", {"PHOTO_AGENT_DATA_DIR": str(data_dir)}, clear=False):
                index = photo_v4.index_project_assets(
                    image_paths,
                    intent={},
                    profile=photo_v4.ensure_asset_profile_fields(dict(photo_v1.DEFAULT_PROFILE)),
                    sink=sink,
                )

            self.assertEqual(index["stats"]["rebuilt_asset_count"], 3)
            self.assertGreaterEqual(index["stats"]["parallel_workers"], 2)
            self.assertTrue(
                any("Rebuilding visual and metadata features" in item for item in sink.progress_updates)
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
