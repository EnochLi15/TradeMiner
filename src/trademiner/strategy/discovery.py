from __future__ import annotations

import ast
import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StrategyMetadata:
    strategy_id: str
    name: str
    description: str
    params: dict[str, Any]


@dataclass(frozen=True)
class StrategySource:
    metadata: StrategyMetadata
    file_path: Path
    source_hash: str
    source_snapshot: str
    git_commit: str | None
    git_dirty: bool | None


def discover_strategy_sources(paths: list[Path]) -> list[StrategySource]:
    strategy_files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            strategy_files.append(path)
        elif path.is_dir():
            strategy_files.extend(sorted(path.rglob("*.py")))

    return [
        read_strategy_source(path)
        for path in sorted(strategy_files)
        if _is_strategy_source_file(path)
    ]


def discover_default_source_strategies() -> list[StrategySource]:
    return discover_strategy_sources([default_source_strategy_dir()])


def default_source_strategy_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "strategies"


def read_strategy_source(path: Path) -> StrategySource:
    source_snapshot = path.read_text()
    metadata = _parse_strategy_metadata(path, source_snapshot)
    git_commit, git_dirty = _git_metadata(path)
    return StrategySource(
        metadata=metadata,
        file_path=path,
        source_hash=hashlib.sha256(source_snapshot.encode()).hexdigest(),
        source_snapshot=source_snapshot,
        git_commit=git_commit,
        git_dirty=git_dirty,
    )


def _parse_strategy_metadata(path: Path, source_snapshot: str) -> StrategyMetadata:
    tree = ast.parse(source_snapshot, filename=str(path))
    raw_metadata: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "STRATEGY":
                    raw_metadata = ast.literal_eval(node.value)
                    break

    strategy_id = str(raw_metadata.get("id") or path.stem)
    name = str(raw_metadata.get("name") or strategy_id)
    description = str(raw_metadata.get("description") or "")
    params = raw_metadata.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError(f"Strategy params must be a dict in {path}")

    return StrategyMetadata(
        strategy_id=strategy_id,
        name=name,
        description=description,
        params=params,
    )


def _is_strategy_source_file(path: Path) -> bool:
    return path.suffix == ".py" and not path.name.startswith("_")


def _git_metadata(path: Path) -> tuple[str | None, bool | None]:
    worktree = _run_git(path.parent, ["rev-parse", "--show-toplevel"])
    if worktree is None:
        return None, None
    commit = _run_git(path.parent, ["rev-parse", "HEAD"])
    status = _run_git(path.parent, ["status", "--porcelain", "--", str(path)])
    return commit, bool(status)


def _run_git(cwd: Path, args: list[str]) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()
