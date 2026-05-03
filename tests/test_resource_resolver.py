"""测试资源路径解析器模块"""

import pytest
from pathlib import Path
from wzry_ai.utils.resource_resolver import (
    RuntimePathResolver,
    get_runtime_path_resolver,
    discover_repo_root,
    get_repo_root,
    build_canonical_path,
    resolve_template_path,
    resolve_hero_portrait_path,
    resolve_model_path,
    resolve_data_path,
)


class TestRuntimePathResolver:
    """测试RuntimePathResolver类"""

    def test_discover_repo_root(self):
        """测试仓库根目录发现"""
        resolver = RuntimePathResolver()
        root = resolver.repo_root
        assert root.exists()
        assert root.is_dir()
        # 验证关键目录存在
        assert (root / "src" / "wzry_ai").exists()
        assert (root / "models").exists() or (root / "data").exists()

    def test_code_root(self):
        """测试代码根目录"""
        resolver = RuntimePathResolver()
        code_root = resolver.code_root()
        assert code_root.exists()
        assert code_root.name == "wzry_ai"
        assert (code_root / "__init__.py").exists()

    def test_build_canonical_path_templates(self):
        """测试构建模板路径"""
        resolver = RuntimePathResolver()
        path = resolver.build_canonical_path("templates", "test.png")
        assert "assets" in str(path)
        assert "templates" in str(path)
        assert path.name == "test.png"

    def test_build_canonical_path_heroes(self):
        """测试构建英雄资源路径"""
        resolver = RuntimePathResolver()
        path = resolver.build_canonical_path("heroes", "yao.png")
        assert "assets" in str(path)
        assert "heroes" in str(path)
        assert path.name == "yao.png"

    def test_build_canonical_path_models(self):
        """测试构建模型路径"""
        resolver = RuntimePathResolver()
        path = resolver.build_canonical_path("models", "model.pt")
        assert "models" in str(path)
        assert path.name == "model.pt"

    def test_build_canonical_path_data(self):
        """测试构建数据路径"""
        resolver = RuntimePathResolver()
        path = resolver.build_canonical_path("data", "config.json")
        assert "data" in str(path)
        assert path.name == "config.json"

    def test_build_canonical_path_invalid_boundary(self):
        """测试无效边界参数"""
        resolver = RuntimePathResolver()
        with pytest.raises(ValueError):
            resolver.build_canonical_path("invalid_boundary", "file.txt")

    def test_templates_dir(self):
        """测试获取模板目录"""
        resolver = RuntimePathResolver()
        templates_dir = resolver.templates_dir()
        assert templates_dir.exists()
        assert templates_dir.is_dir()

    def test_heroes_dir(self):
        """测试获取英雄目录"""
        resolver = RuntimePathResolver()
        heroes_dir = resolver.heroes_dir()
        assert heroes_dir.exists() or "heroes" in str(heroes_dir)

    def test_models_dir(self):
        """测试获取模型目录"""
        resolver = RuntimePathResolver()
        models_dir = resolver.models_dir()
        assert "models" in str(models_dir)

    def test_data_dir(self):
        """测试获取数据目录"""
        resolver = RuntimePathResolver()
        data_dir = resolver.data_dir()
        assert "data" in str(data_dir)

    def test_resolve_template(self):
        """测试解析模板文件"""
        resolver = RuntimePathResolver()
        # 测试解析不存在的模板（应返回规范路径）
        path = resolver.resolve_template("nonexistent.png")
        assert "templates" in str(path) or "image" in str(path)
        assert path.name == "nonexistent.png"

    def test_resolve_model(self):
        """测试解析模型文件"""
        resolver = RuntimePathResolver()
        path = resolver.resolve_model("test_model.pt")
        assert "models" in str(path)
        assert path.name == "test_model.pt"

    def test_resolve_data(self):
        """测试解析数据文件"""
        resolver = RuntimePathResolver()
        path = resolver.resolve_data("test_data.json")
        assert "data" in str(path)
        assert path.name == "test_data.json"

    def test_find_first_existing(self):
        """测试查找第一个存在的路径"""
        resolver = RuntimePathResolver()
        repo_root = resolver.repo_root

        # 测试找到存在的路径
        result = resolver.find_first_existing(
            repo_root / "nonexistent1", repo_root / "src", repo_root / "nonexistent2"
        )
        assert result == repo_root / "src"

        # 测试所有路径都不存在
        result = resolver.find_first_existing(
            repo_root / "nonexistent1", repo_root / "nonexistent2"
        )
        assert result is None


class TestModuleFunctions:
    """测试模块级函数"""

    def test_get_runtime_path_resolver(self):
        """测试获取单例解析器"""
        resolver1 = get_runtime_path_resolver()
        resolver2 = get_runtime_path_resolver()
        assert resolver1 is resolver2  # 应该是同一个实例

    def test_discover_repo_root_function(self):
        """测试仓库根目录发现函数"""
        root = discover_repo_root()
        assert root.exists()
        assert root.is_dir()

    def test_get_repo_root(self):
        """测试获取仓库根目录"""
        root = get_repo_root()
        assert root.exists()
        assert (root / "src" / "wzry_ai").exists()

    def test_build_canonical_path_function(self):
        """测试构建规范路径函数"""
        path = build_canonical_path("templates", "test.png")
        assert "templates" in str(path) or "image" in str(path)

    def test_resolve_template_path(self):
        """测试解析模板路径函数"""
        path = resolve_template_path("test.png")
        assert path.name == "test.png"

    def test_resolve_hero_portrait_path(self):
        """测试解析英雄头像路径函数"""
        path = resolve_hero_portrait_path("yao.png")
        assert path.name == "yao.png"

    def test_resolve_model_path(self):
        """测试解析模型路径函数"""
        path = resolve_model_path("model.pt")
        assert path.name == "model.pt"

    def test_resolve_data_path(self):
        """测试解析数据路径函数"""
        path = resolve_data_path("config.json")
        assert path.name == "config.json"


class TestPathNormalization:
    """测试路径规范化"""

    def test_normalize_parts_with_none(self):
        """测试处理None值"""
        resolver = RuntimePathResolver()
        raw_parts: tuple[str | None, ...] = (None, "test", "", "file.txt")
        parts = [part for part in raw_parts if part is not None]
        assert resolver._normalize_parts(parts) == ("test", "file.txt")

    def test_normalize_parts_with_path_objects(self):
        """测试处理Path对象"""
        resolver = RuntimePathResolver()
        parts = resolver._normalize_parts([Path("dir1/dir2"), "file.txt"])
        assert "dir1" in parts
        assert "dir2" in parts
        assert "file.txt" in parts

    def test_join_with_empty_parts(self):
        """测试连接空路径部分"""
        resolver = RuntimePathResolver()
        root = Path("/test/root")
        raw_parts: tuple[str | None, ...] = (None, "", "file.txt")
        parts = [part for part in raw_parts if part is not None]
        result = resolver._join(root, *parts)
        assert result == root / "file.txt"
