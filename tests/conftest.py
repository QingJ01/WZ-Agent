"""Pytest配置文件 - 全局fixtures和配置"""

import sys
import os
from pathlib import Path
import pytest

# 添加src目录到Python路径
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 设置环境变量
os.environ["PYTHONPATH"] = str(src_path)


@pytest.fixture(scope="session")
def project_root_path():
    """返回项目根目录路径"""
    return project_root


@pytest.fixture(scope="session")
def src_path_fixture():
    """返回src目录路径"""
    return src_path


@pytest.fixture(scope="session")
def test_data_dir(project_root_path):
    """返回测试数据目录"""
    test_data = project_root_path / "tests" / "test_data"
    test_data.mkdir(exist_ok=True)
    return test_data


@pytest.fixture
def mock_frame():
    """创建模拟的游戏帧"""
    import numpy as np
    return np.zeros((1080, 1920, 3), dtype=np.uint8)


@pytest.fixture
def mock_gray_frame():
    """创建模拟的灰度帧"""
    import numpy as np
    return np.zeros((1080, 1920), dtype=np.uint8)


def pytest_configure(config):
    """Pytest配置钩子"""
    # 添加自定义标记
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


def pytest_collection_modifyitems(config, items):
    """修改测试项集合"""
    for item in items:
        # 自动标记慢速测试
        if "slow" in item.nodeid:
            item.add_marker(pytest.mark.slow)
        
        # 自动标记集成测试
        if "integration" in item.nodeid or "Integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)
