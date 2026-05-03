"""
英雄名称映射模块

功能说明：
    本模块提供中文英雄名与拼音之间的双向转换功能，
    包含完整的英雄名称映射字典、分路配置和转换函数。

参数说明：
    无直接参数，通过导入变量和调用函数使用

返回值说明：
    无直接返回值，提供映射字典和转换函数
"""

# ========== 英雄名称映射（中文→拼音） ==========
# from typing import Optional
# HERO_NAME_MAP字典存储所有英雄的中文名到拼音的映射
HERO_NAME_MAP = {
    # 对抗路英雄
    "廉颇": "lianpo",
    "庄周": "zhuangzhou",
    "刘禅": "liushan",
    "白起": "baiqi",
    "项羽": "xiangyu",
    "程咬金": "chengyaojin",
    "刘邦": "liubang",
    "牛魔": "niumo",
    "张飞": "zhangfei",
    "东皇太一": "donghuangtaiyi",
    "苏烈": "sulie",
    "盾山": "dunshan",
    "铠": "kai",
    "梦奇": "mengqi",
    "夏侯惇": "xiahoudun",
    "吕布": "lvbu",
    "蒙恬": "mengtian",
    "猪八戒": "zhubajie",
    "赵云": "zhaoyun",
    "钟无艳": "zhongwuyan",
    "老夫子": "laofuzi",
    "关羽": "guanyu",
    "典韦": "dianwei",
    "宫本武藏": "gongbenwuzang",
    "曹操": "caocao",
    "哪吒": "nezha",
    "花木兰": "huamulan",
    "达摩": "damo",
    "亚瑟": "yase",
    "孙悟空": "sunwukong",
    "刘备": "liubei",
    "杨戬": "yangjian",
    "雅典娜": "yadianna",
    "盘古": "pangu",
    "马超": "machao",
    "狂铁": "kuangtie",
    "李信": "lixin",
    "曜": "yao",
    "云中君": "yunzhongjun",
    "东方曜": "dongfangyao",
    "司空震": "sikongzhen",
    "夏洛特": "xialuote",
    "澜": "lan",
    "姬小满": "jixiaoman",
    "亚连": "yalian",
    "影": "ying",
    "大司命": "dasiming",
    "阿古朵": "aguduo",
    "孙策": "sunce",
    "蚩奼": "chicha",
    "橘右京": "jvyoujing",
    "赵怀真": "zhaohuaizhen",
    "元流之子(坦)": "yuanliuzhizi_tank",
    # 中路英雄
    "小乔": "xiaoqiao",
    "妲己": "daji",
    "嬴政": "yingzheng",
    "赢政": "yingzheng",
    "甄姬": "zhenji",
    "诸葛亮": "zhugeliang",
    "王昭君": "wangzhaojun",
    "安琪拉": "anqila",
    "姜子牙": "jiangziya",
    "周瑜": "zhouyu",
    "芈月": "miyue",
    "武则天": "wuzetian",
    "貂蝉": "diaochan",
    "扁鹊": "bianque",
    "大乔": "daqiao",
    "干将莫邪": "ganjiangmoye",
    "上官婉儿": "shangguanwaner",
    "嫦娥": "change",
    "西施": "xishi",
    "沈梦溪": "shenmengxi",
    "米莱狄": "milaidi",
    "女娲": "nvwa",
    "弈星": "yixing",
    "杨玉环": "yangyuhuan",
    "金蝉": "jinchan",
    "桑启": "sangqi",
    "朵莉亚": "duoliya",
    "海诺": "hainuo",
    "墨子": "mozi",
    "高渐离": "gaojianli",
    "不知火舞": "buzhihuowu",
    "张良": "zhangliang",
    "海月": "haiyue",
    # 发育路英雄
    "孙尚香": "sunshangxiang",
    "鲁班七号": "lubanqihao",
    "后羿": "houyi",
    "狄仁杰": "direnjie",
    "马可波罗": "makeboluo",
    "李元芳": "liyuanfang",
    "虞姬": "yuji",
    "黄忠": "huangzhong",
    "成吉思汗": "chengjisihan",
    "百里守约": "bailishouyue",
    "公孙离": "gongsunli",
    "伽罗": "jialuo",
    "蒙犽": "mengya",
    "艾琳": "ailin",
    "戈娅": "geya",
    "莱西奥": "laixiao",
    "敖隐": "aoyin",
    "百里玄策": "bailixuance",
    "玄策": "bailixuance",
    "鲁班大师": "lubandashi",
    "孙权": "sunquan",
    "苍": "cang",
    # 打野英雄
    "阿轲": "ake",
    "李白": "libai",
    "娜可露露": "nakelulu",
    "兰陵王": "lanlingwang",
    "韩信": "hanxin",
    "露娜": "luna",
    "裴擒虎": "peiqinhu",
    "司马懿": "simayi",
    "元歌": "yuange",
    "镜": "jing",
    "暃": "fei",
    "云缨": "yunying",
    "曜": "yao",
    "孙悟空": "sunwukong",
    "刘备": "liubei",
    "雅典娜": "yadianna",
    "盘古": "pangu",
    "典韦": "dianwei",
    "云中君": "yunzhongjun",
    "赵云": "zhaoyun",
    "阿古朵": "aguduo",
    "哪吒": "nezha",
    "曹操": "caocao",
    "马超": "machao",
    "司空震": "sikongzhen",
    "大司命": "dasiming",
    "影": "ying",
    "赵怀真": "zhaohuaizhen",
    "猪八戒": "zhubajie",
    "元流之子(坦)": "yuanliuzhizi_tank",
    "梦奇": "mengqi",
    "夏侯惇": "xiahoudun",
    "李元芳": "liyuanfang",
    "橘右京": "jvyoujing",
    # 游走英雄
    "孙膑": "sunbin",
    "蔡文姬": "caiwenji",
    "太乙真人": "taiyizhenren",
    "鬼谷子": "guiguzi",
    "牛魔": "niumo",
    "庄周": "zhuangzhou",
    "明世隐": "mingshiyin",
    "瑶": "yao",
    "钟馗": "zhongkui",
    "桑启": "sangqi",
    "少司缘": "shaosiyuan",
    "空空儿": "kongkonger",
    "大禹": "dayu",
    "刘禅": "liushan",
    "张飞": "zhangfei",
    "大乔": "daqiao",
    "朵莉亚": "duoliya",
    "鲁班大师": "lubandashi",
    "廉颇": "lianpo",
    "东皇太一": "donghuangtaiyi",
    "苏烈": "sulie",
    "盾山": "dunshan",
    "刘邦": "liubang",
    "项羽": "xiangyu",
    "甄姬": "zhenji",
    "姜子牙": "jiangziya",
    "牛魔": "niumo",
    "王昭君": "wangzhaojun",
    "夏侯惇": "xiahoudun",
    "墨子": "mozi",
    "米莱狄": "milaidi",
    "弈星": "yixing",
    "张良": "zhangliang",
    # 元流之子系列 - name_with_chinese.txt 中的格式
    "元流之子(坦)": "yuanliuzhizi_tank",
    "元流之子(法)": "yuanliuzhizi_magic",
    "元流之子(射)": "yuanliuzhizi_archer",
    "元流之子(辅)": "yuanliuzhizi_support",
}


