from __future__ import annotations

import hashlib
import shutil
from collections import Counter
from pathlib import Path

from file_compare_app.core.models import Change
from file_compare_app.core.orchestrator import compare_files
from file_compare_app.core.type_detection import detect_file_kind
from file_compare_app.registry.models import FileVersion, MonitoringFileInfo, MonitoringSummary, WatchedFile
from file_compare_app.registry.repository import RegistryRepository


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RegistryMonitor:
    def __init__(self, repository: RegistryRepository) -> None:
        self.repository = repository

    def add_file(self, node_id: int, path: Path | str, label: str | None = None) -> WatchedFile:
        file_path = Path(path)
        digest = file_sha256(file_path)
        watched = self.repository.create_watched_file(
            node_id=node_id,
            file_path=str(file_path),
            label=label or file_path.name,
            file_kind=detect_file_kind(file_path),
            baseline_hash=digest,
            last_hash=digest,
        )
        snapshot_path = self._store_snapshot(watched, file_path, 1)
        self.repository.create_file_version(
            watched_file_id=watched.id,
            version_number=1,
            snapshot_path=str(snapshot_path),
            sha256=digest,
            size_bytes=file_path.stat().st_size,
        )
        self.repository.create_event(
            node_id=node_id,
            watched_file_id=watched.id,
            event_type="baseline",
            message=f"Базовая версия v1 сохранена: {file_path.name}",
        )
        return watched

    def add_file_pair(
        self,
        node_id: int,
        before_path: Path | str,
        after_path: Path | str,
        label: str | None = None,
    ) -> WatchedFile:
        before_file = Path(before_path)
        watched = self.add_file(node_id, before_file, label=label or before_file.name)
        return self.add_next_version(watched.id, after_path)

    def add_next_version(self, watched_file_id: int, path: Path | str) -> WatchedFile:
        watched = self.repository.get_watched_file(watched_file_id)
        file_path = Path(path)
        digest = file_sha256(file_path)
        latest = self._ensure_latest_version(watched, file_path, digest)
        status = "changed" if digest != latest.sha256 else "ok"
        updated = self.repository.update_watched_file_status(
            watched.id,
            digest,
            status,
            file_path=str(file_path),
        )
        if status == "ok":
            self.repository.create_event(
                watched.node_id,
                watched.id,
                "checked",
                message=f"Новая версия совпадает с v{latest.version_number}: {file_path.name}",
            )
            return updated

        self._record_changed_version(updated, file_path, digest, latest)
        return updated

    def check_file(self, watched_file_id: int) -> WatchedFile:
        watched = self.repository.get_watched_file(watched_file_id)
        file_path = Path(watched.file_path)
        if not file_path.exists():
            updated = self.repository.update_watched_file_status(
                watched.id,
                watched.last_hash,
                "missing",
                "Файл не найден",
            )
            self.repository.create_event(
                watched.node_id,
                watched.id,
                "missing",
                message=f"Файл не найден: {file_path}",
            )
            return updated
        try:
            digest = file_sha256(file_path)
        except OSError as exc:
            updated = self.repository.update_watched_file_status(
                watched.id,
                watched.last_hash,
                "error",
                exc.__class__.__name__,
            )
            self.repository.create_event(watched.node_id, watched.id, "error", message=exc.__class__.__name__)
            return updated

        latest = self._ensure_latest_version(watched, file_path, digest)
        status = "changed" if digest != latest.sha256 else "ok"
        updated = self.repository.update_watched_file_status(watched.id, digest, status)
        if status == "ok":
            self.repository.create_event(
                watched.node_id,
                watched.id,
                "checked",
                message=f"Без изменений: v{latest.version_number}, {file_path.name}",
            )
            return updated

        self._record_changed_version(updated, file_path, digest, latest)
        return updated

    def check_node(self, node_id: int, include_children: bool = True) -> list[WatchedFile]:
        node_ids = self.repository.list_descendant_ids(node_id) if include_children else [node_id]
        checked: list[WatchedFile] = []
        for current_node_id in node_ids:
            for watched in self.repository.list_watched_files(current_node_id):
                checked.append(self.check_file(watched.id))
        return checked

    def build_node_summary(self, node_id: int) -> MonitoringSummary:
        files = self.repository.list_watched_files_for_tree(node_id)
        items: list[MonitoringFileInfo] = []
        status_counts: Counter[str] = Counter({"ok": 0, "changed": 0, "missing": 0, "error": 0})
        for watched in files:
            latest: FileVersion | None = None
            try:
                latest = self.repository.get_latest_file_version(watched.id)
            except KeyError:
                pass
            status_counts[watched.status] += 1
            items.append(
                MonitoringFileInfo(
                    node_path=self.repository.node_path(watched.node_id),
                    watched_file=watched,
                    latest_version=latest,
                    last_event=self.repository.get_last_event_for_watched_file(watched.id),
                )
            )
        return MonitoringSummary(
            node_id=node_id,
            total_files=len(files),
            status_counts=status_counts,
            files=items,
        )

    def _ensure_latest_version(self, watched: WatchedFile, file_path: Path, digest: str) -> FileVersion:
        try:
            return self.repository.get_latest_file_version(watched.id)
        except KeyError:
            snapshot_path = self._store_snapshot(watched, file_path, 1)
            return self.repository.create_file_version(
                watched_file_id=watched.id,
                version_number=1,
                snapshot_path=str(snapshot_path),
                sha256=digest,
                size_bytes=file_path.stat().st_size,
            )

    def _store_snapshot(self, watched: WatchedFile, source_path: Path, version_number: int) -> Path:
        version_dir = self.repository.snapshot_root() / f"node_{watched.node_id}" / f"file_{watched.id}"
        version_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = version_dir / f"v{version_number:04d}_{_safe_filename(source_path.name)}"
        shutil.copy2(source_path, snapshot_path)
        return snapshot_path

    def _record_changed_version(
        self,
        watched: WatchedFile,
        file_path: Path,
        digest: str,
        latest: FileVersion,
    ) -> None:
        try:
            result = compare_files(Path(latest.snapshot_path), file_path)
        except Exception as exc:
            self.repository.update_watched_file_status(
                watched.id,
                digest,
                "error",
                str(exc),
            )
            self.repository.create_event(
                watched.node_id,
                watched.id,
                "error",
                message=(
                    f"Не удалось сравнить версии {watched.label}: "
                    f"v{latest.version_number} -> v{latest.version_number + 1}; "
                    f"{exc.__class__.__name__}: {exc}"
                ),
            )
            return
        risk_changes = [change for change in result.changes if change.severity == "risk"]
        next_version_number = latest.version_number + 1
        snapshot_path = self._store_snapshot(watched, file_path, next_version_number)
        self.repository.create_file_version(
            watched_file_id=watched.id,
            version_number=next_version_number,
            snapshot_path=str(snapshot_path),
            sha256=digest,
            size_bytes=file_path.stat().st_size,
            change_count=len(result.changes),
        )
        self.repository.create_event(
            watched.node_id,
            watched.id,
            "changed",
            change_count=len(result.changes),
            risk_count=len(risk_changes),
            risk_summary=_format_risk_summary(risk_changes),
            message=(
                f"Изменен {watched.label}: v{latest.version_number} -> v{next_version_number}; "
                f"изменений: {len(result.changes)}; {_format_change_preview(result.changes)}"
            ),
        )


def _safe_filename(name: str) -> str:
    safe = "".join(character if character.isalnum() or character in ".-_" else "_" for character in name)
    return safe or "file"


def _format_change_preview(changes: list[Change]) -> str:
    if not changes:
        return "структурных изменений не найдено"
    first = changes[0]
    before = _shorten(first.before)
    after = _shorten(first.after)
    key = first.notes if first.notes not in {"line diff", "Kaspersky KLP policy profile"} else ""
    if before and after:
        if key:
            return f"{key}: {before} -> {key}: {after}"
        return f"{before} -> {after}"
    if after:
        return f"добавлено: {after}"
    if before:
        return f"удалено: {before}"
    return first.notes or first.change_type


def _format_risk_summary(changes: list[Change]) -> str:
    if not changes:
        return ""
    previews: list[str] = []
    for change in changes[:3]:
        preview = change.after or change.before or change.notes or change.change_type
        previews.append(_shorten(preview, 90))
    if len(changes) > 3:
        previews.append(f"еще {len(changes) - 3}")
    return "; ".join(previews)


def _shorten(value: str, limit: int = 120) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"
