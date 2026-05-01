from __future__ import annotations

from app.core.settings import candidate_env_file_paths


def test_candidate_env_files_include_repo_root_before_backend(tmp_path) -> None:
    repo_root = tmp_path
    backend_dir = repo_root / "backend"
    backend_dir.mkdir()

    for relative_path in (".env", ".env.local", "model.env", "backend/.env"):
        path = repo_root / relative_path
        path.write_text("PHOTO_DEBUG=false\n", encoding="utf-8")

    paths = candidate_env_file_paths(repo_root=repo_root, cwd=backend_dir)
    relative_paths = [path.relative_to(repo_root).as_posix() for path in paths]

    assert relative_paths == [".env", ".env.local", "model.env", "backend/.env"]