def get_hero_pinyin(chinese_name: str) -> str:
    """
    获取英雄的拼音名称

    功能说明：
        将中文英雄名转换为拼音名

    参数说明：
        chinese_name: 英雄中文名字符串

    返回值说明：
        str: 英雄拼音名，如果找不到映射则返回原中文名
    """
    return HERO_NAME_MAP.get(chinese_name, chinese_name)  # 找不到时返回原名


def convert_priority_heroes(hero_list: list, suffix: str = "_blue") -> list:
    """
    将中文英雄名转换为拼音+后缀格式

    功能说明：
        批量转换英雄名称列表，为每个拼音名添加指定后缀
        常用于生成带阵营标识的英雄名称

    参数说明：
        hero_list: 英雄中文名列表
        suffix: 要添加的后缀字符串，默认为"_blue"

    返回值说明：
        list: 转换后的拼音+后缀名称列表
    """
    result = []  # 初始化结果列表
    for name in hero_list:  # 遍历每个英雄名
        if name in HERO_NAME_MAP:  # 检查是否在映射字典中
            result.append(HERO_NAME_MAP[name] + suffix)  # 添加拼音+后缀
        else:
            result.append(name)  # 找不到映射则保留原名
    return result  # 返回转换后的列表


# ========== 创建反向映射（拼音_blue -> 中文） ==========
# PINYIN_TO_CHINESE字典将带_blue后缀的拼音映射回中文名
# 使用字典推导式从HERO_NAME_MAP生成
PINYIN_TO_CHINESE = {v + "_blue": k for k, v in HERO_NAME_MAP.items()}

