"""英雄特征学习器 - 使用深度学习特征提取和在线学习"""

# 导入标准库模块
import os  # 操作系统接口模块，用于文件路径操作
import pickle  # 序列化模块，用于保存和加载特征数据
import time  # 时间模块，用于记录特征创建时间戳
from dataclasses import dataclass  # 数据类装饰器，用于创建简单的数据容器类
from typing import Any, Optional  # 类型提示，表示可选参数

# 导入第三方库
import cv2  # OpenCV库，用于图像处理和特征提取
import numpy as np  # NumPy库，用于数值计算和数组操作

# 导入日志工具模块，支持相对导入和绝对导入两种方式
from wzry_ai.utils.logging_utils import get_logger

# 导入运行时资源解析器，统一管理 data/ 目录路径
from wzry_ai.utils.resource_resolver import resolve_data_path

# 创建模块级别的日志记录器实例
logger = get_logger(__name__)


# 使用dataclass装饰器定义英雄特征数据类
@dataclass
class HeroFeature:
    """英雄特征数据类，用于存储单个英雄的特征信息"""

    hero_name: str  # 英雄名称（拼音或中文）
    feature_vector: np.ndarray  # 特征向量，表示英雄图像的深度学习特征
    timestamp: float  # 特征创建的时间戳，用于管理特征的新鲜度
    confidence: float  # 特征提取的置信度，表示该特征的可靠程度


