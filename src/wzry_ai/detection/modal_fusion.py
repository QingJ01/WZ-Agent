"""
模态融合模块

功能说明：
    实现模态1（小地图英雄检测）与模态2（全屏血条检测）的数据融合
    通过方位角匹配将模态1的英雄名赋予模态2的血条实体
    
关键设计：
    - 坐标归一化：消除小地图和全屏之间的宽高比差异
    - 排序贪心匹配：按角度差从小到大处理，提高匹配质量
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter
from wzry_ai.utils.logging_utils import get_logger


# 获取模块日志记录器
logger = get_logger(__name__)

# ================= 自身英雄识别平滑机制 =================
# 模块级别的历史缓冲（用于多帧投票平滑）
_self_hero_history = []  # 最近N帧的自身英雄识别结果
_confirmed_self_hero = None  # 已确认的自身英雄
_self_hero_lock_count = 0  # 锁定计数

# ================= 坐标系参数 =================
# 小地图区域的宽高比（配置为 360x380）
MINIMAP_ASPECT_RATIO = 360 / 380  # ≈ 0.947
# 全屏画面的宽高比（1920x1080 = 16:9）
SCREEN_ASPECT_RATIO = 1920 / 1080  # ≈ 1.778
# 全屏可视区域对应小地图的范围（像素）
# 以自身位置为中心，只有这个范围内的小地图实体才会出现在模态2全屏画面中
CAMERA_FOV_W = 101  # 视野宽度（小地图像素）
CAMERA_FOV_H = 57   # 视野高度（小地图像素）


def _filter_by_camera_fov(g_center, entities, margin=1.2):
    """
    过滤小地图实体，只保留在摄像机视野范围内的
    
    功能说明：
        以自身位置为中心，只有 CAMERA_FOV_W x CAMERA_FOV_H 范围内的小地图实体
        才会出现在模态2全屏画面中，超出范围的不参与匹配
    
    参数说明：
        g_center: 自身在小地图的位置 (x, y)
        entities: 实体列表 [(x, y, class_id), ...]
        margin: 边距系数，默认 1.2 表示放宽 20%（补偿检测延迟和边缘情况）
    
    返回值：
        list: 过滤后的实体列表
    """
    half_w = (CAMERA_FOV_W / 2) * margin
    half_h = (CAMERA_FOV_H / 2) * margin
    gx, gy = g_center
    filtered = []
    for entity in entities:
        ex, ey = entity[0], entity[1]
        if abs(ex - gx) <= half_w and abs(ey - gy) <= half_h:
            filtered.append(entity)
    if len(filtered) < len(entities):
        logger.debug(f"视野过滤: {len(entities)} -> {len(filtered)} 个实体（视野 {CAMERA_FOV_W}x{CAMERA_FOV_H}, 中心={g_center}）")
    return filtered


def _normalize_for_angle(self_pos, target_pos, aspect_ratio):
    """
    对坐标进行宽高比归一化，然后计算方位角
    
    功能说明：
        不同坐标系（小地图 vs 全屏）宽高比不同，直接用像素坐标算角度会有偏差
        例如：全屏16:9中，水平100px对应的实际距离远小于垂直100px
        归一化后消除这种偏差，使两个坐标系的角度可以直接对比
    
    参数说明：
        self_pos: 自身位置 (x, y)
        target_pos: 目标位置 (x, y)
        aspect_ratio: 坐标系的宽高比（width/height）
    
    返回值：
        float: 归一化后的方位角（弧度），范围 [-π, π]
    """
    # 将 x 坐标除以宽高比，等效于把水平距离"压缩"到与垂直距离同尺度
    dx = (target_pos[0] - self_pos[0]) / aspect_ratio
    dy = target_pos[1] - self_pos[1]
    return math.atan2(dy, dx)


def angle_difference(a1: float, a2: float) -> float:
    """
    计算两个角度之间的最小差值
    
    功能说明：
        处理 -π 到 π 的角度环绕问题
        返回的角度差值范围是 [0, π]
    
    参数说明：
        a1: 第一个角度（弧度）
        a2: 第二个角度（弧度）
    
    返回值：
        float: 两个角度之间的最小差值（弧度），范围 [0, π]
    """
    diff = abs(a1 - a2)
    # 处理角度环绕：如果差值大于 π，则使用 2π - diff
    while diff > math.pi:
        diff = 2 * math.pi - diff
    return diff


def match_entities_by_angle(
    m1_self: Tuple[float, float],
    m1_entities: List[Tuple[float, float, int]],
    m2_self: Tuple[float, float],
    m2_entities: List[Tuple[float, float, Any]],
    class_names: Dict[int, str],
    max_angle_diff: float = math.pi / 4
) -> Dict[int, str]:
    """
    基于归一化方位角的排序贪心匹配算法
    
    功能说明：
        将模态1（小地图）中的实体与模态2（全屏血条）中的实体进行匹配
        先对坐标进行宽高比归一化，再比较方位角，最后按匹配质量排序贪心选取
    
    改进点（相比旧版）：
        1. 坐标归一化：消除小地图(≈1:1)与全屏(16:9)的宽高比偏差
        2. 排序贪心：所有候选配对按角度差排序，优先确认最佳匹配
    
    参数说明：
        m1_self: 模态1中自身位置 (x, y)
        m1_entities: 模态1中实体列表 [(x, y, class_id), ...]
        m2_self: 模态2中自身位置 (x, y)
        m2_entities: 模态2中实体列表 [(x, y, health), ...]
        class_names: class_id 到英雄中文名的映射字典
        max_angle_diff: 最大允许角度差（弧度），默认 π/4（45度）
    
    返回值：
        Dict[int, str]: 模态2实体索引到英雄中文名的映射
    """
    result = {}
    
    # 边界情况处理
    if not m1_entities or not m2_entities:
        logger.debug("实体列表为空，跳过匹配")
        return result
    
    # 第一步：计算模态1中每个实体的归一化方位角（使用小地图宽高比）
    m1_angles = []
    for i, entity in enumerate(m1_entities):
        x, y, class_id = entity
        angle = _normalize_for_angle(m1_self, (x, y), MINIMAP_ASPECT_RATIO)
        m1_angles.append((i, angle, class_id))
    
    # 第二步：计算模态2中每个实体的归一化方位角（使用全屏宽高比）
    m2_angles = []
    for idx, entity in enumerate(m2_entities):
        x, y = entity[0], entity[1]
        angle = _normalize_for_angle(m2_self, (x, y), SCREEN_ASPECT_RATIO)
        m2_angles.append((idx, angle))
    
    # 第三步：生成所有候选配对，并计算角度差
    # 格式：(角度差, m2索引, m1索引, class_id)
    candidates = []
    for m2_idx, m2_angle in m2_angles:
        for m1_i, m1_angle, class_id in m1_angles:
            diff = angle_difference(m1_angle, m2_angle)
            if diff <= max_angle_diff:
                candidates.append((diff, m2_idx, m1_i, class_id))
    
    # 第四步：按角度差从小到大排序（最佳匹配优先）
    candidates.sort(key=lambda c: c[0])
    
    # 第五步：排序贪心选取——每个 m1 和 m2 实体只匹配一次
    matched_m1 = set()   # 已匹配的 m1 索引
    matched_m2 = set()   # 已匹配的 m2 索引
    
    for diff, m2_idx, m1_i, class_id in candidates:
        # 如果任一方已被匹配，跳过
        if m2_idx in matched_m2 or m1_i in matched_m1:
            continue
        
        # 获取英雄中文名
        chinese_name = class_names.get(class_id)
        if chinese_name:
            result[m2_idx] = chinese_name
            matched_m1.add(m1_i)
            matched_m2.add(m2_idx)
            logger.debug(f"匹配成功: m2[{m2_idx}] <-> m1[{m1_i}] ({chinese_name}), 角度差={math.degrees(diff):.1f}°")
        else:
            logger.debug(f"无法获取英雄中文名: class_id={class_id}")
    
    logger.info(f"匹配完成: {len(result)}/{len(m2_entities)} 个实体成功匹配")
    return result


def fuse_modal_data(
    model1_result: Optional[Dict[str, Any]],
    model2_result: Optional[Dict[str, Any]],
    known_self_hero: Optional[str] = None  # 新增：选英雄阶段确认的英雄
) -> Dict[str, Any]:
    """
    主融合函数，协调整个匹配流程
    
    功能说明：
        整合模态1和模态2的检测结果，通过方位角匹配
        将模态1的英雄名称赋予模态2的血条实体
    
    参数说明：
        model1_result: 模态1检测结果字典
        model2_result: 模态2检测结果字典
    
    返回值：
        Dict[str, Any]: 融合结果，包含以下字段：
            - self_name: 自身英雄中文名（或 None）
            - team_names: 队友索引到英雄中文名的映射
            - enemy_names: 敌人索引到英雄中文名的映射
    """
    # 初始化返回结果
    result = {
        'self_name': None,
        'team_names': {},
        'enemy_names': {}
    }
    
    # 边界情况处理：输入为 None
    if model1_result is None:
        logger.debug("模态1结果为空，无法融合")
        return result
    
    if model2_result is None:
        logger.debug("模态2结果为空，无法融合")
        return result
    
    # 提取必要数据
    g_center = model1_result.get('g_center')
    self_class_id = model1_result.get('self_class_id')
    b_centers = model1_result.get('b_centers', [])
    r_centers = model1_result.get('r_centers', [])
    class_names = model1_result.get('class_names', {})
    
    self_pos = model2_result.get('self_pos')
    team_targets = model2_result.get('team_targets', [])
    enemies = model2_result.get('enemies', [])
    
    # 检查必要数据是否存在
    if g_center is None:
        logger.debug("模态1缺少自身位置(g_center)，无法融合")
        return result
    
    if self_pos is None:
        logger.debug("模态2缺少自身位置(self_pos)，无法融合")
        return result
    
    # 1. 获取自身英雄名称
    global _self_hero_history, _confirmed_self_hero, _self_hero_lock_count
    
    # 如果已知英雄名（来自选英雄阶段），直接使用，跳过YOLO投票
    if known_self_hero:
        if _confirmed_self_hero != known_self_hero:
            _confirmed_self_hero = known_self_hero
            logger.info(f"使用选英雄阶段确认的英雄: {known_self_hero}")
        result['self_name'] = known_self_hero
    else:
        # 保留原有的多帧投票逻辑（作为 fallback）
        self_chinese = None
        if self_class_id is not None and self_class_id in class_names:
            self_chinese = class_names[self_class_id]
        else:
            logger.debug(f"自身class_id无效或不在class_names中: {self_class_id}")
        
        # 多帧投票平滑逻辑
        if self_chinese:
            _self_hero_history.append(self_chinese)
            # 只保留最近10帧
            if len(_self_hero_history) > 10:
                _self_hero_history.pop(0)
        
        # 如果已有确认的英雄，且当前帧与之不同，需要连续多帧不同才切换
        if _confirmed_self_hero:
            if self_chinese == _confirmed_self_hero:
                _self_hero_lock_count = 0
                result['self_name'] = _confirmed_self_hero
            else:
                _self_hero_lock_count += 1
                # 需要连续5帧不同才考虑切换
                if _self_hero_lock_count >= 5:
                    # 从历史中投票选最多的
                    counter = Counter(_self_hero_history[-5:])
                    most_common = counter.most_common(1)[0]
                    if most_common[1] >= 3:  # 至少3/5帧一致
                        old_hero = _confirmed_self_hero
                        _confirmed_self_hero = most_common[0]
                        _self_hero_lock_count = 0
                        logger.info(f"自身英雄切换: {old_hero} -> {_confirmed_self_hero}")
                result['self_name'] = _confirmed_self_hero  # 保持已确认的英雄
        else:
            # 首次确认：需要历史中有3帧以上一致
            if len(_self_hero_history) >= 3:
                counter = Counter(_self_hero_history)
                most_common = counter.most_common(1)[0]
                if most_common[1] >= 3:
                    _confirmed_self_hero = most_common[0]
                    result['self_name'] = _confirmed_self_hero
                    logger.info(f"自身英雄确认为: {_confirmed_self_hero}")
                else:
                    result['self_name'] = self_chinese  # 暂用当前帧结果
            else:
                result['self_name'] = self_chinese  # 历史不够，暂用当前帧
    
    # 输出最终识别结果
    if result['self_name']:
        logger.info(f"自身英雄识别: {result['self_name']}")
    
    # 2. 队友匹配
    # 视野过滤：只保留小地图上在摄像机视野范围内的队友
    visible_b_centers = _filter_by_camera_fov(g_center, b_centers)
    
    if visible_b_centers and team_targets:
        result['team_names'] = match_entities_by_angle(
            m1_self=g_center,
            m1_entities=visible_b_centers,
            m2_self=self_pos,
            m2_entities=team_targets,
            class_names=class_names,
            max_angle_diff=math.pi / 4
        )

    
    # 3. 敌人匹配
    # 视野过滤：只保留小地图上在摄像机视野范围内的敌人
    visible_r_centers = _filter_by_camera_fov(g_center, r_centers)
    
    if visible_r_centers and enemies:
        result['enemy_names'] = match_entities_by_angle(
            m1_self=g_center,
            m1_entities=visible_r_centers,
            m2_self=self_pos,
            m2_entities=enemies,
            class_names=class_names,
            max_angle_diff=math.pi / 4
        )

    
    # 4. 匹配后结果上限检查
    if len(result['team_names']) > 4:
        logger.warning(f"队友匹配结果超过上限: {len(result['team_names'])} > 4，检测可能有误")
    if len(result['enemy_names']) > 5:
        logger.warning(f"敌人匹配结果超过上限: {len(result['enemy_names'])} > 5，检测可能有误")
    
    # 5. 计算融合置信度评分（基于视野过滤后的实体数）
    visible_team_count = len(visible_b_centers) if 'visible_b_centers' in dir() else len(b_centers)
    visible_enemy_count = len(visible_r_centers) if 'visible_r_centers' in dir() else len(r_centers)
    team_match_ratio = len(result['team_names']) / max(visible_team_count, len(team_targets), 1)
    enemy_match_ratio = len(result['enemy_names']) / max(visible_enemy_count, len(enemies), 1)
    result['confidence'] = (team_match_ratio + enemy_match_ratio) / 2
    
    # 汇总结果
    logger.info(
        f"融合完成: 自身={result['self_name']}, "
        f"队友={len(result['team_names'])}/{len(team_targets)}, "
        f"敌人={len(result['enemy_names'])}/{len(enemies)}, "
        f"置信度={result['confidence']:.2f}"
    )
    
    return result