# ========== 创建基础拼音到中文的映射（处理后缀） ==========
# PINYIN_BASE_TO_CHINESE字典存储基础拼音到中文的映射
# 用于处理带各种后缀（_blue, _green, _red等）的拼音名
PINYIN_BASE_TO_CHINESE = {v: k for k, v in HERO_NAME_MAP.items()}


def get_hero_chinese(pinyin_name: str) -> str:
    """
    获取英雄的中文名称，支持 _blue, _green, _red 等后缀

    功能说明：
        将带后缀的拼音名转换为中文名，支持多种阵营后缀
        先尝试完整匹配，再尝试去掉后缀匹配

    参数说明：
        pinyin_name: 带后缀的英雄拼音名，如"yao_blue"

    返回值说明：
        str: 英雄中文名，如果找不到映射则返回原拼音名
    """
    # 首先尝试直接匹配带后缀的完整名称
    if pinyin_name in PINYIN_TO_CHINESE:
        return PINYIN_TO_CHINESE[pinyin_name]  # 返回对应中文名

    # 如果直接匹配失败，尝试去掉后缀再匹配
    if "_" in pinyin_name:  # 检查是否包含下划线（有后缀）
        base_name = pinyin_name.rsplit("_", 1)[0]  # 从右侧分割，去掉最后一个后缀
        if base_name in PINYIN_BASE_TO_CHINESE:  # 检查基础拼音是否在映射中
            return PINYIN_BASE_TO_CHINESE[base_name]  # 返回对应中文名

    # 都找不到则返回原拼音名
    return pinyin_name


# ========== 按分路分类的英雄列表 ==========
# LANE_HEROES字典定义了每个分路对应的中文英雄名列表
LANE_HEROES = {
    "lane_top": [  # 对抗路
        "蚩奼",
        "马超",
        "元歌",
        "关羽",
        "狂铁",
        "夏洛特",
        "司空震",
        "蒙恬",
        "哪吒",
        "老夫子",
        "花木兰",
        "曹操",
        "影",
        "孙策",
        "姬小满",
        "杨戬",
        "梦奇",
        "东皇太一",
        "达摩",
        "猪八戒",
        "项羽",
        "李信",
        "大司命",
        "白起",
        "芈月",
        "海诺",
        "貂蝉",
        "橘右京",
        "钟无艳",
        "亚瑟",
        "刘邦",
        "夏侯惇",
        "赵怀真",
        "元流之子(坦)",
        "程咬金",
        "廉颇",
        "吕布",
        "亚连",
        "铠",
        "盘古",
        "苏烈",
    ],
    "lane_mid": [  # 中路
        "女娲",
        "嫦娥",
        "干将莫邪",
        "海月",
        "沈梦溪",
        "甄姬",
        "西施",
        "诸葛亮",
        "杨玉环",
        "不知火舞",
        "小乔",
        "上官婉儿",
        "貂蝉",
        "高渐离",
        "武则天",
        "海诺",
        "弈星",
        "张良",
        "安琪拉",
        "妲己",
        "王昭君",
        "米莱狄",
        "周瑜",
        "墨子",
        "扁鹊",
        "金蝉",
        "嬴政",
        "元流之子(法)",
        "姜子牙",
        "大乔",
        "司马懿",
    ],
    "lane_adc": [  # 发育路
        "敖隐",
        "公孙离",
        "艾琳",
        "戈娅",
        "狄仁杰",
        "孙尚香",
        "虞姬",
        "孙权",
        "后羿",
        "鲁班七号",
        "百里守约",
        "莱西奥",
        "马可波罗",
        "李元芳",
        "伽罗",
        "黄忠",
        "蒙犽",
        "苍",
        "元流之子(射)",
        "阿古朵",
    ],
    "lane_jungle": [  # 打野
        "云缨",
        "镜",
        "裴擒虎",
        "韩信",
        "赵云",
        "阿古朵",
        "露娜",
        "百里玄策",
        "孙悟空",
        "雅典娜",
        "刘备",
        "典韦",
        "盘古",
        "东方曜",
        "云中君",
        "李白",
        "阿轲",
        "兰陵王",
        "娜可露露",
        "赵怀真",
        "猪八戒",
        "元流之子(坦)",
        "梦奇",
        "夏侯惇",
        "马超",
        "司空震",
        "曹操",
        "大司命",
        "影",
        "哪吒",
        "李元芳",
        "暃",
        "宫本武藏",
        "铠",
        "澜",
        "司马懿",
        "芈月",
        "亚瑟",
        "诸葛亮",
        "苍",
        "蚩奼",
        "橘右京",
        "孙策",
        "杨戬",
        "杨玉环",
        "钟无艳",
        "嫦娥",
    ],
    "lane_support": [  # 游走
        "大禹",
        "墨子",
        "少司缘",
        "空空儿",
        "张飞",
        "苏烈",
        "庄周",
        "大乔",
        "朵莉亚",
        "桑启",
        "瑶",
        "鲁班大师",
        "鬼谷子",
        "刘禅",
        "张良",
        "廉颇",
        "钟馗",
        "东皇太一",
        "蔡文姬",
        "孙膑",
        "刘邦",
        "太乙真人",
        "姜子牙",
        "牛魔",
        "王昭君",
        "夏侯惇",
        "项羽",
        "盾山",
        "明世隐",
        "元流之子(辅)",
        "赵怀真",
        "金蝉",
        "杨玉环",
    ],
}

