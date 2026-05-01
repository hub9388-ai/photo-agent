from __future__ import annotations

import json
import mimetypes
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Callable

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.ExifTags import IFD, TAGS

from app.core.settings import Settings, get_settings
from app.schemas.media import MediaAsset
from app.schemas.response import UploadMediaResponse, upload_media_response_from_asset


ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
RAW_IMAGE_EXTS = {".arw", ".cr2", ".cr3", ".dng", ".nef", ".orf", ".raf", ".rw2"}
SAFE_EXIF_TAGS = {
    "Make",
    "Model",
    "LensModel",
    "FocalLength",
    "FNumber",
    "ExposureTime",
    "ISOSpeedRatings",
    "PhotographicSensitivity",
    "DateTimeOriginal",
    "DateTimeDigitized",
    "DateTime",
    "Orientation",
}
CHUNK_SIZE = 1024 * 1024


class MediaStoreError(Exception):
    status_code = 400


class UnsupportedMediaTypeError(MediaStoreError):
    status_code = 415


class MediaTooLargeError(MediaStoreError):
    status_code = 413


class MediaProcessingError(MediaStoreError):
    status_code = 400


class MediaNotFoundError(MediaStoreError):
    status_code = 404


@dataclass(frozen=True)
class MediaStore:
    root: Path
    max_upload_bytes: int = 25 * 1024 * 1024
    preview_max_side: int = 1600
    thumbnail_max_side: int = 320
    preview_quality: int = 85
    thumbnail_quality: int = 75

    @classmethod
    def from_settings(cls, settings: Settings) -> MediaStore:
        return cls(
            root=settings.media_root,
            max_upload_bytes=settings.max_upload_bytes,
        )

    @property
    def originals_dir(self) -> Path:
        return self.root / "originals"

    @property
    def previews_dir(self) -> Path:
        return self.root / "previews"

    @property
    def thumbnails_dir(self) -> Path:
        return self.root / "thumbnails"

    @property
    def records_dir(self) -> Path:
        return self.root / "records"

    def save_and_prepare_sync(self, upload: UploadFile) -> UploadMediaResponse:
        file_name = self._sanitize_filename(upload.filename)
        content_type = self._resolve_content_type(file_name, upload.content_type)
        suffix = self._validate_media_type(file_name, content_type)
        media_id = f"media_{uuid.uuid4().hex}"

        self._ensure_directories()
        original_path = self.originals_dir / f"{media_id}{suffix}"
        preview_path = self.previews_dir / f"{media_id}.jpg"
        thumbnail_path = self.thumbnails_dir / f"{media_id}.jpg"
        record_path = self.records_dir / f"{media_id}.json"

        try:
            size_bytes = self._write_upload(upload.file, original_path)
            metadata = self._prepare_images(
                original_path=original_path,
                preview_path=preview_path,
                thumbnail_path=thumbnail_path,
                file_name=file_name,
                content_type=content_type,
                size_bytes=size_bytes,
            )
        except MediaStoreError:
            self._cleanup_paths(original_path, preview_path, thumbnail_path, record_path)
            raise
        except (OSError, UnidentifiedImageError) as exc:
            self._cleanup_paths(original_path, preview_path, thumbnail_path, record_path)
            raise MediaProcessingError(f"Could not process uploaded image: {exc}") from exc

        asset = MediaAsset(
            id=media_id,
            kind="photo",
            filename=file_name,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_uri=str(original_path),
            preview_url=f"/media/previews/{media_id}.jpg",
            metadata=metadata,
            status="ready",
        )
        record_path.write_text(
            json.dumps(asset.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.to_upload_response(asset)

    def to_upload_response(self, asset: MediaAsset) -> UploadMediaResponse:
        return upload_media_response_from_asset(asset)

    def register_existing_file(
        self,
        path: Path,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> MediaAsset:
        resolved = path.resolve(strict=False)
        if not resolved.exists() or not resolved.is_file():
            raise MediaNotFoundError(f"Media file not found: {path}")

        self._ensure_directories()
        suffix = resolved.suffix.lower()
        content_type = self._resolve_content_type(resolved.name, None)
        media_id = f"media_{uuid.uuid4().hex}"
        asset = MediaAsset(
            id=media_id,
            kind=self._infer_media_kind(suffix, content_type),
            filename=resolved.name,
            content_type=content_type,
            size_bytes=resolved.stat().st_size,
            storage_uri=str(resolved),
            preview_url=None,
            metadata=metadata or {},
            status="ready",
        )
        record_path = self.records_dir / f"{media_id}.json"
        record_path.write_text(
            json.dumps(asset.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return asset

    def get(self, media_id: str) -> MediaAsset:
        record_path = self.records_dir / f"{media_id}.json"
        if not record_path.exists():
            raise MediaNotFoundError(f"Media not found: {media_id}")
        try:
            return MediaAsset.model_validate_json(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MediaProcessingError(f"Could not read media record: {media_id}") from exc

    def prepare_legacy_media_items(
        self,
        media_ids: list[str],
        legacy_prepare_media_items: Callable[..., tuple[list[dict], list[Path], bool]],
        *,
        sink: Any = None,
    ) -> tuple[list[dict], int, bool]:
        assets = [self.get(media_id) for media_id in media_ids]
        analysis_paths = [self._analysis_path_for_asset(asset) for asset in assets]
        asset_by_path = {
            str(path.resolve(strict=False)): asset
            for asset, path in zip(assets, analysis_paths, strict=False)
        }

        media_items, expanded_paths, is_batch = legacy_prepare_media_items(
            analysis_paths,
            sink=sink,
        )

        for item in media_items:
            item_path = Path(item.get("path", ""))
            asset = asset_by_path.get(str(item_path.resolve(strict=False)))
            if asset is None:
                continue
            item["media_id"] = asset.id
            item["label"] = asset.filename
            item["original_storage_uri"] = asset.storage_uri
            if item_path == self._preview_path_for_asset(asset):
                item["source_label"] = f"{asset.filename}（上传预览图）"
                preview_note = str(item.get("preview_note") or "").strip()
                upload_note = "使用上传阶段生成的预览图供模型分析"
                item["preview_note"] = (
                    f"{upload_note}；{preview_note}" if preview_note else upload_note
                )

        return media_items, len(expanded_paths), is_batch

    def _ensure_directories(self) -> None:
        for directory in (
            self.originals_dir,
            self.previews_dir,
            self.thumbnails_dir,
            self.records_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, file_name: str | None) -> str:
        name = Path(file_name or "").name.strip()
        if not name:
            raise UnsupportedMediaTypeError("Uploaded file must have a filename.")
        return name

    def _resolve_content_type(self, file_name: str, content_type: str | None) -> str:
        if content_type and content_type != "application/octet-stream":
            return content_type.lower()
        guessed, _ = mimetypes.guess_type(file_name)
        return (guessed or "application/octet-stream").lower()

    def _validate_media_type(self, file_name: str, content_type: str) -> str:
        suffix = Path(file_name).suffix.lower()
        if suffix == ".jpeg":
            suffix = ".jpg"
        if suffix not in ALLOWED_IMAGE_EXTS:
            allowed = ", ".join(sorted(ALLOWED_IMAGE_EXTS))
            raise UnsupportedMediaTypeError(f"Unsupported media extension. Allowed: {allowed}.")
        if content_type not in ALLOWED_IMAGE_TYPES:
            allowed = ", ".join(sorted(ALLOWED_IMAGE_TYPES))
            raise UnsupportedMediaTypeError(f"Unsupported media type. Allowed: {allowed}.")
        return suffix

    def _write_upload(self, file_obj: BinaryIO, destination: Path) -> int:
        total = 0
        try:
            file_obj.seek(0)
        except (AttributeError, OSError):
            pass

        with destination.open("wb") as output:
            while True:
                chunk = file_obj.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > self.max_upload_bytes:
                    raise MediaTooLargeError(
                        f"Uploaded file exceeds {self.max_upload_bytes} bytes."
                    )
                output.write(chunk)

        return total

    def _prepare_images(
        self,
        *,
        original_path: Path,
        preview_path: Path,
        thumbnail_path: Path,
        file_name: str,
        content_type: str,
        size_bytes: int,
    ) -> dict[str, Any]:
        with Image.open(original_path) as image:
            image.load()
            image = ImageOps.exif_transpose(image)
            metadata = self._extract_metadata(
                image=image,
                file_name=file_name,
                content_type=content_type,
                size_bytes=size_bytes,
            )

            preview = self._as_rgb(image.copy())
            preview.thumbnail(
                (self.preview_max_side, self.preview_max_side),
                Image.Resampling.LANCZOS,
            )
            preview.save(preview_path, "JPEG", quality=self.preview_quality, optimize=True)

            thumbnail = self._as_rgb(image.copy())
            thumbnail.thumbnail(
                (self.thumbnail_max_side, self.thumbnail_max_side),
                Image.Resampling.LANCZOS,
            )
            thumbnail.save(
                thumbnail_path,
                "JPEG",
                quality=self.thumbnail_quality,
                optimize=True,
            )

        metadata["preview"] = {
            "width": preview.width,
            "height": preview.height,
            "url": f"/media/previews/{preview_path.stem}.jpg",
        }
        metadata["thumbnail"] = {
            "width": thumbnail.width,
            "height": thumbnail.height,
            "url": f"/media/thumbnails/{thumbnail_path.stem}.jpg",
        }
        return metadata

    def _extract_metadata(
        self,
        *,
        image: Image.Image,
        file_name: str,
        content_type: str,
        size_bytes: int,
    ) -> dict[str, Any]:
        exif_payload: dict[str, Any] = {}
        gps_redacted = False

        exif = image.getexif()
        gps_redacted = "GPSInfo" in {TAGS.get(tag_id, str(tag_id)) for tag_id in exif.keys()}
        self._collect_safe_exif_tags(exif.items(), exif_payload)
        try:
            self._collect_safe_exif_tags(exif.get_ifd(IFD.Exif).items(), exif_payload)
        except (KeyError, TypeError, ValueError):
            pass

        return {
            "fileName": file_name,
            "mimeType": content_type,
            "sizeBytes": size_bytes,
            "width": image.width,
            "height": image.height,
            "format": image.format,
            "mode": image.mode,
            "hasExif": bool(exif),
            "exif": exif_payload,
            "privacy": {"gpsRedacted": gps_redacted},
        }

    def _collect_safe_exif_tags(
        self,
        items: Any,
        exif_payload: dict[str, Any],
    ) -> None:
        for tag_id, value in items:
            tag_name = TAGS.get(tag_id, str(tag_id))
            if tag_name == "GPSInfo":
                continue
            if tag_name not in SAFE_EXIF_TAGS:
                continue
            exif_payload[tag_name] = self._json_safe(value)

    def _as_rgb(self, image: Image.Image) -> Image.Image:
        if image.mode == "RGB":
            return image
        if image.mode in {"RGBA", "LA"}:
            background = Image.new("RGB", image.size, (255, 255, 255))
            alpha = image.getchannel("A")
            background.paste(image.convert("RGB"), mask=alpha)
            return background
        return image.convert("RGB")

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, bytes):
            return f"<bytes:{len(value)}>"
        if isinstance(value, tuple):
            return [self._json_safe(item) for item in value]
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        try:
            return float(value)
        except (TypeError, ValueError):
            return str(value)

    def _cleanup_paths(self, *paths: Path) -> None:
        for path in paths:
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
            except OSError:
                continue

    def _analysis_path_for_asset(self, asset: MediaAsset) -> Path:
        preview_path = self._preview_path_for_asset(asset)
        if preview_path.exists():
            return preview_path
        storage_path = Path(asset.storage_uri)
        if storage_path.exists():
            return storage_path
        raise MediaNotFoundError(f"Media file not found: {asset.id}")

    def _preview_path_for_asset(self, asset: MediaAsset) -> Path:
        return self.previews_dir / f"{asset.id}.jpg"

    def _infer_media_kind(self, suffix: str, content_type: str | None) -> str:
        if suffix in RAW_IMAGE_EXTS:
            return "raw"
        if content_type and content_type.startswith("image/"):
            return "photo"
        if content_type and content_type.startswith("video/"):
            return "video"
        return "other"


def get_media_store() -> MediaStore:
    return MediaStore.from_settings(get_settings())
