"""运行时资源路径解析器。

集中管理仓库根目录发现、规范路径构建，以及从规范目录回退到当前过渡目录的查找逻辑。
未来迁移到 ``wzry_ai.utils`` 时，只需移动本模块即可，调用方 API 保持不变。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple, Union


PathLike = Union[str, Path]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


class RuntimePathResolver:
    """单一运行时路径权威。"""

    _DOC_FALLBACKS: Dict[Tuple[str, ...], Tuple[Tuple[str, ...], ...]] = {
        ("project-knowledge", "AGENTS.md"): (("AGENTS.md",),),
        ("operator", "使用文档.txt"): (("使用文档.txt",),),
    }

    def __init__(self, start: Optional[PathLike] = None):
        self._repo_root = self.discover_repo_root(start or __file__)

    @classmethod
    def discover_repo_root(cls, start: PathLike) -> Path:
        """从给定锚点向上发现仓库根目录。"""
        current = Path(start).resolve()
        if current.is_file():
            current = current.parent

        for candidate in (current, *current.parents):
            if cls._is_repo_root(candidate):
                return candidate

        raise RuntimeError(f"无法从 {start!r} 发现仓库根目录")

    @classmethod
    def _is_repo_root(cls, candidate: Path) -> bool:
        has_legacy_packages = (candidate / "config").is_dir() and (
            candidate / "utils"
        ).is_dir()
        has_canonical_code = (candidate / "src" / "wzry_ai").is_dir()
        has_runtime_boundaries = (candidate / "models").is_dir() and (
            candidate / "data"
        ).is_dir()
        has_entrypoint = (candidate / "Master_Auto.py").is_file()
        has_ledger = (
            candidate / ".sisyphus" / "task-1-modernization-ledger.json"
        ).is_file()
        return (
            (has_legacy_packages or has_canonical_code)
            and has_runtime_boundaries
            and (has_entrypoint or has_ledger)
        )

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    def code_root(self) -> Path:
        return self.repo_root / "src" / "wzry_ai"

    def build_canonical_path(self, boundary: str, *parts: PathLike) -> Path:
        """构建冻结后的规范路径，不做过渡回退。"""
        roots = {
            "templates": self.repo_root / "assets" / "templates",
            "hero_skills": self.repo_root / "assets" / "templates" / "hero_skills",
            "heroes": self.repo_root / "assets" / "heroes",
            "models": self.repo_root / "models",
            "data": self.repo_root / "data",
            "docs": self.repo_root / "docs",
        }
        try:
            root = roots[boundary]
        except KeyError as exc:
            raise ValueError(f"不支持的资源边界: {boundary}") from exc
        return self._join(root, *parts)

    def templates_dir(self, preferred_root: Optional[PathLike] = None) -> Path:
        return self._resolve_dir(
            self.build_canonical_path("templates"),
            (self.repo_root / "image",),
            preferred_root=preferred_root,
        )

    def heroes_dir(self, preferred_root: Optional[PathLike] = None) -> Path:
        return self._resolve_dir(
            self.build_canonical_path("heroes"),
            (self.repo_root / "hero",),
            preferred_root=preferred_root,
        )

    def hero_skills_dir(self, preferred_root: Optional[PathLike] = None) -> Path:
        return self._resolve_dir(
            self.build_canonical_path("hero_skills"),
            (self.repo_root / "hero_skills",),
            preferred_root=preferred_root,
        )

    def models_dir(self) -> Path:
        return self.build_canonical_path("models")

    def data_dir(self) -> Path:
        return self.build_canonical_path("data")

    def docs_dir(self) -> Path:
        return self.build_canonical_path("docs")

    def resolve_template(
        self, *parts: PathLike, preferred_root: Optional[PathLike] = None
    ) -> Path:
        return self._resolve_file(
            self.build_canonical_path("templates", *parts),
            (self.repo_root / "image",),
            parts,
            preferred_root=preferred_root,
        )

    def resolve_hero_portrait(
        self, *parts: PathLike, preferred_root: Optional[PathLike] = None
    ) -> Path:
        return self._resolve_file(
            self.build_canonical_path("heroes", *parts),
            (self.repo_root / "hero",),
            parts,
            preferred_root=preferred_root,
        )

    def resolve_hero_skill(
        self, *parts: PathLike, preferred_root: Optional[PathLike] = None
    ) -> Path:
        return self._resolve_file(
            self.build_canonical_path("hero_skills", *parts),
            (self.repo_root / "hero_skills",),
            parts,
            preferred_root=preferred_root,
        )

    def resolve_model(self, *parts: PathLike) -> Path:
        return self.build_canonical_path("models", *parts)

    def resolve_data(self, *parts: PathLike) -> Path:
        return self.build_canonical_path("data", *parts)

    def resolve_doc(self, *parts: PathLike) -> Path:
        normalized_parts = self._normalize_parts(parts)
        canonical = self.build_canonical_path("docs", *normalized_parts)
        if canonical.exists():
            return canonical

        for fallback_parts in self._DOC_FALLBACKS.get(
            normalized_parts, ()
        ):  # 仅在解析器内部允许过渡回退
            candidate = self._join(self.repo_root, *fallback_parts)
            if candidate.exists():
                return candidate

        return canonical

    @staticmethod
    def find_first_existing(*paths: PathLike) -> Optional[Path]:
        for path in paths:
            candidate = Path(path)
            if candidate.exists():
                return candidate
        return None

    def _resolve_dir(
        self,
        canonical_dir: Path,
        fallback_dirs: Sequence[Path],
        *,
        preferred_root: Optional[PathLike] = None,
    ) -> Path:
        candidates = self._candidate_roots(
            canonical_dir, fallback_dirs, preferred_root=preferred_root
        )

        for candidate in candidates:
            if self._has_image_files(candidate):
                return candidate

        return self.find_first_existing(*candidates) or candidates[0]

    def _resolve_file(
        self,
        canonical_path: Path,
        fallback_dirs: Sequence[Path],
        parts: Iterable[PathLike],
        *,
        preferred_root: Optional[PathLike] = None,
    ) -> Path:
        roots = self._candidate_roots(
            canonical_path.parent,
            fallback_dirs,
            preferred_root=preferred_root,
        )

        for root in roots:
            candidate = self._join(root, *parts)
            if candidate.exists():
                return candidate

        return canonical_path

    def _candidate_roots(
        self,
        canonical_root: Path,
        fallback_dirs: Sequence[Path],
        *,
        preferred_root: Optional[PathLike] = None,
    ) -> Tuple[Path, ...]:
        if preferred_root is None:
            return (canonical_root, *fallback_dirs)

        preferred_path = Path(preferred_root)
        if not preferred_path.is_absolute():
            preferred_path = self._join(self.repo_root, preferred_path)

        alias_roots = (canonical_root, *fallback_dirs)
        resolved_preferred = preferred_path.resolve(strict=False)
        for alias_root in alias_roots:
            if resolved_preferred == alias_root.resolve(strict=False):
                return alias_roots

        return (preferred_path,)

    @staticmethod
    def _has_image_files(directory: Path) -> bool:
        if not directory.is_dir():
            return False

        try:
            return any(
                child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES
                for child in directory.iterdir()
            )
        except OSError:
            return False

    @staticmethod
    def _join(root: Path, *parts: PathLike) -> Path:
        normalized_parts = RuntimePathResolver._normalize_parts(parts)
        if not normalized_parts:
            return root
        return root.joinpath(*normalized_parts)

    @staticmethod
    def _normalize_parts(parts: Iterable[PathLike]) -> Tuple[str, ...]:
        normalized = []
        for part in parts:
            if part in (None, ""):
                continue
            normalized.extend(Path(str(part)).parts)
        return tuple(normalized)


@lru_cache(maxsize=1)
def get_runtime_path_resolver() -> RuntimePathResolver:
    return RuntimePathResolver()


def discover_repo_root(start: Optional[PathLike] = None) -> Path:
    return RuntimePathResolver.discover_repo_root(start or __file__)


def get_repo_root() -> Path:
    return get_runtime_path_resolver().repo_root


def build_canonical_path(boundary: str, *parts: PathLike) -> Path:
    return get_runtime_path_resolver().build_canonical_path(boundary, *parts)


def resolve_template_path(*parts: PathLike) -> Path:
    return get_runtime_path_resolver().resolve_template(*parts)


def resolve_hero_portrait_path(*parts: PathLike) -> Path:
    return get_runtime_path_resolver().resolve_hero_portrait(*parts)


def resolve_hero_skill_path(*parts: PathLike) -> Path:
    return get_runtime_path_resolver().resolve_hero_skill(*parts)


def resolve_model_path(*parts: PathLike) -> Path:
    return get_runtime_path_resolver().resolve_model(*parts)


def resolve_data_path(*parts: PathLike) -> Path:
    return get_runtime_path_resolver().resolve_data(*parts)


def resolve_doc_path(*parts: PathLike) -> Path:
    return get_runtime_path_resolver().resolve_doc(*parts)