# ========== 分路中文名映射 ==========
# LANE_NAME_MAP字典将分路代码映射为中文分路名称
LANE_NAME_MAP = {
    "lane_top": "对抗路",  # 上路
    "lane_jungle": "打野",  # 野区
    "lane_mid": "中路",  # 中路
    "lane_adc": "发育路",  # 下路/射手路
    "lane_support": "游走",  # 辅助
}

# ========== 英雄到分路的反向映射 ==========
# HERO_LANE_MAP字典通过遍历LANE_HEROES自动生成
# 键为英雄中文名，值为所属分路代码
HERO_LANE_MAP = {}
for lane, heroes in LANE_HEROES.items():  # 遍历每个分路及其英雄列表
    for hero in heroes:  # 遍历该分路的每个英雄
        if hero not in HERO_LANE_MAP:  # 一个英雄可能在多个分路，保留第一个
            HERO_LANE_MAP[hero] = lane  # 建立英雄到分路的映射关系


# ========== 分路相关辅助函数 ==========


def get_heroes_by_lane(lane: str) -> list:
    """
    获取指定分路的所有英雄

    功能说明：
        根据分路代码查询该分路下的所有英雄中文名

    参数说明：
        lane: 分路类型字符串，如 'lane_support'、'lane_adc' 等

    返回值说明：
        list: 该分路下所有英雄的中文名列表，如果分路不存在则返回空列表
    """
    return LANE_HEROES.get(lane, [])  # 使用get方法，不存在时返回空列表


def get_lane_by_hero(hero: str) -> str | None:
    """
    获取英雄所属分路

    功能说明：
        根据英雄中文名或拼音名查询该英雄所属的分路

    参数说明：
        hero: 英雄名字符串，可以是中文名或拼音名，如 '瑶'、'yao' 等

    返回值说明：
        str | None: 分路类型字符串，如 'lane_support'，如果英雄不存在则返回 None
    """
    # 首先尝试作为中文名查询
    if hero in HERO_LANE_MAP:
        return HERO_LANE_MAP[hero]
    # 如果失败，尝试将拼音转换为中文名再查询
    chinese_name = get_hero_chinese(hero)
    if chinese_name != hero and chinese_name in HERO_LANE_MAP:
        return HERO_LANE_MAP[chinese_name]
    return None  # 都找不到则返回None


def get_hero_chinese_name(pinyin: str) -> str:
    """
    获取英雄中文名

    功能说明：
        将英雄拼音名转换为中文名

    参数说明：
        pinyin: 英雄拼音名字符串

    返回值说明：
        str: 英雄中文名，如果找不到映射则返回原拼音名
    """
    return get_hero_chinese(pinyin)  # 复用get_hero_chinese函数