class HeroFeatureLearner:
    """
    英雄特征学习器类

    功能说明：
    1. 使用深度学习模型（MobileNetV2）提取英雄图像的特征向量
    2. 通过余弦相似度匹配图像与已知英雄
    3. 支持在线学习，不断积累新的英雄特征样本
    4. 自动保存和加载特征数据库

    参数说明：
    - feature_db_path: 特征数据库文件路径，默认保存为hero_features.pkl

    返回值说明：
    - match方法返回匹配到的英雄名称和相似度分数
    """

    # 类常量定义
    FEATURE_DIM = 1280  # 特征向量维度，MobileNetV2输出的特征维度
    SIMILARITY_THRESHOLD = 0.85  # 相似度阈值，超过此值才认为匹配成功
    TEMPLATE_FALLBACK_THRESHOLD = (
        0.40  # 模板匹配回退阈值，模板置信度在此范围内时启用深度学习
    )

    def __init__(self, feature_db_path: Optional[str] = None):
        """
        初始化英雄特征学习器

        参数说明：
        - feature_db_path: 特征数据库文件路径，默认为None（自动使用 data/hero_features.pkl）
        """
        # 如果未指定路径，使用默认的 data/ 目录
        if feature_db_path is None:
            feature_db_path = os.fspath(resolve_data_path("hero_features.pkl"))

        self.feature_db_path = feature_db_path  # 保存特征数据库文件路径
        self.features: dict[
            str, list[HeroFeature]
        ] = {}  # 特征字典，键是英雄名，值是该英雄的特征列表
        self.model: Any | None = None
        self.transform: Any | None = None
        self.net: Any | None = None
        self.use_torch = False
        self._load_features()  # 从文件加载已保存的特征数据
        self._init_feature_extractor()  # 初始化特征提取器（PyTorch或OpenCV）

        # 记录加载的特征数量
        logger.info(f"加载了 {len(self.features)} 个英雄的特征库")

    def _init_feature_extractor(self):
        """
        初始化特征提取器

        功能说明：
        尝试使用PyTorch加载MobileNetV2模型进行特征提取
        如果PyTorch未安装，则回退到使用OpenCV DNN或直方图特征
        """
        try:
            # 导入PyTorch相关库
            import torch  # PyTorch深度学习框架
            import torchvision.models as models  # 预训练模型库
            import torchvision.transforms as transforms  # 图像预处理变换

            # 加载预训练的MobileNetV2模型
            model: Any = models.mobilenet_v2(pretrained=True)
            # 将分类器替换为Identity层，使其输出特征向量而非分类结果
            model.classifier = torch.nn.Identity()
            # 设置模型为评估模式（禁用dropout等训练专用层）
            model.eval()

            # 定义图像预处理流程
            self.model = model
            self.transform = transforms.Compose(
                [
                    transforms.ToPILImage(),  # 将NumPy数组转换为PIL图像
                    transforms.Resize(
                        (224, 224)
                    ),  # 调整图像大小为224x224（模型输入尺寸）
                    transforms.ToTensor(),  # 转换为PyTorch张量
                    transforms.Normalize(
                        mean=[0.485, 0.456, 0.406],  # ImageNet均值标准化
                        std=[0.229, 0.224, 0.225],
                    ),  # ImageNet标准差标准化
                ]
            )

            # 标记使用PyTorch模式
            self.use_torch = True
            logger.info("使用PyTorch MobileNetV2提取特征")

        except ImportError:
            # PyTorch未安装，使用备选方案
            logger.info("PyTorch未安装，使用OpenCV DNN")
            self.use_torch = False  # 标记不使用PyTorch
            self._init_opencv_extractor()  # 初始化OpenCV备选方案

    def _init_opencv_extractor(self):
        """
        使用OpenCV DNN作为特征提取的备选方案

        功能说明：
        尝试加载TensorFlow格式的MobileNetV2模型
        如果模型文件不存在，则使用颜色直方图作为最简单的备选特征
        """
        # 构建模型文件路径
        model_path = os.path.join("models", "mobilenet_v2.pb")

        # 检查模型文件是否存在
        if os.path.exists(model_path):
            # 使用OpenCV DNN读取TensorFlow模型
            self.net = cv2.dnn.readNetFromTensorflow(model_path)
            logger.info("加载OpenCV DNN模型")
        else:
            # 模型文件不存在，使用直方图特征
            logger.info("使用直方图特征作为备选")
            self.net = None  # 网络对象设为None，表示使用直方图特征

    def _load_features(self):
        """
        从文件加载特征数据库

        功能说明：
        从pickle文件读取之前保存的英雄特征数据
        如果文件不存在或读取失败，则初始化为空字典
        """
        # 检查特征数据库文件是否存在
        if os.path.exists(self.feature_db_path):
            try:
                # 以二进制读取模式打开文件
                with open(self.feature_db_path, "rb") as f:
                    # 使用pickle反序列化特征数据
                    self.features = pickle.load(f)
                logger.info(f"从 {self.feature_db_path} 加载特征库")
            except (FileNotFoundError, pickle.UnpicklingError, OSError, EOFError) as e:
                # 读取失败时记录错误并初始化为空字典
                logger.error(f"加载特征库失败: {e}", exc_info=True)
                self.features = {}
        else:
            # 文件不存在，初始化为空字典
            self.features = {}

    def _save_features(self):
        """
        保存特征数据库到文件

        功能说明：
        将当前内存中的特征数据序列化保存到pickle文件
        用于持久化存储学习到的英雄特征
        """
        try:
            # 以二进制写入模式打开文件
            with open(self.feature_db_path, "wb") as f:
                # 使用pickle序列化特征数据
                pickle.dump(self.features, f)
            logger.info(f"特征库已保存到 {self.feature_db_path}")
        except (OSError, pickle.PicklingError) as e:
            # 保存失败时记录错误
            logger.error(f"保存特征库失败: {e}", exc_info=True)

    def extract_features(self, img: np.ndarray) -> np.ndarray:
        """
        提取图像特征的主入口方法

        参数说明：
        - img: 输入图像，BGR格式的NumPy数组

        返回值说明：
        - 返回特征向量，NumPy数组格式

        功能说明：
        根据初始化时确定的特征提取方式，调用对应的特征提取方法
        """
        # 根据初始化时设置的标志选择特征提取方法
        if self.use_torch and self.model is not None and self.transform is not None:
            # 使用PyTorch深度学习模型提取特征
            return self._extract_torch_features(img)
        elif self.net is not None:
            # 使用OpenCV DNN提取特征
            return self._extract_opencv_features(img)
        else:
            # 使用颜色直方图作为最简单的备选特征
            return self._extract_histogram_features(img)

    def _extract_torch_features(self, img: np.ndarray) -> np.ndarray:
        """
        使用PyTorch MobileNetV2模型提取图像特征

        参数说明：
        - img: 输入图像，BGR格式的NumPy数组

        返回值说明：
        - 返回1280维的特征向量

        功能说明：
        1. 将BGR图像转换为RGB格式
        2. 应用预处理变换（调整大小、标准化等）
        3. 使用MobileNetV2模型提取特征
        4. 返回展平的特征向量
        """
        import torch  # 在方法内导入torch，避免模块级别依赖

        if self.model is None or self.transform is None:
            return self._extract_histogram_features(img)

        # 将BGR格式转换为RGB格式（PyTorch模型需要RGB输入）
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        # 应用预处理变换并增加batch维度（unsqueeze(0)）
        transformed: Any = self.transform(img_rgb)
        input_tensor: Any = transformed.unsqueeze(0)

        # 使用torch.no_grad()禁用梯度计算，提高推理速度并减少内存使用
        with torch.no_grad():
            # 前向传播获取特征
            features: Any = self.model(input_tensor)

        # 将PyTorch张量转换为NumPy数组并展平为一维向量
        return np.asarray(features.numpy()).flatten()

    def _extract_opencv_features(self, img: np.ndarray) -> np.ndarray:
        """
        使用OpenCV DNN提取图像特征

        参数说明：
        - img: 输入图像，BGR格式的NumPy数组

        返回值说明：
        - 返回特征向量

        功能说明：
        使用OpenCV的blobFromImage创建输入blob，通过DNN网络前向传播提取特征
        """
        if self.net is None:
            return self._extract_histogram_features(img)

        # 创建输入blob，进行预处理（调整大小、减去均值、交换RB通道）
        blob = cv2.dnn.blobFromImage(
            img,
            1.0,
            (224, 224),
            (0.485, 0.456, 0.406),  # ImageNet均值
            swapRB=True,
            crop=False,
        )  # 交换红蓝通道
        # 设置网络输入
        self.net.setInput(blob)
        # 前向传播获取特征
        features = self.net.forward()
        # 返回展平的特征向量
        return features.flatten()

    def _extract_histogram_features(self, img: np.ndarray) -> np.ndarray:
        """
        使用颜色直方图作为备选特征提取方法

        参数说明：
        - img: 输入图像，BGR格式的NumPy数组

        返回值说明：
        - 返回1280维的特征向量（不足部分用0填充）

        功能说明：
        1. 将图像从BGR转换到HSV颜色空间
        2. 计算色调(H)和饱和度(S)的直方图
        3. 归一化并拼接直方图
        4. 填充或截断到固定维度
        """
        # 将BGR图像转换为HSV颜色空间
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 计算色调(Hue)直方图，30个bins，范围0-180度
        h_hist = cv2.calcHist([hsv], [0], None, [30], [0, 180])
        # 计算饱和度(Saturation)直方图，32个bins，范围0-256
        s_hist = cv2.calcHist([hsv], [1], None, [32], [0, 256])

        # 对直方图进行归一化处理
        h_hist = cv2.normalize(h_hist, h_hist).flatten()
        s_hist = cv2.normalize(s_hist, s_hist).flatten()

        # 将两个直方图拼接成一个特征向量
        features = np.concatenate([h_hist, s_hist])

        # 如果特征维度不足，用0填充到目标维度
        if len(features) < self.FEATURE_DIM:
            features = np.pad(features, (0, self.FEATURE_DIM - len(features)))

        # 返回前FEATURE_DIM个元素（如果超过则截断）
        return features[: self.FEATURE_DIM]

    def match(
        self, img: np.ndarray, hero_list: list[str]
    ) -> tuple[Optional[str], float]:
        """
        将输入图像与英雄列表进行匹配

        参数说明：
        - img: 输入图像，BGR格式的NumPy数组
        - hero_list: 待匹配的英雄名称列表

        返回值说明：
        - 返回元组 (匹配的英雄名称, 相似度分数)
        - 如果没有匹配成功，英雄名称为None

        功能说明：
        1. 提取输入图像的特征向量
        2. 与特征库中每个英雄的特征计算余弦相似度
        3. 返回相似度最高且超过阈值的英雄
        """
        # 检查特征库是否为空
        if not self.features:
            return None, 0.0

        # 提取查询图像的特征向量
        query_feature = self.extract_features(img)

        # 初始化最佳匹配结果
        best_match = None  # 最佳匹配的英雄名称
        best_similarity = 0.0  # 最高相似度分数

        # 遍历英雄列表，计算与每个英雄的相似度
        for hero_name in hero_list:
            # 检查该英雄是否在特征库中
            if hero_name not in self.features:
                continue

            # 计算与该英雄所有存储特征的相似度
            similarities = []
            for hero_feature in self.features[hero_name]:
                # 计算余弦相似度
                sim = self._cosine_similarity(
                    query_feature, hero_feature.feature_vector
                )
                similarities.append(sim)

            # 获取该英雄的最高相似度
            max_sim = max(similarities) if similarities else 0

            # 更新全局最佳匹配
            if max_sim > best_similarity:
                best_similarity = max_sim
                best_match = hero_name

        # 检查是否超过相似度阈值
        if best_similarity >= self.SIMILARITY_THRESHOLD:
            return best_match, best_similarity

        # 未超过阈值，返回None
        return None, best_similarity

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        计算两个向量之间的余弦相似度

        参数说明：
        - a: 第一个向量，NumPy数组
        - b: 第二个向量，NumPy数组

        返回值说明：
        - 返回余弦相似度值，范围[-1, 1]，值越大表示越相似

        功能说明：
        余弦相似度 = (A·B) / (||A|| * ||B||)
        用于衡量两个向量在方向上的相似程度
        """
        # 计算向量的L2范数（模长）
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        # 处理零向量情况，避免除零错误
        if norm_a == 0 or norm_b == 0:
            return 0.0

        # 计算并返回余弦相似度
        return np.dot(a, b) / (norm_a * norm_b)

    def learn(self, hero_name: str, img: np.ndarray, confidence: float):
        """
        学习新的英雄特征

        参数说明：
        - hero_name: 英雄名称
        - img: 英雄图像，BGR格式的NumPy数组
        - confidence: 特征提取的置信度

        功能说明：
        1. 提取图像特征向量
        2. 创建HeroFeature对象并添加到特征库
        3. 限制每个英雄的特征数量不超过100个
        4. 自动保存特征库到文件
        """
        # 提取图像特征向量
        feature_vector = self.extract_features(img)

        # 创建HeroFeature数据对象
        hero_feature = HeroFeature(
            hero_name=hero_name,  # 英雄名称
            feature_vector=feature_vector,  # 特征向量
            timestamp=time.time(),  # 当前时间戳
            confidence=confidence,  # 置信度
        )

        # 如果该英雄还没有特征列表，创建空列表
        if hero_name not in self.features:
            self.features[hero_name] = []

        # 将新特征添加到该英雄的特征列表
        self.features[hero_name].append(hero_feature)

        # 限制每个英雄的特征数量，保留最新的100个
        if len(self.features[hero_name]) > 100:
            self.features[hero_name] = self.features[hero_name][-100:]

        # 记录学习信息
        logger.info(
            f"学习新特征: {hero_name} (当前共{len(self.features[hero_name])}个特征)"
        )

        # 自动保存特征库
        self._save_features()

    def should_use_deep_learning(self, template_confidence: float) -> bool:
        """
        判断是否应该使用深度学习进行特征匹配

        参数说明：
        - template_confidence: 模板匹配的置信度分数

        返回值说明：
        - 返回True表示应该使用深度学习，False表示不需要

        功能说明：
        当模板匹配置信度在回退阈值和0.60之间时，启用深度学习作为补充验证
        这用于处理模板匹配不确定但可能通过深度学习改善的情况
        """
        return self.TEMPLATE_FALLBACK_THRESHOLD <= template_confidence < 0.60
