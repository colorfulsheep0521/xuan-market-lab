#!/usr/bin/env python3
"""Run an independent A-share xuanxue market lab.

This standalone module provides cultural-model signals and research tools.
It reads local daily bars and stock labels, builds a symbolic culture-model
profile, runs a simple rebalance simulation, and writes standalone outputs.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


ELEMENTS = ["wood", "fire", "earth", "metal", "water"]
ELEMENT_CN = {
    "wood": "木",
    "fire": "火",
    "earth": "土",
    "metal": "金",
    "water": "水",
}
GENERATES = {
    "wood": "fire",
    "fire": "earth",
    "earth": "metal",
    "metal": "water",
    "water": "wood",
}
CONTROLS = {
    "wood": "earth",
    "earth": "water",
    "water": "fire",
    "fire": "metal",
    "metal": "wood",
}
STEMS = list("甲乙丙丁戊己庚辛壬癸")
BRANCHES = list("子丑寅卯辰巳午未申酉戌亥")
STEM_COLOR = {
    "甲": "青",
    "乙": "青",
    "丙": "赤",
    "丁": "赤",
    "戊": "黄",
    "己": "黄",
    "庚": "白",
    "辛": "白",
    "壬": "黑",
    "癸": "黑",
}
BRANCH_ZODIAC = {
    "子": "鼠",
    "丑": "牛",
    "寅": "虎",
    "卯": "兔",
    "辰": "龙",
    "巳": "蛇",
    "午": "马",
    "未": "羊",
    "申": "猴",
    "酉": "鸡",
    "戌": "狗",
    "亥": "猪",
}
BRANCH_DIRECTION = {
    "子": "北",
    "丑": "东北",
    "寅": "东",
    "卯": "东",
    "辰": "东南",
    "巳": "东南",
    "午": "南",
    "未": "西南",
    "申": "西南",
    "酉": "西",
    "戌": "西北",
    "亥": "西北",
}
STEM_AUSPICIOUS_DIRECTION = {
    "甲": "东",
    "乙": "东南",
    "丙": "南",
    "丁": "南",
    "戊": "中",
    "己": "中",
    "庚": "西",
    "辛": "西北",
    "壬": "北",
    "癸": "北",
}
STEM_WEALTH_DIRECTION = {
    "甲": "东北",
    "乙": "东",
    "丙": "西南",
    "丁": "南",
    "戊": "北",
    "己": "西北",
    "庚": "东",
    "辛": "东南",
    "壬": "南",
    "癸": "西南",
}
NAYIN_BY_PAIR = {
    ("甲", "子"): "海中金", ("乙", "丑"): "海中金",
    ("丙", "寅"): "炉中火", ("丁", "卯"): "炉中火",
    ("戊", "辰"): "大林木", ("己", "巳"): "大林木",
    ("庚", "午"): "路旁土", ("辛", "未"): "路旁土",
    ("壬", "申"): "剑锋金", ("癸", "酉"): "剑锋金",
    ("甲", "戌"): "山头火", ("乙", "亥"): "山头火",
    ("丙", "子"): "涧下水", ("丁", "丑"): "涧下水",
    ("戊", "寅"): "城头土", ("己", "卯"): "城头土",
    ("庚", "辰"): "白蜡金", ("辛", "巳"): "白蜡金",
    ("壬", "午"): "杨柳木", ("癸", "未"): "杨柳木",
    ("甲", "申"): "泉中水", ("乙", "酉"): "泉中水",
    ("丙", "戌"): "屋上土", ("丁", "亥"): "屋上土",
    ("戊", "子"): "霹雳火", ("己", "丑"): "霹雳火",
    ("庚", "寅"): "松柏木", ("辛", "卯"): "松柏木",
    ("壬", "辰"): "长流水", ("癸", "巳"): "长流水",
    ("甲", "午"): "砂中金", ("乙", "未"): "砂中金",
    ("丙", "申"): "山下火", ("丁", "酉"): "山下火",
    ("戊", "戌"): "平地木", ("己", "亥"): "平地木",
    ("庚", "子"): "壁上土", ("辛", "丑"): "壁上土",
    ("壬", "寅"): "金箔金", ("癸", "卯"): "金箔金",
    ("甲", "辰"): "覆灯火", ("乙", "巳"): "覆灯火",
    ("丙", "午"): "天河水", ("丁", "未"): "天河水",
    ("戊", "申"): "大驿土", ("己", "酉"): "大驿土",
    ("庚", "戌"): "钗钏金", ("辛", "亥"): "钗钏金",
    ("壬", "子"): "桑柘木", ("癸", "丑"): "桑柘木",
    ("甲", "寅"): "大溪水", ("乙", "卯"): "大溪水",
    ("丙", "辰"): "沙中土", ("丁", "巳"): "沙中土",
    ("戊", "午"): "天上火", ("己", "未"): "天上火",
    ("庚", "申"): "石榴木", ("辛", "酉"): "石榴木",
    ("壬", "戌"): "大海水", ("癸", "亥"): "大海水",
}
STEM_ELEMENT = {
    "甲": "wood",
    "乙": "wood",
    "丙": "fire",
    "丁": "fire",
    "戊": "earth",
    "己": "earth",
    "庚": "metal",
    "辛": "metal",
    "壬": "water",
    "癸": "water",
}
BRANCH_ELEMENT = {
    "寅": "wood",
    "卯": "wood",
    "巳": "fire",
    "午": "fire",
    "辰": "earth",
    "戌": "earth",
    "丑": "earth",
    "未": "earth",
    "申": "metal",
    "酉": "metal",
    "亥": "water",
    "子": "water",
}
TRIGRAM_ELEMENT = {
    "震": "wood",
    "巽": "wood",
    "离": "fire",
    "坤": "earth",
    "艮": "earth",
    "乾": "metal",
    "兑": "metal",
    "坎": "water",
}
TRIGRAMS = list(TRIGRAM_ELEMENT)
LINE_META = {
    1: {"name": "初爻", "phase": "潜藏初动", "hold_delta": 2, "buy": ("未正", "14:00"), "sell": ("未末", "14:50")},
    2: {"name": "二爻", "phase": "得中可进", "hold_delta": 1, "buy": ("巳正", "10:15"), "sell": ("未正", "14:20")},
    3: {"name": "三爻", "phase": "多凶多变", "hold_delta": -1, "buy": ("午末", "11:15"), "sell": ("午末", "11:20")},
    4: {"name": "四爻", "phase": "近君待时", "hold_delta": 1, "buy": ("未初", "13:15"), "sell": ("未末", "14:45")},
    5: {"name": "五爻", "phase": "中正当位", "hold_delta": -2, "buy": ("巳初", "09:45"), "sell": ("未正", "14:20")},
    6: {"name": "上爻", "phase": "亢极将变", "hold_delta": -3, "buy": ("未末", "14:40"), "sell": ("午末", "11:20")},
}
TRIGRAM_META = {
    "乾": {"image": "天", "direction": "西北", "nature": "健", "phase": "主动上行", "time": "巳正", "trade": "强势可持，忌贪满"},
    "兑": {"image": "泽", "direction": "西", "nature": "悦", "phase": "兑现收敛", "time": "巳正", "trade": "有利兑现，快进快出"},
    "离": {"image": "火", "direction": "南", "nature": "明", "phase": "显露外放", "time": "巳正", "trade": "明牌行情，宜短不宜恋"},
    "震": {"image": "雷", "direction": "东", "nature": "动", "phase": "发动初起", "time": "巳初", "trade": "发动开仓，快打快收"},
    "巽": {"image": "风", "direction": "东南", "nature": "入", "phase": "渐入渗透", "time": "巳正", "trade": "顺势切入，分批不躁"},
    "坎": {"image": "水", "direction": "北", "nature": "险", "phase": "险中求机", "time": "未正", "trade": "先观后动，尾盘低吸"},
    "艮": {"image": "山", "direction": "东北", "nature": "止", "phase": "止而后定", "time": "未正", "trade": "慢买慢卖，等待确认"},
    "坤": {"image": "地", "direction": "西南", "nature": "顺", "phase": "承载蓄势", "time": "未正", "trade": "厚重承接，偏长周期"},
}
ELEMENT_META = {
    "wood": {"yin_yang": "少阳", "season": "春", "organ": "肝胆", "direction": "东", "trade": "生发扩张，宜顺势启动"},
    "fire": {"yin_yang": "太阳", "season": "夏", "organ": "心小肠", "direction": "南", "trade": "外放明亮，宜快进快出"},
    "earth": {"yin_yang": "中气", "season": "长夏", "organ": "脾胃", "direction": "中", "trade": "承载转化，宜等确认"},
    "metal": {"yin_yang": "少阴", "season": "秋", "organ": "肺大肠", "direction": "西", "trade": "肃杀收敛，宜择强兑现"},
    "water": {"yin_yang": "太阴", "season": "冬", "organ": "肾膀胱", "direction": "北", "trade": "伏藏流动，宜低吸潜伏"},
}
TRIGRAM_HOLD_DAYS = {
    "震": 3,  # 雷动，快进快出
    "离": 4,  # 火明而躁，短持
    "兑": 5,  # 泽悦，有兑现之象
    "巽": 6,  # 风入，渐进
    "坎": 7,  # 水险，七日来复，等确认
    "艮": 8,  # 山止，持而观
    "坤": 9,  # 地载，厚重
    "乾": 9,  # 天行健，完整阳数
}
ELEMENT_HOLD_DAYS = {
    "wood": 6,
    "fire": 4,
    "earth": 7,
    "metal": 5,
    "water": 8,
}
LONG_ELEMENT_DAYS = {
    "wood": 21,   # 春生，三七成势
    "fire": 13,   # 火势快，十三日取明
    "earth": 34,  # 土厚，五七近中宫
    "metal": 21,  # 金主收敛，三七兑现
    "water": 34,  # 水主伏藏，五七待复
}
PIVOT_SOLAR_TERMS = {"立春", "春分", "立夏", "夏至", "立秋", "秋分", "立冬", "冬至"}
GROWTH_SOLAR_TERMS = {"立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏", "小满", "芒种"}
HARVEST_SOLAR_TERMS = {"立秋", "处暑", "白露", "秋分", "寒露", "霜降"}
STORAGE_SOLAR_TERMS = {"立冬", "小雪", "大雪", "冬至", "小寒", "大寒"}
INTRADAY_TIMES = {
    "发动开仓": ("巳初", "09:45", "未末", "14:45"),
    "明兑现仓": ("巳正", "10:30", "午末", "11:20"),
    "转气试仓": ("未初", "13:15", "未末", "14:45"),
    "平气可仓": ("巳正", "10:15", "未正", "14:15"),
    "伏藏低吸": ("未正", "14:00", "未末", "14:50"),
    "收敛择仓": ("午末", "11:15", "未正", "14:20"),
    "阴守小仓": ("未初", "13:30", "未末", "14:40"),
    "险止观察": ("未正", "14:00", "未末", "14:50"),
}
SHICHEN_WINDOWS = {
    "巳初": ("09:35", "09:59"),
    "巳正": ("10:00", "10:44"),
    "午末": ("11:00", "11:25"),
    "未初": ("13:05", "13:35"),
    "未正": ("13:36", "14:20"),
    "未末": ("14:21", "14:55"),
}
MANSIONS_28 = [
    ("角", "wood", "东", "吉", "青龙角，主生发开端"),
    ("亢", "metal", "东", "凶", "亢极易争，忌追满"),
    ("氐", "earth", "东", "平", "根基入地，宜守不宜躁"),
    ("房", "fire", "东", "吉", "房日明堂，宜开仓承接"),
    ("心", "fire", "东", "凶", "心火过烈，忌恋战"),
    ("尾", "fire", "东", "吉", "尾火续势，宜顺势"),
    ("箕", "water", "东", "平", "风水相荡，宜观察"),
    ("斗", "wood", "北", "吉", "斗柄开机，宜启新"),
    ("牛", "earth", "北", "凶", "牛宿滞重，忌强开"),
    ("女", "earth", "北", "凶", "女宿收敛，宜守"),
    ("虚", "water", "北", "凶", "虚宿空耗，忌新仓"),
    ("危", "water", "北", "凶", "危宿险象，先观"),
    ("室", "fire", "北", "吉", "室宿成屋，宜承载"),
    ("壁", "water", "北", "吉", "壁宿藏书，宜伏藏"),
    ("奎", "wood", "西", "吉", "奎木文章，宜名声题材"),
    ("娄", "metal", "西", "吉", "娄金聚敛，宜择强"),
    ("胃", "earth", "西", "平", "胃土纳气，宜分批"),
    ("昴", "metal", "西", "凶", "昴日肃杀，宜兑现"),
    ("毕", "metal", "西", "吉", "毕月成形，宜持成器"),
    ("觜", "fire", "西", "凶", "觜火口舌，忌躁进"),
    ("参", "water", "西", "平", "参宿参差，宜辨强弱"),
    ("井", "water", "南", "吉", "井水通源，宜低吸"),
    ("鬼", "metal", "南", "凶", "鬼宿阴耗，忌新开"),
    ("柳", "wood", "南", "凶", "柳木摇摆，忌恋战"),
    ("星", "fire", "南", "吉", "星日明现，宜明牌快取"),
    ("张", "fire", "南", "吉", "张月张扬，宜显露题材"),
    ("翼", "fire", "南", "平", "翼火飞扬，宜轻仓"),
    ("轸", "water", "南", "吉", "轸水收车，宜收束兑现"),
]
JIANCHU_12 = [
    ("建", "开端立事", 1, 1),
    ("除", "去旧布新", 0, 0),
    ("满", "气满易溢", -1, -1),
    ("平", "平气可仓", 0, 0),
    ("定", "定气可持", 1, 1),
    ("执", "执守不放", 0, 1),
    ("破", "破局勿新", -2, -2),
    ("危", "危中观望", -1, -1),
    ("成", "成事可入", 2, 1),
    ("收", "收敛兑现", -1, -1),
    ("开", "开门可入", 2, 1),
    ("闭", "闭门不入", -3, -2),
]
DAY_DEITIES_12 = [
    ("青龙", "吉", "青龙主生发，宜新开"),
    ("明堂", "吉", "明堂主明现，宜承接"),
    ("天刑", "凶", "天刑主约束，忌强攻"),
    ("朱雀", "凶", "朱雀主口舌，忌躁进"),
    ("金匮", "吉", "金匮主成器，宜择强"),
    ("天德", "吉", "天德主化解，可小仓"),
    ("白虎", "凶", "白虎主肃杀，宜兑现"),
    ("玉堂", "吉", "玉堂主贵气，宜守正"),
    ("天牢", "凶", "天牢主困，忌新仓"),
    ("玄武", "凶", "玄武主伏暗，先观"),
    ("司命", "吉", "司命主有序，宜按正候"),
    ("勾陈", "凶", "勾陈主滞，忌拖泥"),
]
NINE_STARS = {
    1: ("一白", "water", "北", "吉", "一白贪狼，主流动人气"),
    2: ("二黑", "earth", "西南", "凶", "二黑巨门，主滞重病符"),
    3: ("三碧", "wood", "东", "凶", "三碧禄存，主争动"),
    4: ("四绿", "wood", "东南", "吉", "四绿文曲，主名声技术"),
    5: ("五黄", "earth", "中", "凶", "五黄廉贞，主大忌中宫"),
    6: ("六白", "metal", "西北", "吉", "六白武曲，主权柄金气"),
    7: ("七赤", "metal", "西", "平", "七赤破军，主兑现口舌"),
    8: ("八白", "earth", "东北", "吉", "八白左辅，主承载财气"),
    9: ("九紫", "fire", "南", "吉", "九紫右弼，主火明喜庆"),
}
OPPOSITE_BRANCH = {
    "子": "午", "丑": "未", "寅": "申", "卯": "酉", "辰": "戌", "巳": "亥",
    "午": "子", "未": "丑", "申": "寅", "酉": "卯", "戌": "辰", "亥": "巳",
}
SAN_SHA_DIRECTION = {
    "申": "南", "子": "南", "辰": "南",
    "寅": "北", "午": "北", "戌": "北",
    "亥": "西", "卯": "西", "未": "西",
    "巳": "东", "酉": "东", "丑": "东",
}
BRANCH_LIUHE = {
    "子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯",
    "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午",
}
BRANCH_LIUHAI = {
    "子": "未", "未": "子", "丑": "午", "午": "丑", "寅": "巳", "巳": "寅",
    "卯": "辰", "辰": "卯", "申": "亥", "亥": "申", "酉": "戌", "戌": "酉",
}
BRANCH_SANHE = [
    ({"申", "子", "辰"}, "water", "水局"),
    ({"亥", "卯", "未"}, "wood", "木局"),
    ({"寅", "午", "戌"}, "fire", "火局"),
    ({"巳", "酉", "丑"}, "metal", "金局"),
]
BRANCH_SANXING = [
    ({"寅", "巳", "申"}, "无恩三刑"),
    ({"丑", "戌", "未"}, "恃势三刑"),
    ({"子", "卯"}, "无礼之刑"),
    ({"辰"}, "自刑"),
    ({"午"}, "自刑"),
    ({"酉"}, "自刑"),
    ({"亥"}, "自刑"),
]
KONGWANG_BY_XUN = {
    0: ("戌", "亥"),
    1: ("申", "酉"),
    2: ("午", "未"),
    3: ("辰", "巳"),
    4: ("寅", "卯"),
    5: ("子", "丑"),
}
NOBLEMAN_BRANCHES = {
    "甲": ("丑", "未"), "戊": ("丑", "未"), "庚": ("丑", "未"),
    "乙": ("子", "申"), "己": ("子", "申"),
    "丙": ("亥", "酉"), "丁": ("亥", "酉"),
    "壬": ("卯", "巳"), "癸": ("卯", "巳"),
    "辛": ("寅", "午"),
}
PEACH_BLOSSOM_BRANCH = {
    "申": "酉", "子": "酉", "辰": "酉",
    "寅": "卯", "午": "卯", "戌": "卯",
    "亥": "子", "卯": "子", "未": "子",
    "巳": "午", "酉": "午", "丑": "午",
}
TRAVEL_HORSE_BRANCH = {
    "申": "寅", "子": "寅", "辰": "寅",
    "寅": "申", "午": "申", "戌": "申",
    "亥": "巳", "卯": "巳", "未": "巳",
    "巳": "亥", "酉": "亥", "丑": "亥",
}
HUAGAI_BRANCH = {
    "申": "辰", "子": "辰", "辰": "辰",
    "寅": "戌", "午": "戌", "戌": "戌",
    "亥": "未", "卯": "未", "未": "未",
    "巳": "丑", "酉": "丑", "丑": "丑",
}
LU_BRANCH = {
    "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
    "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子",
}
YANG_REN_BRANCH = {
    "甲": "卯", "乙": "寅", "丙": "午", "丁": "巳", "戊": "午",
    "己": "巳", "庚": "酉", "辛": "申", "壬": "子", "癸": "亥",
}
QIMEN_DOORS = [
    ("休门", "water", "北", "吉", "宜伏藏低吸"),
    ("生门", "earth", "东北", "吉", "宜新开求生"),
    ("伤门", "wood", "东", "凶", "伤气勿追"),
    ("杜门", "wood", "东南", "平", "闭塞守候"),
    ("景门", "fire", "南", "吉", "明现可取"),
    ("死门", "earth", "西南", "凶", "闭绝不入"),
    ("惊门", "metal", "西", "凶", "惊扰快退"),
    ("开门", "metal", "西北", "吉", "门户大开"),
]
QIMEN_STARS = ["蓬", "任", "冲", "辅", "英", "芮", "柱", "心"]
QIMEN_DEITIES = ["值符", "腾蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天"]
DECISION_LAYERS = [
    ("年运", "年干支、生肖色象、纳音，定年度大气"),
    ("太岁星曜", "太岁、岁破、三煞、九星，定年度方位禁忌和星气"),
    ("节气月令", "节气和季节，定旺衰进退"),
    ("宿曜黄历", "二十八宿、建除十二神、值日星神、月相，定今日仓门"),
    ("日课", "日干支、主气辅气、日卦，定当天可否发动"),
    ("行业五行", "行业归类，定股票本体用神"),
    ("名字字象", "名称文字，定外显象意"),
    ("代码象数", "尾数五行、重卦、动爻，定操作细节"),
    ("盘中时辰", "巳午未三时再细分到分钟"),
]
TAIL_ELEMENT = {
    "1": "water",
    "6": "water",
    "2": "fire",
    "7": "fire",
    "3": "wood",
    "8": "wood",
    "4": "metal",
    "9": "metal",
    "5": "earth",
    "0": "earth",
}

INDUSTRY_ELEMENT_KEYWORDS = {
    "wood": [
        "农",
        "林",
        "牧",
        "渔",
        "医药",
        "生物",
        "环保",
        "教育",
        "造纸",
        "家居",
        "美容",
    ],
    "fire": [
        "电子",
        "计算机",
        "通信",
        "传媒",
        "电力设备",
        "新能源",
        "汽车",
        "军工",
        "游戏",
        "影视",
    ],
    "earth": [
        "房地产",
        "建筑",
        "建材",
        "煤炭",
        "公用事业",
        "水泥",
        "钢铁",
        "基础化工",
        "综合",
    ],
    "metal": [
        "银行",
        "非银金融",
        "证券",
        "保险",
        "机械",
        "有色金属",
        "金属",
        "国防军工",
        "家用电器",
    ],
    "water": [
        "交通运输",
        "航运",
        "港口",
        "物流",
        "商贸零售",
        "社会服务",
        "食品饮料",
        "互联网",
        "旅游",
    ],
}

NAME_ELEMENT_CHARS = {
    "wood": "木林森药春生华荣禾竹青苗康仁",
    "fire": "火光阳明电星日晶热红炎辉耀智",
    "earth": "土山石城基建地矿田安稳厚坤",
    "metal": "金银钢铜铁锋锐鑫创器机财证",
    "water": "水海江河湖洋港航泉流雨云润泽",
}
NAME_CHAR_EXPLAIN = {
    char: f"字象取{ELEMENT_CN[element]}，{ELEMENT_META[element]['trade']}"
    for element, chars in NAME_ELEMENT_CHARS.items()
    for char in chars
}

SOLAR_TERMS_FIXED = [
    ((1, 6), "小寒", "water"),
    ((1, 20), "大寒", "water"),
    ((2, 4), "立春", "wood"),
    ((2, 19), "雨水", "wood"),
    ((3, 6), "惊蛰", "wood"),
    ((3, 21), "春分", "wood"),
    ((4, 5), "清明", "wood"),
    ((4, 20), "谷雨", "earth"),
    ((5, 6), "立夏", "fire"),
    ((5, 21), "小满", "fire"),
    ((6, 6), "芒种", "fire"),
    ((6, 21), "夏至", "fire"),
    ((7, 7), "小暑", "fire"),
    ((7, 23), "大暑", "earth"),
    ((8, 8), "立秋", "metal"),
    ((8, 23), "处暑", "metal"),
    ((9, 8), "白露", "metal"),
    ((9, 23), "秋分", "metal"),
    ((10, 8), "寒露", "metal"),
    ((10, 23), "霜降", "earth"),
    ((11, 7), "立冬", "water"),
    ((11, 22), "小雪", "water"),
    ((12, 7), "大雪", "water"),
    ((12, 22), "冬至", "water"),
]


@dataclass
class Paths:
    daily_dir: Path
    labels_path: Path
    locations_path: Path
    output_dir: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run XuanMarket Lab.")
    parser.add_argument("--daily-dir", default="data/raw/daily")
    parser.add_argument("--labels", default="data/raw/a_share_industry_concept_labels.csv")
    parser.add_argument("--locations", default="data/company_locations.csv")
    parser.add_argument("--output-dir", default="outputs/research")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--max-stocks", type=int, default=800, help="0 means all local stocks.")
    parser.add_argument("--positions", type=int, default=0, help="Hard cap for open names; 0 means use each day's recommended_count without a manual cap.")
    parser.add_argument("--rebalance-days", type=int, default=5)
    parser.add_argument(
        "--hold-mode",
        choices=["xuan", "fixed"],
        default="xuan",
        help="xuan derives holding time from qi; fixed uses --rebalance-days.",
    )
    parser.add_argument(
        "--cycle-mode",
        choices=["hierarchical", "short", "long", "mixed"],
        default="hierarchical",
        help="hierarchical derives the horizon from year -> solar term -> day -> stock layers.",
    )
    parser.add_argument(
        "--buy-gate",
        choices=["none", "soft", "strict"],
        default="soft",
        help="soft waits on avoid days for new entries; strict only buys on open days.",
    )
    parser.add_argument("--initial-cash", type=float, default=100000.0)
    parser.add_argument("--fee-rate", type=float, default=0.001)
    parser.add_argument("--candidate-top-n", type=int, default=30)
    return parser.parse_args()


def empty_element_scores() -> dict[str, float]:
    return {element: 0.0 for element in ELEMENTS}


def normalize(scores: dict[str, float]) -> dict[str, float]:
    total = sum(max(v, 0.0) for v in scores.values())
    if total <= 0:
        return {element: 1.0 / len(ELEMENTS) for element in ELEMENTS}
    return {element: max(scores[element], 0.0) / total for element in ELEMENTS}


def yin_yang_for_element(element: str) -> str:
    return "阳" if element in {"wood", "fire"} else "阴" if element in {"metal", "water"} else "中"


def ganzhi_symbol(ganzhi: str) -> dict[str, str]:
    stem, branch = ganzhi[0], ganzhi[1]
    color = STEM_COLOR[stem]
    zodiac = BRANCH_ZODIAC[branch]
    nayin = NAYIN_BY_PAIR.get((stem, branch), "")
    return {
        "color": color,
        "zodiac": zodiac,
        "nayin": nayin,
        "alias": f"{color}{zodiac}",
        "note": f"{ganzhi}取{color}{zodiac}，纳音{nayin}",
    }


def digital_root(value: int) -> int:
    while value > 9:
        value = sum(int(char) for char in str(value))
    return value or 9


def annual_flying_star(year: int) -> int:
    # Common almanac engineering approximation: 2024->三碧, 2025->二黑, 2026->一白.
    star = 11 - digital_root(year)
    while star <= 0:
        star += 9
    while star > 9:
        star -= 9
    return star


def moon_phase_for_date(date: pd.Timestamp) -> dict[str, str]:
    new_moon_anchor = pd.Timestamp("2000-01-06 18:14")
    age = ((date.normalize() - new_moon_anchor).total_seconds() / 86400.0) % 29.53058867
    if age < 2 or age >= 28:
        return {"moon_phase": "朔", "moon_element": "water", "moon_note": "朔月气伏，宜观不宜躁"}
    if 6 <= age < 9:
        return {"moon_phase": "上弦", "moon_element": "wood", "moon_note": "上弦气升，宜生发试仓"}
    if 13 <= age < 17:
        return {"moon_phase": "望", "moon_element": "fire", "moon_note": "望月气满，明极防泄"}
    if 21 <= age < 24:
        return {"moon_phase": "下弦", "moon_element": "metal", "moon_note": "下弦气收，宜兑现择强"}
    if age < 13:
        return {"moon_phase": "渐盈", "moon_element": "wood", "moon_note": "月气渐盈，宜顺势"}
    return {"moon_phase": "渐亏", "moon_element": "metal", "moon_note": "月气渐亏，宜收敛"}


def astro_fortune_for_day(date: pd.Timestamp, year_gz: str, day_gz: str) -> dict[str, object]:
    anchor = pd.Timestamp("1984-02-02")
    offset = int((date.normalize() - anchor).days)
    mansion_name, mansion_element, mansion_direction, mansion_luck, mansion_note = MANSIONS_28[offset % 28]
    jian_name, jian_note, jian_gate_delta, jian_hold_delta = JIANCHU_12[offset % 12]
    deity_name, deity_luck, deity_note = DAY_DEITIES_12[offset % 12]

    star_no = annual_flying_star(date.year)
    star_name, star_element, star_direction, star_luck, star_note = NINE_STARS[star_no]
    day_star_no = (star_no + offset) % 9 + 1
    day_star_name, day_star_element, day_star_direction, day_star_luck, day_star_note = NINE_STARS[day_star_no]
    moon = moon_phase_for_date(date)

    tai_sui_branch = year_gz[1]
    sui_po_branch = OPPOSITE_BRANCH[tai_sui_branch]
    tai_sui_direction = BRANCH_DIRECTION[tai_sui_branch]
    sui_po_direction = BRANCH_DIRECTION[sui_po_branch]
    san_sha_direction = SAN_SHA_DIRECTION[tai_sui_branch]

    gate_score = jian_gate_delta
    if mansion_luck == "吉":
        gate_score += 1
    elif mansion_luck == "凶":
        gate_score -= 1
    if deity_luck == "吉":
        gate_score += 1
    else:
        gate_score -= 1
    if day_star_luck == "吉":
        gate_score += 1
    elif day_star_luck == "凶":
        gate_score -= 1
    if moon["moon_phase"] in {"望"}:
        gate_score -= 1
    elif moon["moon_phase"] in {"上弦", "渐盈"}:
        gate_score += 1

    if gate_score >= 3:
        gate = "开"
        gate_note = "星曜仓门开，可取新局"
    elif gate_score >= 0:
        gate = "半开"
        gate_note = "星曜仓门半开，择正候应象者"
    elif gate_score >= -2:
        gate = "守"
        gate_note = "星曜仓门偏守，主续持少新开"
    else:
        gate = "闭"
        gate_note = "星曜仓门闭，观气不强入"

    astro_note = (
        f"二十八宿{mansion_name}宿，{mansion_note}；"
        f"建除取{jian_name}，{jian_note}；值神{deity_name}，{deity_note}；"
        f"年飞星{star_name}临{star_direction}，{star_note}；"
        f"日飞星{day_star_name}临{day_star_direction}，{day_star_note}；"
        f"{moon['moon_phase']}，{moon['moon_note']}；"
        f"太岁在{tai_sui_direction}，岁破在{sui_po_direction}，三煞在{san_sha_direction}；"
        f"{gate_note}"
    )
    return {
        "mansion": mansion_name,
        "mansion_element": ELEMENT_CN[mansion_element],
        "mansion_element_key": mansion_element,
        "mansion_direction": mansion_direction,
        "mansion_luck": mansion_luck,
        "mansion_note": mansion_note,
        "jianchu": jian_name,
        "jianchu_note": jian_note,
        "jianchu_gate_delta": jian_gate_delta,
        "jianchu_hold_delta": jian_hold_delta,
        "day_deity": deity_name,
        "day_deity_luck": deity_luck,
        "day_deity_note": deity_note,
        "annual_star": star_name,
        "annual_star_no": star_no,
        "annual_star_element": ELEMENT_CN[star_element],
        "annual_star_element_key": star_element,
        "annual_star_direction": star_direction,
        "annual_star_luck": star_luck,
        "day_star": day_star_name,
        "day_star_no": day_star_no,
        "day_star_element": ELEMENT_CN[day_star_element],
        "day_star_element_key": day_star_element,
        "day_star_direction": day_star_direction,
        "day_star_luck": day_star_luck,
        "moon_phase": moon["moon_phase"],
        "moon_element": ELEMENT_CN[moon["moon_element"]],
        "moon_element_key": moon["moon_element"],
        "moon_note": moon["moon_note"],
        "tai_sui_direction": tai_sui_direction,
        "sui_po_direction": sui_po_direction,
        "san_sha_direction": san_sha_direction,
        "astro_gate_score": gate_score,
        "new_position_gate": gate,
        "new_position_note": gate_note,
        "astro_note": astro_note,
    }


def month_ganzhi_for_date(date: pd.Timestamp, year_gz: str) -> dict[str, str]:
    # Engineering approximation: month branch follows solar-term month order from 寅.
    month_branch_order = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"]
    month_index = (date.month - 2) % 12
    branch = month_branch_order[month_index]
    year_stem_index = STEMS.index(year_gz[0])
    stem = STEMS[(year_stem_index * 2 + month_index + 2) % 10]
    return {
        "month_ganzhi": stem + branch,
        "month_branch": branch,
        "month_element": ELEMENT_CN[BRANCH_ELEMENT[branch]],
        "month_note": f"月柱近似取{stem}{branch}，以节令月建定旺衰",
    }


def lunar_approx_for_date(date: pd.Timestamp) -> dict[str, str]:
    # Stable approximation for the symbolic layer; replaceable by a precise lunar calendar.
    new_moon_anchor = pd.Timestamp("2000-01-06 18:14")
    lunation = int(((date.normalize() - new_moon_anchor).total_seconds() / 86400.0) // 29.53058867)
    day = int(((date.normalize() - new_moon_anchor).total_seconds() / 86400.0) % 29.53058867) + 1
    month = lunation % 12 + 1
    return {
        "lunar_month_approx": str(month),
        "lunar_day_approx": str(day),
        "lunar_note": f"农历近似{month}月{day}日，用于月相和月建占位",
    }


def hour_pillars_for_trading_day(date: pd.Timestamp, day_gz: str) -> dict[str, str]:
    day_stem_index = STEMS.index(day_gz[0])
    branches = {"巳": "巳", "午": "午", "未": "未"}
    pillars = {}
    notes = []
    for label, branch in branches.items():
        branch_index = BRANCHES.index(branch)
        stem = STEMS[(day_stem_index * 2 + branch_index) % 10]
        pillars[f"{label}_pillar"] = stem + branch
        notes.append(f"{label}时取{stem}{branch}")
    pillars["hour_pillar_note"] = "；".join(notes)
    return pillars


def branch_relations_for_day(year_gz: str, month_gz: str, day_gz: str) -> dict[str, str]:
    year_branch, month_branch, day_branch = year_gz[1], month_gz[1], day_gz[1]
    branches = {year_branch, month_branch, day_branch}
    relations = []
    if OPPOSITE_BRANCH[day_branch] in {year_branch, month_branch}:
        relations.append(f"日支{day_branch}冲年/月支，主动荡")
    if BRANCH_LIUHE[day_branch] in {year_branch, month_branch}:
        relations.append(f"日支{day_branch}得六合，主合气")
    if BRANCH_LIUHAI[day_branch] in {year_branch, month_branch}:
        relations.append(f"日支{day_branch}见六害，主暗耗")
    for combo, element, name in BRANCH_SANHE:
        if len(branches & combo) >= 2:
            relations.append(f"年/月/日入{name}半合，助{ELEMENT_CN[element]}气")
    for combo, name in BRANCH_SANXING:
        if len(branches & combo) >= min(2, len(combo)):
            relations.append(f"年/月/日见{name}，忌躁")
    if not relations:
        relations.append("年/月/日支无大冲合，平参")
    return {
        "branch_relation_note": "；".join(relations),
        "day_clash_branch": OPPOSITE_BRANCH[day_branch],
        "day_liuhe_branch": BRANCH_LIUHE[day_branch],
        "day_liuhai_branch": BRANCH_LIUHAI[day_branch],
    }


def kongwang_for_day(day_gz: str) -> dict[str, str]:
    day_index = (STEMS.index(day_gz[0]) - BRANCHES.index(day_gz[1])) % 12
    xun_index = day_index // 2
    empty = KONGWANG_BY_XUN.get(xun_index, ("", ""))
    return {
        "kongwang": "/".join(empty),
        "kongwang_note": f"{day_gz}旬空取{empty[0]}{empty[1]}，落空者不强求",
    }


def shensha_for_day(day_gz: str) -> dict[str, str]:
    stem, branch = day_gz[0], day_gz[1]
    noble = NOBLEMAN_BRANCHES.get(stem, ("", ""))
    peach = PEACH_BLOSSOM_BRANCH[branch]
    horse = TRAVEL_HORSE_BRANCH[branch]
    huagai = HUAGAI_BRANCH[branch]
    lu = LU_BRANCH[stem]
    yang_ren = YANG_REN_BRANCH[stem]
    note = (
        f"天乙贵人在{noble[0]}{noble[1]}，得贵可扶；"
        f"驿马在{horse}，主动迁移；桃花在{peach}，主声量；"
        f"华盖在{huagai}，主孤高题材；禄神在{lu}，主得禄；"
        f"羊刃在{yang_ren}，主过刚易折"
    )
    return {
        "nobleman_branches": "/".join(noble),
        "travel_horse_branch": horse,
        "peach_blossom_branch": peach,
        "huagai_branch": huagai,
        "lu_branch": lu,
        "yang_ren_branch": yang_ren,
        "shensha_note": note,
    }


def qimen_for_day(date: pd.Timestamp, day_gz: str) -> dict[str, str]:
    offset = int((date.normalize() - pd.Timestamp("1984-02-02")).days)
    door_name, door_element, door_direction, door_luck, door_note = QIMEN_DOORS[offset % 8]
    star = QIMEN_STARS[(offset + STEMS.index(day_gz[0])) % 8]
    deity = QIMEN_DEITIES[(offset + BRANCHES.index(day_gz[1])) % 8]
    return {
        "qimen_door": door_name,
        "qimen_door_element": ELEMENT_CN[door_element],
        "qimen_door_direction": door_direction,
        "qimen_door_luck": door_luck,
        "qimen_star": star,
        "qimen_deity": deity,
        "qimen_note": f"奇门近似取{door_name}临{door_direction}，{door_note}；星{star}，神{deity}",
    }


def meihua_for_day(date: pd.Timestamp, day_gz: str) -> dict[str, str]:
    upper = TRIGRAMS[(date.year + date.month + date.day) % 8]
    lower = TRIGRAMS[(STEMS.index(day_gz[0]) + BRANCHES.index(day_gz[1])) % 8]
    moving = (date.year + date.month + date.day + STEMS.index(day_gz[0]) + 1) % 6 + 1
    body = upper if moving > 3 else lower
    use = lower if body == upper else upper
    return {
        "meihua_hexagram": f"{upper}上{lower}下",
        "meihua_moving_line": str(moving),
        "meihua_body": body,
        "meihua_use": use,
        "meihua_note": f"梅花近似起{upper}上{lower}下，{moving}爻动，体{body}用{use}",
    }


def almanac_for_day(
    year_gz: str,
    day_gz: str,
    term_name: str,
    main: str,
    secondary: str,
    trigram: str,
) -> dict[str, str]:
    day_stem, day_branch = day_gz[0], day_gz[1]
    favorable = [ELEMENT_CN[main], ELEMENT_CN[secondary], ELEMENT_CN[GENERATES[main]]]
    avoid = [ELEMENT_CN[CONTROLS[main]]]
    avoid = [element for element in avoid if element not in favorable]
    if not avoid:
        avoid = [ELEMENT_CN[CONTROLS[secondary]]]
    direction = BRANCH_DIRECTION[day_branch]
    auspicious_direction = STEM_AUSPICIOUS_DIRECTION[day_stem]
    wealth_direction = STEM_WEALTH_DIRECTION[day_stem]
    if trigram in {"震", "巽"}:
        yi = "宜发动、试仓、顺势切入"
        ji = "忌犹豫错过、忌重仓追满"
    elif trigram in {"离", "兑"}:
        yi = "宜快进快出、宜兑现"
        ji = "忌恋战"
    elif trigram in {"坎", "艮"}:
        yi = "宜观察、尾盘低吸"
        ji = "忌早盘重仓"
    else:
        yi = "宜承接、分批"
        ji = "忌急躁"
    if term_name in PIVOT_SOLAR_TERMS:
        yi += "、宜小仓"
        ji += "、忌大仓"
    return {
        "day_direction": direction,
        "auspicious_direction": auspicious_direction,
        "wealth_direction": wealth_direction,
        "favorable_elements": "/".join(favorable),
        "avoid_elements": "/".join(avoid),
        "yi": yi,
        "ji": ji,
        "almanac_note": (
            f"{day_gz}{ganzhi_symbol(day_gz)['alias']}日，方{direction}；"
            f"喜神取{auspicious_direction}，财位取{wealth_direction}；"
            f"{yi}；{ji}；用神偏{','.join(favorable)}，避{','.join(avoid)}"
        ),
    }


def derive_recommendation_plan(
    main: str,
    secondary: str,
    trigram: str,
    buy_phase: str,
    term_name: str,
    days_since_term: int,
    new_position_gate: str = "半开",
) -> dict[str, object]:
    count = 3
    reasons = []
    if buy_phase == "发动开仓":
        count += 2
        reasons.append("发动开仓，多取候选")
    elif buy_phase == "明兑现仓":
        count += 1
        reasons.append("明兑现仓，取中等数量")
    elif buy_phase in {"险止观察", "转气试仓", "阴守小仓"}:
        count -= 1
        reasons.append(f"{buy_phase}，少取候选")
    if trigram in {"震", "巽"}:
        count += 1
        reasons.append(f"{trigram}象主动，增一只")
    elif trigram in {"坎", "艮"}:
        count -= 1
        reasons.append(f"{trigram}象险止，减一只")
    if main in {"wood", "fire"} and secondary in {"wood", "fire", "metal"}:
        count += 1
        reasons.append("主气生发或明亮，扩到一组")
    if term_name in PIVOT_SOLAR_TERMS or days_since_term <= 2:
        count -= 1
        reasons.append("节气交接，只宜试仓")
    if new_position_gate == "开":
        count += 1
        reasons.append("星曜仓门开，增一只")
    elif new_position_gate == "守":
        count -= 1
        reasons.append("星曜仓门守，减一只")
    elif new_position_gate == "闭":
        count = 0
        reasons.append("星曜仓门闭，不开新仓")
    count = max(0, min(8, count))

    if count == 0:
        style = "今日无买"
        sizing = "不开新仓，只观旧局"
    elif count <= 2:
        style = "小仓试探"
        sizing = "单只不超过试验资金的10%-15%，宁少勿满"
    elif count <= 4:
        style = "分散择强"
        sizing = "等权或强者略重，单只约20%-30%观察仓"
    elif count <= 6:
        style = "一组发动"
        sizing = "分成一组，前二名略重，其余轻仓跟随"
    else:
        style = "广撒观察"
        sizing = "只做观察池，实买需再二次筛选，不宜全买"
    return {
        "recommended_count": count,
        "position_style": style,
        "sizing_note": sizing,
        "recommendation_note": "；".join(reasons) if reasons else "平气日，取三只为中",
    }


def code_digits(code: str) -> list[int]:
    return [int(char) for char in str(code) if char.isdigit()]


def minute_to_int(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def int_to_minute(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def refine_minute(shichen: str, code: str, moving_line: int, salt: int = 0) -> str:
    start_text, end_text = SHICHEN_WINDOWS[shichen]
    start, end = minute_to_int(start_text), minute_to_int(end_text)
    width = max(end - start, 1)
    digits = code_digits(code)
    seed = sum((idx + 1) * digit for idx, digit in enumerate(digits)) + moving_line * 7 + salt
    return int_to_minute(start + seed % (width + 1))


def code_hexagram(code: str) -> dict[str, object]:
    digits = code_digits(code)
    if not digits:
        return {
            "upper_trigram": "坤",
            "lower_trigram": "坤",
            "code_branch": "丑",
            "moving_line": 1,
            "hexagram_name": "坤上坤下",
            "hexagram_evidence": "代码无数字，取坤为地",
        }
    lower = TRIGRAMS[digits[-1] % len(TRIGRAMS)]
    upper = TRIGRAMS[sum(digits[:3] or digits) % len(TRIGRAMS)]
    weighted = sum((idx + 1) * digit for idx, digit in enumerate(digits))
    moving_line = weighted % 6 + 1
    code_branch = BRANCHES[weighted % 12]
    line = LINE_META[moving_line]
    return {
        "upper_trigram": upper,
        "lower_trigram": lower,
        "code_branch": code_branch,
        "moving_line": moving_line,
        "hexagram_name": f"{upper}上{lower}下",
        "hexagram_evidence": (
            f"代码数字{''.join(map(str, digits))}起象，"
            f"上卦{upper}({TRIGRAM_META[upper]['image']})，"
            f"下卦{lower}({TRIGRAM_META[lower]['image']})，"
            f"代码支取{code_branch}，{line['name']}动，{line['phase']}"
        ),
    }


def score_stock_profile(row: pd.Series) -> tuple[dict[str, float], dict[str, str]]:
    scores = empty_element_scores()
    text_fields = [
        str(row.get("industry_name", "")),
        str(row.get("sector_top_label", "")),
        str(row.get("sector_mid_label", "")),
        str(row.get("sector_label", "")),
    ]
    industry_text = " ".join(text_fields)
    industry_hits = []
    for element, keywords in INDUSTRY_ELEMENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword and keyword in industry_text:
                scores[element] += 3.0
                industry_hits.append(f"{keyword}->{ELEMENT_CN[element]}")

    name = str(row.get("code_name", ""))
    name_hits = []
    for element, chars in NAME_ELEMENT_CHARS.items():
        matched = [char for char in name if char in chars]
        scores[element] += 0.6 * len(matched)
        name_hits.extend(f"{char}->{ELEMENT_CN[element]}({NAME_CHAR_EXPLAIN.get(char, '字象归类')})" for char in matched)

    code = str(row.get("code", ""))
    tail = code[-1:] if code else ""
    code_tail_note = ""
    if tail in TAIL_ELEMENT:
        scores[TAIL_ELEMENT[tail]] += 1.0
        code_tail_note = f"尾数{tail}->{ELEMENT_CN[TAIL_ELEMENT[tail]]}"

    if str(row.get("code", "")).startswith("sh.688") or str(row.get("code", "")).startswith("sz.300"):
        scores["fire"] += 0.8
        scores["wood"] += 0.4
        board_note = "科创/创业->火木"
    else:
        board_note = ""

    evidence = {
        "industry_evidence": "|".join(industry_hits),
        "name_evidence": "|".join(name_hits),
        "code_evidence": "|".join(part for part in [code_tail_note, board_note] if part),
    }
    return normalize(scores), evidence


def load_location_profiles(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(
            columns=[
                "code",
                "registered_region",
                "registered_city",
                "registered_address",
                "registered_direction",
                "location_source",
            ]
        )
    return pd.read_csv(path).fillna("")


def build_stock_profiles(labels: pd.DataFrame, locations: pd.DataFrame | None = None) -> pd.DataFrame:
    location_map = {}
    if locations is not None and not locations.empty:
        location_map = locations.set_index("code").to_dict(orient="index")
    records = []
    for _, row in labels.iterrows():
        weights, evidence = score_stock_profile(row)
        primary = max(weights, key=weights.get)
        secondary = sorted(weights, key=weights.get, reverse=True)[1]
        code = str(row["code"])
        location = location_map.get(code, {})
        hexagram = code_hexagram(code)
        trigram = str(hexagram["lower_trigram"])
        trigram_meta = TRIGRAM_META[trigram]
        primary_meta = ELEMENT_META[primary]
        records.append(
            {
                "code": code,
                "code_name": row.get("code_name", ""),
                "industry": row.get("sector_top_label", row.get("industry_name", "")),
                "primary_element": ELEMENT_CN[primary],
                "secondary_element": ELEMENT_CN[secondary],
                "yin_yang": yin_yang_for_element(primary),
                "trigram": trigram,
                "upper_trigram": hexagram["upper_trigram"],
                "lower_trigram": hexagram["lower_trigram"],
                "code_branch": hexagram.get("code_branch", ""),
                "moving_line": hexagram["moving_line"],
                "hexagram_name": hexagram["hexagram_name"],
                "hexagram_evidence": hexagram["hexagram_evidence"],
                "registered_region": location.get("registered_region", ""),
                "registered_city": location.get("registered_city", ""),
                "registered_address": location.get("registered_address", ""),
                "registered_direction": location.get("registered_direction", ""),
                "location_source": location.get("location_source", ""),
                "location_evidence": (
                    f"注册地{location.get('registered_region', '')}{location.get('registered_city', '')}，"
                    f"方位取{location.get('registered_direction', '')}"
                    if location
                    else "注册地未入库，方位不参与加权"
                ),
                "trigram_evidence": (
                    f"{trigram}卦取{trigram_meta['image']}象，方{trigram_meta['direction']}，"
                    f"性{trigram_meta['nature']}，交易义：{trigram_meta['trade']}"
                ),
                "element_theory": (
                    f"{ELEMENT_CN[primary]}属{primary_meta['yin_yang']}，"
                    f"应{primary_meta['season']}令，方{primary_meta['direction']}，"
                    f"中医取{primary_meta['organ']}，交易义：{primary_meta['trade']}"
                ),
                "industry_evidence": evidence["industry_evidence"],
                "name_evidence": evidence["name_evidence"],
                "code_evidence": evidence["code_evidence"],
                "xuan_note": (
                    f"行业/名字/代码合参，{ELEMENT_CN[primary]}为主，"
                    f"{ELEMENT_CN[secondary]}为辅，{trigram}象"
                ),
                **{f"{element}_weight": weights[element] for element in ELEMENTS},
            }
        )
    return pd.DataFrame(records)


def ganzhi_year(year: int) -> str:
    return STEMS[(year - 4) % 10] + BRANCHES[(year - 4) % 12]


def ganzhi_day(date: pd.Timestamp) -> str:
    # 1984-02-02 is commonly used as a Jia-Zi day anchor in practical tools.
    anchor = pd.Timestamp("1984-02-02")
    offset = (date.normalize() - anchor).days
    return STEMS[offset % 10] + BRANCHES[offset % 12]


def fixed_solar_term(date: pd.Timestamp) -> tuple[str, str]:
    term_name, term_element = "冬至", "water"
    for (month, day), name, element in SOLAR_TERMS_FIXED:
        if (date.month, date.day) >= (month, day):
            term_name, term_element = name, element
    return term_name, term_element


def days_since_fixed_solar_term(date: pd.Timestamp) -> int:
    term_month, term_day = SOLAR_TERMS_FIXED[0][0]
    for (month, day), _, _ in SOLAR_TERMS_FIXED:
        if (date.month, date.day) >= (month, day):
            term_month, term_day = month, day
    term_date = pd.Timestamp(year=date.year, month=term_month, day=term_day)
    if term_date > date:
        term_date = pd.Timestamp(year=date.year - 1, month=12, day=22)
    return int((date.normalize() - term_date).days)


def season_element(month: int) -> str:
    if month in (2, 3, 4):
        return "wood"
    if month in (5, 6, 7):
        return "fire"
    if month in (8, 9, 10):
        return "metal"
    if month in (11, 12, 1):
        return "water"
    return "earth"


def build_daily_qi(dates: list[pd.Timestamp]) -> pd.DataFrame:
    records = []
    for date in dates:
        day_gz = ganzhi_day(date)
        year_gz = ganzhi_year(date.year)
        year_symbol = ganzhi_symbol(year_gz)
        day_symbol = ganzhi_symbol(day_gz)
        term_name, term_element = fixed_solar_term(date)
        year_stem_element = STEM_ELEMENT[year_gz[0]]
        year_branch_element = BRANCH_ELEMENT[year_gz[1]]
        weights = empty_element_scores()
        weights[year_stem_element] += 1.0
        weights[year_branch_element] += 1.0
        weights[STEM_ELEMENT[day_gz[0]]] += 2.0
        weights[BRANCH_ELEMENT[day_gz[1]]] += 2.0
        weights[term_element] += 1.8
        weights[season_element(date.month)] += 1.2
        astro = astro_fortune_for_day(date, year_gz, day_gz)
        month_meta = month_ganzhi_for_date(date, year_gz)
        lunar_meta = lunar_approx_for_date(date)
        hour_meta = hour_pillars_for_trading_day(date, day_gz)
        branch_meta = branch_relations_for_day(year_gz, str(month_meta["month_ganzhi"]), day_gz)
        kongwang_meta = kongwang_for_day(day_gz)
        shensha_meta = shensha_for_day(day_gz)
        qimen_meta = qimen_for_day(date, day_gz)
        meihua_meta = meihua_for_day(date, day_gz)
        weights[str(astro["mansion_element_key"])] += 0.6
        weights[str(astro["annual_star_element_key"])] += 0.4
        weights[str(astro["day_star_element_key"])] += 0.5
        weights[str(astro["moon_element_key"])] += 0.3
        weights[element_key(str(month_meta["month_element"]))] += 0.7
        weights[element_key(str(qimen_meta["qimen_door_element"]))] += 0.4
        weights[TRIGRAM_ELEMENT[str(meihua_meta["meihua_body"])]] += 0.3
        weights = normalize(weights)
        main = max(weights, key=weights.get)
        secondary = sorted(weights, key=weights.get, reverse=True)[1]
        trigram = TRIGRAMS[(date.day + date.month + date.year) % len(TRIGRAMS)]
        almanac = almanac_for_day(year_gz, day_gz, term_name, main, secondary, trigram)
        polarity = "阳" if main in {"wood", "fire"} else "阴" if main in {"metal", "water"} else "中"
        days_since_term = days_since_fixed_solar_term(date)
        short_hold_days = derive_short_hold_days(main, secondary, trigram, polarity, term_name, days_since_term)
        long_hold_days = derive_long_hold_days(
            main,
            secondary,
            year_stem_element,
            year_branch_element,
            term_name,
            days_since_term,
        )
        buy_phase, buy_allowed_soft, buy_allowed_strict, buy_note = derive_buy_timing(
            main, secondary, trigram, polarity, term_name, days_since_term
        )
        recommendation_plan = derive_recommendation_plan(
            main,
            secondary,
            trigram,
            buy_phase,
            term_name,
            days_since_term,
            str(astro["new_position_gate"]),
        )
        legacy_cycle_type, legacy_hold_days = choose_cycle_type(
            main,
            trigram,
            buy_phase,
            term_name,
            short_hold_days,
            long_hold_days,
        )
        hierarchy_type, hold_days, hierarchy_note = derive_hierarchy_hold_days(
            main,
            secondary,
            trigram,
            polarity,
            term_name,
            days_since_term,
            year_stem_element,
            year_branch_element,
            buy_phase,
            short_hold_days,
            long_hold_days,
            astro,
        )
        timing_note = build_timing_note(
            main,
            secondary,
            trigram,
            polarity,
            term_name,
            days_since_term,
            short_hold_days,
            long_hold_days,
            hierarchy_type,
            hold_days,
            buy_phase,
            buy_note,
            hierarchy_note,
            str(astro["astro_note"]),
        )
        buy_shichen, buy_time, sell_shichen, sell_time, intraday_note = derive_intraday_timing(
            buy_phase, hierarchy_type, main, trigram
        )
        records.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "year_ganzhi": year_gz,
                "year_qi": f"{ELEMENT_CN[year_stem_element]}{ELEMENT_CN[year_branch_element]}",
                "year_symbol": year_symbol["alias"],
                "year_nayin": year_symbol["nayin"],
                "year_symbol_note": year_symbol["note"],
                "day_ganzhi": day_gz,
                "day_symbol": day_symbol["alias"],
                "day_nayin": day_symbol["nayin"],
                "day_symbol_note": day_symbol["note"],
                "month_ganzhi": month_meta["month_ganzhi"],
                "month_element": month_meta["month_element"],
                "month_note": month_meta["month_note"],
                "lunar_month_approx": lunar_meta["lunar_month_approx"],
                "lunar_day_approx": lunar_meta["lunar_day_approx"],
                "lunar_note": lunar_meta["lunar_note"],
                "si_pillar": hour_meta["巳_pillar"],
                "wu_pillar": hour_meta["午_pillar"],
                "wei_pillar": hour_meta["未_pillar"],
                "hour_pillar_note": hour_meta["hour_pillar_note"],
                "branch_relation_note": branch_meta["branch_relation_note"],
                "day_clash_branch": branch_meta["day_clash_branch"],
                "day_liuhe_branch": branch_meta["day_liuhe_branch"],
                "day_liuhai_branch": branch_meta["day_liuhai_branch"],
                "kongwang": kongwang_meta["kongwang"],
                "kongwang_note": kongwang_meta["kongwang_note"],
                "nobleman_branches": shensha_meta["nobleman_branches"],
                "travel_horse_branch": shensha_meta["travel_horse_branch"],
                "peach_blossom_branch": shensha_meta["peach_blossom_branch"],
                "huagai_branch": shensha_meta["huagai_branch"],
                "lu_branch": shensha_meta["lu_branch"],
                "yang_ren_branch": shensha_meta["yang_ren_branch"],
                "shensha_note": shensha_meta["shensha_note"],
                "qimen_door": qimen_meta["qimen_door"],
                "qimen_door_direction": qimen_meta["qimen_door_direction"],
                "qimen_door_luck": qimen_meta["qimen_door_luck"],
                "qimen_star": qimen_meta["qimen_star"],
                "qimen_deity": qimen_meta["qimen_deity"],
                "qimen_note": qimen_meta["qimen_note"],
                "meihua_hexagram": meihua_meta["meihua_hexagram"],
                "meihua_moving_line": meihua_meta["meihua_moving_line"],
                "meihua_body": meihua_meta["meihua_body"],
                "meihua_use": meihua_meta["meihua_use"],
                "meihua_note": meihua_meta["meihua_note"],
                "day_direction": almanac["day_direction"],
                "auspicious_direction": almanac["auspicious_direction"],
                "wealth_direction": almanac["wealth_direction"],
                "mansion": astro["mansion"],
                "mansion_element": astro["mansion_element"],
                "mansion_direction": astro["mansion_direction"],
                "mansion_luck": astro["mansion_luck"],
                "mansion_note": astro["mansion_note"],
                "jianchu": astro["jianchu"],
                "jianchu_note": astro["jianchu_note"],
                "day_deity": astro["day_deity"],
                "day_deity_luck": astro["day_deity_luck"],
                "day_deity_note": astro["day_deity_note"],
                "annual_star": astro["annual_star"],
                "annual_star_direction": astro["annual_star_direction"],
                "annual_star_luck": astro["annual_star_luck"],
                "day_star": astro["day_star"],
                "day_star_direction": astro["day_star_direction"],
                "day_star_luck": astro["day_star_luck"],
                "moon_phase": astro["moon_phase"],
                "moon_element": astro["moon_element"],
                "moon_note": astro["moon_note"],
                "tai_sui_direction": astro["tai_sui_direction"],
                "sui_po_direction": astro["sui_po_direction"],
                "san_sha_direction": astro["san_sha_direction"],
                "astro_gate_score": astro["astro_gate_score"],
                "new_position_gate": astro["new_position_gate"],
                "new_position_note": astro["new_position_note"],
                "astro_note": astro["astro_note"],
                "solar_term": term_name,
                "days_since_solar_term": days_since_term,
                "main_qi": ELEMENT_CN[main],
                "secondary_qi": ELEMENT_CN[secondary],
                "polarity": polarity,
                "trigram": trigram,
                "short_hold_days": short_hold_days,
                "long_hold_days": long_hold_days,
                "legacy_cycle_type": legacy_cycle_type,
                "legacy_hold_days": legacy_hold_days,
                "hierarchy_type": hierarchy_type,
                "hierarchy_hold_days": hold_days,
                "hierarchy_note": hierarchy_note,
                "cycle_type": hierarchy_type,
                "xuan_hold_days": hold_days,
                "buy_phase": buy_phase,
                "buy_allowed_soft": buy_allowed_soft,
                "buy_allowed_strict": buy_allowed_strict,
                "buy_note": buy_note,
                "recommended_count": recommendation_plan["recommended_count"],
                "position_style": recommendation_plan["position_style"],
                "sizing_note": recommendation_plan["sizing_note"],
                "recommendation_note": recommendation_plan["recommendation_note"],
                "favorable_elements": almanac["favorable_elements"],
                "avoid_elements": almanac["avoid_elements"],
                "almanac_yi": almanac["yi"],
                "almanac_ji": almanac["ji"],
                "almanac_note": almanac["almanac_note"],
                "buy_shichen": buy_shichen,
                "buy_time": buy_time,
                "sell_shichen": sell_shichen,
                "sell_time": sell_time,
                "intraday_note": intraday_note,
                "timing_note": timing_note,
                "daily_note": (
                    f"{year_gz}{year_symbol['alias']}年，纳音{year_symbol['nayin']}；"
                    f"{day_gz}{day_symbol['alias']}日，纳音{day_symbol['nayin']}；"
                    f"{term_name}气，{ELEMENT_CN[main]}旺，"
                    f"{ELEMENT_CN[secondary]}相，{trigram}象，{buy_phase}，"
                    f"宜{buy_time}买，持{hold_days}日，{sell_time}卖"
                ),
                "decision_hierarchy": " > ".join(f"{name}:{desc}" for name, desc in DECISION_LAYERS),
                **{f"{element}_qi": weights[element] for element in ELEMENTS},
            }
        )
    return pd.DataFrame(records)


def derive_short_hold_days(
    main: str,
    secondary: str,
    trigram: str,
    polarity: str,
    term_name: str,
    days_since_term: int,
) -> int:
    """Derive holding time from symbolic timing rules.

    The rules are intentionally simple and explicit: five is the central number,
    seven echoes "七日来复", nine is mature yang, and solar-term pivots shorten
    the trade because qi is changing.
    """
    hold = round((ELEMENT_HOLD_DAYS[main] + TRIGRAM_HOLD_DAYS[trigram]) / 2)
    if secondary == GENERATES[main]:
        hold += 1
    if polarity == "阳" and main == "fire":
        hold -= 1
    if polarity == "阴" and main == "water":
        hold += 1
    if term_name in PIVOT_SOLAR_TERMS or days_since_term <= 2:
        hold -= 1
    if days_since_term >= 12:
        hold += 1
    return max(3, min(11, hold))


def derive_long_hold_days(
    main: str,
    secondary: str,
    year_stem_element: str,
    year_branch_element: str,
    term_name: str,
    days_since_term: int,
) -> int:
    hold = LONG_ELEMENT_DAYS[main]
    if year_stem_element == main:
        hold += 5
    if year_branch_element == main:
        hold += 5
    if secondary == GENERATES[main]:
        hold += 3
    if term_name in GROWTH_SOLAR_TERMS and main in {"wood", "fire"}:
        hold += 5
    if term_name in HARVEST_SOLAR_TERMS and main in {"metal", "earth"}:
        hold += 5
    if term_name in STORAGE_SOLAR_TERMS and main in {"water", "earth"}:
        hold += 5
    if term_name in PIVOT_SOLAR_TERMS or days_since_term <= 2:
        hold -= 5
    return max(13, min(55, hold))


def derive_buy_timing(
    main: str,
    secondary: str,
    trigram: str,
    polarity: str,
    term_name: str,
    days_since_term: int,
) -> tuple[str, bool, bool, str]:
    if term_name in PIVOT_SOLAR_TERMS or days_since_term <= 2:
        return "转气试仓", True, False, "节气交接，旧气未尽新气初生，只宜试仓"
    if trigram in {"震", "巽"} and main in {"wood", "fire"}:
        return "发动开仓", True, True, "震巽主动，木火生发，宜主动开仓"
    if trigram in {"离", "兑"} and polarity == "阳":
        return "明兑现仓", True, True, "离明兑悦，阳气外放，宜快进快出"
    if trigram in {"坎", "艮"}:
        return "险止观察", False, False, "坎险艮止，先观察后行动"
    if term_name in HARVEST_SOLAR_TERMS:
        return "收敛择仓", True, False, "秋令收敛，宜择强不宜追广"
    if term_name in STORAGE_SOLAR_TERMS:
        return "伏藏低吸", True, False, "冬令伏藏，宜低吸不宜躁进"
    if polarity == "阴":
        return "阴守小仓", True, False, "阴气偏重，小仓试探"
    return "平气可仓", True, True, "气机平顺，可按象意开仓"


def derive_intraday_timing(
    buy_phase: str,
    cycle_type: str,
    main: str,
    trigram: str,
) -> tuple[str, str, str, str, str]:
    buy_shichen, buy_time, sell_shichen, sell_time = INTRADAY_TIMES[buy_phase]
    if is_long_horizon(cycle_type) and buy_phase in {"伏藏低吸", "收敛择仓", "平气可仓"}:
        sell_shichen, sell_time = "未末", "14:50"
    if main == "fire" and trigram in {"震", "离"}:
        buy_shichen, buy_time = "巳初", "09:45"
    if main in {"water", "earth"} and is_long_horizon(cycle_type):
        buy_shichen, buy_time = "未正", "14:00"
    note = (
        f"A股盘中仅取巳午未三时；{buy_phase}取{buy_shichen}{buy_time}，"
        f"{cycle_type}到期取{sell_shichen}{sell_time}"
    )
    return buy_shichen, buy_time, sell_shichen, sell_time, note


def is_long_horizon(value: str) -> bool:
    return str(value) in {"long", "节气波段", "年运持仓"}


def is_short_horizon(value: str) -> bool:
    return str(value) in {"short", "日课短打"}


def choose_cycle_type(
    main: str,
    trigram: str,
    buy_phase: str,
    term_name: str,
    short_hold_days: int,
    long_hold_days: int,
) -> tuple[str, int]:
    if buy_phase in {"发动开仓", "明兑现仓"} or trigram in {"震", "离", "兑"}:
        return "short", short_hold_days
    if buy_phase in {"伏藏低吸", "收敛择仓"} or main in {"water", "earth"}:
        return "long", long_hold_days
    if term_name in GROWTH_SOLAR_TERMS and main in {"wood", "fire"}:
        return "long", long_hold_days
    return "short", short_hold_days


def derive_hierarchy_hold_days(
    main: str,
    secondary: str,
    trigram: str,
    polarity: str,
    term_name: str,
    days_since_term: int,
    year_stem_element: str,
    year_branch_element: str,
    buy_phase: str,
    short_hold_days: int,
    long_hold_days: int,
    astro: dict[str, object] | None = None,
) -> tuple[str, int, str]:
    """Derive the final horizon from large cycles down to the day lesson.

    short_hold_days and long_hold_days are diagnostic anchors only. The final
    horizon is decided by the hierarchy score, not by a user-selected bucket.
    """
    score = 0
    notes = []
    if year_stem_element == main:
        score += 2
        notes.append("年干同主气，年运托举")
    if year_branch_element == main:
        score += 2
        notes.append("年支同主气，地支托举")
    if year_stem_element == secondary or year_branch_element == secondary:
        score += 1
        notes.append("年运合辅气，留有余脉")
    if CONTROLS[year_stem_element] == main or CONTROLS[year_branch_element] == main:
        score -= 2
        notes.append("年运克主气，不宜恋战")

    if term_name in GROWTH_SOLAR_TERMS and main in {"wood", "fire"}:
        score += 2
        notes.append("节气生发，木火可成段")
    if term_name in HARVEST_SOLAR_TERMS and main in {"metal", "earth"}:
        score += 2
        notes.append("秋令收敛，金土可成段")
    if term_name in STORAGE_SOLAR_TERMS and main in {"water", "earth"}:
        score += 2
        notes.append("冬令伏藏，水土可久守")
    if term_name in PIVOT_SOLAR_TERMS or days_since_term <= 2:
        score -= 2
        notes.append("节气交接，先试后定")
    elif days_since_term >= 12:
        score -= 1
        notes.append("节气将尽，长气渐散")

    if buy_phase in {"发动开仓", "明兑现仓"} or trigram in {"震", "离", "兑"}:
        score -= 3
        notes.append("日课发动或明兑现，偏快")
    if buy_phase in {"伏藏低吸", "收敛择仓", "平气可仓"}:
        score += 1
        notes.append("日课可承，可放大到波段")
    if trigram in {"坎", "艮", "坤"}:
        score += 1
        notes.append("日卦险止承载，需等气成形")
    if polarity == "阳" and main in {"wood", "fire"}:
        score -= 1
        notes.append("阳气外放，来速去亦速")
    elif polarity == "阴" and main in {"water", "metal"}:
        score += 1
        notes.append("阴气收束，持而观复")
    if astro:
        gate = str(astro.get("new_position_gate", "半开"))
        if gate == "开":
            score += 1
            notes.append("星曜仓门开，可延一线")
        elif gate == "守":
            score -= 1
            notes.append("星曜仓门守，宜缩不宜放")
        elif gate == "闭":
            score -= 3
            notes.append("星曜仓门闭，只观不新开")
        score += int(astro.get("jianchu_hold_delta", 0))
        notes.append(f"建除{astro.get('jianchu', '')}，持股修正{astro.get('jianchu_hold_delta', 0)}日")

    if score <= -2:
        horizon = "日课短打"
        hold = max(1, min(6, short_hold_days))
    elif score <= 4:
        horizon = "节气波段"
        hold = round(short_hold_days * 0.65 + long_hold_days * 0.35)
        hold = max(5, min(21, hold))
    else:
        horizon = "年运持仓"
        hold = max(13, min(55, long_hold_days))
    notes.append(f"层级分{score}，落为{horizon}")
    return horizon, int(hold), "；".join(notes)


def build_timing_note(
    main: str,
    secondary: str,
    trigram: str,
    polarity: str,
    term_name: str,
    days_since_term: int,
    short_hold_days: int,
    long_hold_days: int,
    cycle_type: str,
    hold_days: int,
    buy_phase: str,
    buy_note: str,
    hierarchy_note: str = "",
    astro_note: str = "",
) -> str:
    parts = [
        f"{ELEMENT_CN[main]}旺",
        f"{ELEMENT_CN[secondary]}相",
        f"{trigram}象取{TRIGRAM_HOLD_DAYS[trigram]}日",
        f"{buy_phase}",
        buy_note,
    ]
    if term_name in PIVOT_SOLAR_TERMS or days_since_term <= 2:
        parts.append("节气交接，减一日")
    elif days_since_term >= 12:
        parts.append("节气将尽，加一日等变")
    if polarity == "阳":
        parts.append("阳主动")
    elif polarity == "阴":
        parts.append("阴主守")
    parts.append(f"日课锚{short_hold_days}日")
    parts.append(f"年节锚{long_hold_days}日")
    if hierarchy_note:
        parts.append(hierarchy_note)
    if astro_note:
        parts.append(astro_note)
    return "；".join(parts) + f"；层级推演为{cycle_type}，合成持{hold_days}个交易日"


def discover_price_files(daily_dir: Path) -> list[Path]:
    return sorted(daily_dir.glob("*.csv"))


def load_prices(
    files: list[Path],
    start_date: str,
    end_date: str | None,
    max_stocks: int,
) -> pd.DataFrame:
    frames = []
    for file in files:
        try:
            df = pd.read_csv(
                file,
                usecols=["date", "code", "close", "pctChg", "amount", "isST"],
                parse_dates=["date"],
            )
        except Exception:
            continue
        if df.empty:
            continue
        if start_date:
            df = df[df["date"] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df["date"] <= pd.Timestamp(end_date)]
        if df.empty:
            continue
        df = df.dropna(subset=["close"])
        frames.append(df)
    if not frames:
        raise RuntimeError("No local daily bars found for the requested date range.")

    prices = pd.concat(frames, ignore_index=True)
    prices = prices[prices["close"] > 0].copy()
    if max_stocks > 0:
        latest_date = prices["date"].max()
        recent_start = latest_date - pd.Timedelta(days=180)
        recent_prices = prices[prices["date"] >= recent_start]
        if recent_prices.empty:
            recent_prices = prices
        liquidity = recent_prices.groupby("code")["amount"].mean().sort_values(ascending=False)
        keep = set(liquidity.head(max_stocks).index)
        prices = prices[prices["code"].isin(keep)].copy()
    return prices.sort_values(["date", "code"]).reset_index(drop=True)


def compatibility(stock_row: pd.Series, qi_row: pd.Series) -> float:
    score = 0.0
    for element in ELEMENTS:
        score += float(stock_row[f"{element}_weight"]) * float(qi_row[f"{element}_qi"])
    primary = next(
        element for element in ELEMENTS if ELEMENT_CN[element] == stock_row["primary_element"]
    )
    main_qi = next(element for element in ELEMENTS if ELEMENT_CN[element] == qi_row["main_qi"])
    if GENERATES[main_qi] == primary:
        score += 0.12
    if GENERATES[primary] == main_qi:
        score += 0.08
    if CONTROLS[main_qi] == primary:
        score -= 0.10
    if CONTROLS[primary] == main_qi:
        score -= 0.05
    if stock_row["trigram"] == qi_row["trigram"]:
        score += 0.05
    if stock_row["yin_yang"] == qi_row["polarity"]:
        score += 0.03
    registered_direction = str(stock_row.get("registered_direction", ""))
    if registered_direction:
        day_direction = str(qi_row.get("day_direction", ""))
        auspicious_direction = str(qi_row.get("auspicious_direction", ""))
        wealth_direction = str(qi_row.get("wealth_direction", ""))
        tai_sui_direction = str(qi_row.get("tai_sui_direction", ""))
        sui_po_direction = str(qi_row.get("sui_po_direction", ""))
        san_sha_direction = str(qi_row.get("san_sha_direction", ""))
        qimen_direction = str(qi_row.get("qimen_door_direction", ""))
        qimen_luck = str(qi_row.get("qimen_door_luck", ""))
        day_trigram = str(qi_row.get("trigram", "坤"))
        day_trigram_direction = TRIGRAM_META[day_trigram]["direction"]
        if registered_direction == day_trigram_direction:
            score += 0.06
        if registered_direction == wealth_direction:
            score += 0.05
        if registered_direction == auspicious_direction:
            score += 0.04
        if registered_direction == day_direction:
            score += 0.03
        if registered_direction == tai_sui_direction:
            score += 0.02
        if registered_direction == qimen_direction and qimen_luck == "吉":
            score += 0.05
        if registered_direction in {sui_po_direction, san_sha_direction}:
            score -= 0.08
    return score


def element_key(element_cn: str) -> str:
    return next(element for element in ELEMENTS if ELEMENT_CN[element] == element_cn)


def stock_day_timing(stock_row: pd.Series, qi_row: pd.Series, code: str | None = None) -> dict[str, object]:
    stock_element = element_key(stock_row["primary_element"])
    stock_secondary = element_key(stock_row["secondary_element"])
    day_element = element_key(qi_row["main_qi"])
    stock_trigram = str(stock_row["trigram"])
    upper_trigram = str(stock_row.get("upper_trigram", stock_trigram))
    code_branch = str(stock_row.get("code_branch", ""))
    moving_line = int(stock_row.get("moving_line", 1))
    line_meta = LINE_META[moving_line]
    day_trigram = str(qi_row["trigram"])
    registered_direction = str(stock_row.get("registered_direction", ""))
    day_direction = str(qi_row.get("day_direction", ""))
    auspicious_direction = str(qi_row.get("auspicious_direction", ""))
    wealth_direction = str(qi_row.get("wealth_direction", ""))
    tai_sui_direction = str(qi_row.get("tai_sui_direction", ""))
    sui_po_direction = str(qi_row.get("sui_po_direction", ""))
    san_sha_direction = str(qi_row.get("san_sha_direction", ""))
    qimen_direction = str(qi_row.get("qimen_door_direction", ""))
    qimen_luck = str(qi_row.get("qimen_door_luck", ""))
    qimen_door = str(qi_row.get("qimen_door", ""))
    kongwang = set(str(qi_row.get("kongwang", "")).split("/"))
    day_clash_branch = str(qi_row.get("day_clash_branch", ""))
    day_liuhai_branch = str(qi_row.get("day_liuhai_branch", ""))
    day_trigram_direction = TRIGRAM_META[day_trigram]["direction"]
    base_hold = int(qi_row["xuan_hold_days"])
    hold = base_hold
    reasons = []
    relation = "平"
    relation_basis = "股日五行平参，无明显生克"

    if stock_element == day_element:
        hold -= 1
        relation = "比和"
        relation_basis = f"股属{ELEMENT_CN[stock_element]}，日主{qi_row['main_qi']}，同气相应"
        reasons.append("股日同气，来得快，减一日")
    elif GENERATES[day_element] == stock_element:
        hold += 2
        relation = "日生股"
        relation_basis = f"日主{qi_row['main_qi']}生股票{stock_row['primary_element']}，取母生子"
        reasons.append("日气生股，气源较长，加二日")
    elif GENERATES[stock_element] == day_element:
        hold += 1
        relation = "股生日"
        relation_basis = f"股票{stock_row['primary_element']}生日主{qi_row['main_qi']}，股气顺泄于日"
        reasons.append("股票生扶日气，顺势加一日")
    elif CONTROLS[day_element] == stock_element:
        hold -= 2
        relation = "日克股"
        relation_basis = f"日主{qi_row['main_qi']}克股票{stock_row['primary_element']}，取受制短试"
        reasons.append("日气克股，只作短试，减二日")
    elif CONTROLS[stock_element] == day_element:
        hold -= 1
        relation = "股克日"
        relation_basis = f"股票{stock_row['primary_element']}克日主{qi_row['main_qi']}，取耗气"
        reasons.append("股票克日气，耗气减一日")

    if stock_secondary == day_element:
        hold += 1
        reasons.append("辅气贴日，加一日")
    if stock_trigram == day_trigram:
        hold -= 1
        trigram_relation = "同卦"
        trigram_basis = f"股票{stock_trigram}卦与日卦{day_trigram}同频，事来速"
        reasons.append("卦象同频，发动快，减一日")
    elif stock_trigram in {"坎", "艮", "坤"}:
        hold += 2
        trigram_relation = "守卦"
        trigram_basis = f"股票{stock_trigram}卦取{TRIGRAM_META[stock_trigram]['image']}象，性{TRIGRAM_META[stock_trigram]['nature']}，偏守"
        reasons.append(f"{stock_trigram}象偏守，加二日")
    elif stock_trigram in {"震", "离", "兑"}:
        hold -= 1
        trigram_relation = "动卦"
        trigram_basis = f"股票{stock_trigram}卦取{TRIGRAM_META[stock_trigram]['image']}象，性{TRIGRAM_META[stock_trigram]['nature']}，偏动"
        reasons.append(f"{stock_trigram}象偏动，减一日")
    else:
        trigram_relation = "顺入"
        trigram_basis = f"股票{stock_trigram}卦取{TRIGRAM_META[stock_trigram]['image']}象，{TRIGRAM_META[stock_trigram]['phase']}"

    if stock_element in {"water", "earth"} and is_long_horizon(str(qi_row["cycle_type"])):
        hold += 3
        reasons.append("水土逢长周期，伏藏承载，加三日")
    if stock_element == "fire" and qi_row["buy_phase"] in {"发动开仓", "明兑现仓"}:
        hold -= 1
        reasons.append("火股遇发动，宜快不宜恋，减一日")
    if stock_element == "fire" and qi_row["buy_phase"] == "明兑现仓":
        hold -= 2
        reasons.append("明兑现仓火明易泄，再减二日")
    if stock_trigram in {"坎", "艮"} and qimen_luck == "凶":
        hold -= 1
        reasons.append(f"奇门{qimen_door}不利守险，减一日")
    if code_branch in kongwang:
        hold -= 1
        reasons.append(f"代码支{code_branch}落空亡，减一日")
    if code_branch == day_clash_branch:
        hold -= 1
        reasons.append(f"代码支{code_branch}冲日，减一日")
    if code_branch == day_liuhai_branch:
        hold -= 1
        reasons.append(f"代码支{code_branch}害日，减一日")
    hold += int(line_meta["hold_delta"])
    reasons.append(f"{line_meta['name']}动，{line_meta['phase']}，持股修正{line_meta['hold_delta']}日")
    if moving_line in {5, 6} and upper_trigram in {"震", "离", "兑"}:
        hold -= 2
        reasons.append(f"{line_meta['name']}逢上卦{upper_trigram}偏动，过亢再减二日")
    if stock_trigram == day_trigram and upper_trigram == day_trigram:
        hold -= 2
        reasons.append(f"上下重{day_trigram}又同日卦，明极易泄，再减二日")
    if upper_trigram in {"坎", "艮", "坤"}:
        hold += 1
        reasons.append(f"上卦{upper_trigram}偏守，加一日")
    elif upper_trigram in {"震", "离", "兑"}:
        hold -= 1
        reasons.append(f"上卦{upper_trigram}偏动，减一日")

    location_basis = "注册地未入库，方位只取日课"
    location_relation = "未入库"
    if registered_direction:
        if registered_direction in {sui_po_direction, san_sha_direction}:
            location_relation = "犯忌"
            location_basis = (
                f"注册地方{registered_direction}，犯岁破{sui_po_direction}/三煞{san_sha_direction}之一，"
                "虽有股象亦不加仓"
            )
            hold -= 1
            reasons.append("注册地方位犯岁破或三煞，减一日")
        elif registered_direction in {day_direction, auspicious_direction, wealth_direction, day_trigram_direction, tai_sui_direction, qimen_direction}:
            location_relation = "得方"
            location_basis = (
                f"注册地方{registered_direction}，与日方{day_direction}/喜神{auspicious_direction}/"
                f"财位{wealth_direction}/日卦{day_trigram_direction}/太岁{tai_sui_direction}/"
                f"奇门{qimen_door}{qimen_direction}有合"
            )
            hold += 1
            reasons.append("注册地方位得气，加一日")
        else:
            location_relation = "失方"
            location_basis = (
                f"注册地方{registered_direction}，未合日方{day_direction}、喜神{auspicious_direction}、"
                f"财位{wealth_direction}、日卦{day_trigram_direction}"
            )
            reasons.append("注册地方位未得气，只作候选不加仓")

    min_hold = 1
    max_hold = 13 if is_short_horizon(str(qi_row["cycle_type"])) else 55
    hold = max(min_hold, min(max_hold, hold))

    buy_phase = str(qi_row["buy_phase"])
    buy_shichen, buy_time, sell_shichen, sell_time = stock_intraday_timing(
        buy_phase,
        str(qi_row["cycle_type"]),
        stock_element,
        stock_trigram,
        upper_trigram,
        moving_line,
        str(code or stock_row.get("code", "")),
        day_element,
        day_trigram,
    )
    note = "；".join(reasons) if reasons else "股日平和，沿用日课"
    intraday_note = (
        f"股属{ELEMENT_CN[stock_element]}、{upper_trigram}上{stock_trigram}下、{line_meta['name']}动；"
        f"日为{qi_row['main_qi']}、{day_trigram}象；"
        f"取{buy_shichen}{buy_time}入，{sell_shichen}{sell_time}出"
    )
    theory_basis = (
        f"层级：{' > '.join(name for name, _ in DECISION_LAYERS)}；"
        f"{relation_basis}；{trigram_basis}；"
        f"重卦：{stock_row.get('hexagram_evidence', '')}；"
        f"星曜：{qi_row.get('astro_note', '')}；"
        f"地理：{stock_row.get('location_evidence', '')}，{location_basis}；"
        f"五行义：{ELEMENT_META[stock_element]['trade']}；"
        f"卦义：{TRIGRAM_META[stock_trigram]['trade']}；"
        f"时辰义：{intraday_note}；分钟由完整代码与{line_meta['name']}动细分"
    )
    return {
        "stock_cycle_type": qi_row["cycle_type"],
        "stock_hierarchy_type": qi_row.get("hierarchy_type", qi_row["cycle_type"]),
        "stock_hold_days": int(hold),
        "stock_relation": relation,
        "stock_relation_basis": relation_basis,
        "stock_trigram_relation": trigram_relation,
        "stock_trigram_basis": trigram_basis,
        "stock_hexagram": stock_row.get("hexagram_name", ""),
        "stock_moving_line": moving_line,
        "stock_hexagram_basis": stock_row.get("hexagram_evidence", ""),
        "stock_location_relation": location_relation,
        "stock_location_basis": location_basis,
        "stock_buy_shichen": buy_shichen,
        "stock_buy_time": buy_time,
        "stock_sell_shichen": sell_shichen,
        "stock_sell_time": sell_time,
        "stock_timing_reason": note,
        "stock_intraday_note": intraday_note,
        "stock_theory_basis": theory_basis,
    }


def stock_intraday_timing(
    buy_phase: str,
    cycle_type: str,
    stock_element: str,
    stock_trigram: str,
    upper_trigram: str,
    moving_line: int,
    code: str,
    day_element: str,
    day_trigram: str,
) -> tuple[str, str, str, str]:
    if stock_trigram == "震" or stock_element == "fire":
        buy_shichen, buy_time = "巳初", "09:45"
    elif stock_trigram in {"离", "兑"}:
        buy_shichen, buy_time = "巳正", "10:30"
    elif stock_element == "metal":
        buy_shichen, buy_time = "午末", "11:15"
    elif stock_element in {"earth", "water"} or stock_trigram in {"坎", "艮", "坤"}:
        buy_shichen, buy_time = "未正", "14:00"
    elif stock_element == "wood" or stock_trigram == "巽":
        buy_shichen, buy_time = "巳正", "10:15"
    else:
        buy_shichen, buy_time = INTRADAY_TIMES[buy_phase][0], INTRADAY_TIMES[buy_phase][1]

    line_meta = LINE_META[moving_line]
    line_buy_shichen, line_buy_time = line_meta["buy"]
    line_sell_shichen, line_sell_time = line_meta["sell"]
    if moving_line in {1, 4, 6}:
        buy_shichen, buy_time = line_buy_shichen, line_buy_time
    elif moving_line in {2, 3, 5} and stock_trigram == day_trigram:
        buy_shichen, buy_time = line_buy_shichen, line_buy_time

    if CONTROLS[day_element] == stock_element:
        buy_shichen, buy_time = "未末", "14:40"
    elif GENERATES[day_element] == stock_element:
        buy_shichen, buy_time = "巳正", "10:15"

    if moving_line in {3, 6}:
        sell_shichen, sell_time = line_sell_shichen, line_sell_time
    elif is_long_horizon(cycle_type) or stock_trigram in {"坎", "艮", "坤"} or upper_trigram in {"坎", "艮", "坤"}:
        sell_shichen, sell_time = "未末", "14:50"
    elif stock_element == "fire" or stock_trigram in {"离", "兑"}:
        sell_shichen, sell_time = "午末", "11:20"
    elif stock_element == "metal":
        sell_shichen, sell_time = "未正", "14:20"
    else:
        sell_shichen, sell_time = "未末", "14:45"

    buy_time = refine_minute(buy_shichen, code, moving_line, salt=3)
    sell_time = refine_minute(sell_shichen, code, moving_line, salt=17)
    return buy_shichen, buy_time, sell_shichen, sell_time


def mystic_advice(row: pd.Series) -> str:
    region = str(row.get("registered_region", ""))
    city = str(row.get("registered_city", ""))
    direction = str(row.get("registered_direction", ""))
    location = f"{region}{city}{direction}方" if direction else "地脉未详"
    return (
        f"{row['code_name']}一票，股性取{row['primary_element']}，辅以{row['secondary_element']}，"
        f"地脉在{location}；代码起{row['stock_hexagram_name']}，"
        f"{int(row['stock_moving_line'])}爻动。今日天盘{row['day_qi']}旺，"
        f"地盘{row.get('day_trigram', '')}起，股日相参为{row.get('stock_relation', '')}。"
        f"宜于{row['stock_buy_shichen']}{row['stock_buy_time']}候气入局，"
        f"守{int(row['stock_hold_days'])}个交易日，至{row['stock_sell_shichen']}{row['stock_sell_time']}收锋。"
        f"此为借势，不为恋战；得气则进，气散则退。"
    )


def build_candidates(
    prices: pd.DataFrame,
    profiles: pd.DataFrame,
    qi: pd.DataFrame,
    top_n: int,
) -> pd.DataFrame:
    profile_idx = profiles.set_index("code")
    qi_idx = qi.set_index("date")
    records = []
    tradable = prices[(prices["isST"].fillna(0) == 0)].copy()
    for date, day_df in tradable.groupby("date", sort=True):
        date_key = date.strftime("%Y-%m-%d")
        if date_key not in qi_idx.index:
            continue
        qi_row = qi_idx.loc[date_key]
        day_records = []
        for code in day_df["code"].unique():
            if code not in profile_idx.index:
                continue
            p = profile_idx.loc[code]
            stock_timing = stock_day_timing(p, qi_row, code)
            record = {
                    "date": date_key,
                    "code": code,
                    "code_name": p["code_name"],
                    "industry": p["industry"],
                    "registered_region": p.get("registered_region", ""),
                    "registered_city": p.get("registered_city", ""),
                    "registered_direction": p.get("registered_direction", ""),
                    "location_evidence": p.get("location_evidence", ""),
                    "primary_element": p["primary_element"],
                    "secondary_element": p["secondary_element"],
                    "stock_trigram": p["trigram"],
                    "stock_hexagram_name": p["hexagram_name"],
                    "stock_code_branch": p.get("code_branch", ""),
                    "stock_moving_line": p["moving_line"],
                    "stock_hexagram_evidence": p["hexagram_evidence"],
                    "stock_trigram_evidence": p["trigram_evidence"],
                    "stock_element_theory": p["element_theory"],
                    "day_qi": qi_row["main_qi"],
                    "day_trigram": qi_row["trigram"],
                    "mansion": qi_row.get("mansion", ""),
                    "mansion_luck": qi_row.get("mansion_luck", ""),
                    "jianchu": qi_row.get("jianchu", ""),
                    "day_deity": qi_row.get("day_deity", ""),
                    "annual_star": qi_row.get("annual_star", ""),
                    "day_star": qi_row.get("day_star", ""),
                    "moon_phase": qi_row.get("moon_phase", ""),
                    "month_ganzhi": qi_row.get("month_ganzhi", ""),
                    "lunar_month_approx": qi_row.get("lunar_month_approx", ""),
                    "lunar_day_approx": qi_row.get("lunar_day_approx", ""),
                    "si_pillar": qi_row.get("si_pillar", ""),
                    "wu_pillar": qi_row.get("wu_pillar", ""),
                    "wei_pillar": qi_row.get("wei_pillar", ""),
                    "branch_relation_note": qi_row.get("branch_relation_note", ""),
                    "kongwang": qi_row.get("kongwang", ""),
                    "nobleman_branches": qi_row.get("nobleman_branches", ""),
                    "travel_horse_branch": qi_row.get("travel_horse_branch", ""),
                    "peach_blossom_branch": qi_row.get("peach_blossom_branch", ""),
                    "huagai_branch": qi_row.get("huagai_branch", ""),
                    "lu_branch": qi_row.get("lu_branch", ""),
                    "yang_ren_branch": qi_row.get("yang_ren_branch", ""),
                    "qimen_door": qi_row.get("qimen_door", ""),
                    "qimen_door_direction": qi_row.get("qimen_door_direction", ""),
                    "qimen_star": qi_row.get("qimen_star", ""),
                    "qimen_deity": qi_row.get("qimen_deity", ""),
                    "meihua_hexagram": qi_row.get("meihua_hexagram", ""),
                    "meihua_moving_line": qi_row.get("meihua_moving_line", ""),
                    "meihua_body": qi_row.get("meihua_body", ""),
                    "meihua_use": qi_row.get("meihua_use", ""),
                    "tai_sui_direction": qi_row.get("tai_sui_direction", ""),
                    "sui_po_direction": qi_row.get("sui_po_direction", ""),
                    "san_sha_direction": qi_row.get("san_sha_direction", ""),
                    "new_position_gate": qi_row.get("new_position_gate", ""),
                    "new_position_note": qi_row.get("new_position_note", ""),
                    "astro_note": qi_row.get("astro_note", ""),
                    "short_hold_days": int(qi_row["short_hold_days"]),
                    "long_hold_days": int(qi_row["long_hold_days"]),
                    "cycle_type": qi_row["cycle_type"],
                    "xuan_hold_days": int(qi_row["xuan_hold_days"]),
                    **stock_timing,
                    "buy_phase": qi_row["buy_phase"],
                    "buy_note": qi_row["buy_note"],
                    "recommended_count": int(qi_row["recommended_count"]),
                    "position_style": qi_row["position_style"],
                    "sizing_note": qi_row["sizing_note"],
                    "recommendation_note": qi_row["recommendation_note"],
                    "almanac_note": qi_row["almanac_note"],
                    "favorable_elements": qi_row["favorable_elements"],
                    "avoid_elements": qi_row["avoid_elements"],
                    "buy_shichen": qi_row["buy_shichen"],
                    "buy_time": qi_row["buy_time"],
                    "sell_shichen": qi_row["sell_shichen"],
                    "sell_time": qi_row["sell_time"],
                    "intraday_note": qi_row["intraday_note"],
                    "timing_note": qi_row["timing_note"],
                    "industry_evidence": p["industry_evidence"],
                    "name_evidence": p["name_evidence"],
                    "code_evidence": p["code_evidence"],
                    "xuan_score": compatibility(p, qi_row),
                    "xuan_reason": (
                        f"{p['xuan_note']} | {p['element_theory']} | {p['trigram_evidence']} | "
                        f"{p.get('location_evidence', '')} | "
                        f"{qi_row['almanac_note']} | {qi_row.get('astro_note', '')} | "
                        f"{stock_timing['stock_theory_basis']} | {qi_row['daily_note']}"
                    ),
                }
            record["mystic_advice"] = mystic_advice(pd.Series(record))
            day_records.append(record)
        if day_records:
            ranked = sorted(day_records, key=lambda item: item["xuan_score"], reverse=True)[:top_n]
            records.extend(ranked)
    return pd.DataFrame(records)


def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return float(dd.min()) if not dd.empty else 0.0


def run_backtest(
    prices: pd.DataFrame,
    candidates: pd.DataFrame,
    qi: pd.DataFrame,
    positions: int,
    rebalance_days: int,
    hold_mode: str,
    cycle_mode: str,
    buy_gate: str,
    initial_cash: float,
    fee_rate: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    close_raw = prices.pivot_table(
        index="date",
        columns="code",
        values="close",
        aggfunc="last",
    ).sort_index()
    close = close_raw.ffill()
    dates = list(close.index)
    cand_map = {
        pd.Timestamp(date): group.sort_values("xuan_score", ascending=False)
        for date, group in candidates.groupby("date")
    }
    qi_map = {}
    cycle_map = {}
    recommended_count_map = {}
    buy_gate_map = {}
    timing_map = {
        pd.Timestamp(row["date"]): row["timing_note"]
        for _, row in qi.iterrows()
    }
    for _, row in qi.iterrows():
        date_key = pd.Timestamp(row["date"])
        if cycle_mode == "short":
            hold_days = int(row["short_hold_days"])
            cycle = "short"
        elif cycle_mode == "long":
            hold_days = int(row["long_hold_days"])
            cycle = "long"
        elif cycle_mode == "mixed":
            hold_days = int(row["xuan_hold_days"])
            cycle = row["cycle_type"]
        else:
            hold_days = int(row.get("hierarchy_hold_days", row["xuan_hold_days"]))
            cycle = row.get("hierarchy_type", row["cycle_type"])
        qi_map[date_key] = hold_days
        cycle_map[date_key] = cycle
        recommended_count_map[date_key] = int(row.get("recommended_count", positions if positions > 0 else 0))
        gate = str(row.get("new_position_gate", "半开"))
        gate_open = gate in {"开", "半开"}
        gate_strict = gate == "开"
        buy_gate_map[date_key] = {
            "soft": bool(row["buy_allowed_soft"]) and gate_open,
            "strict": bool(row["buy_allowed_strict"]) and gate_strict,
            "none": True,
            "phase": row["buy_phase"],
            "note": f"{row['buy_note']}；{row.get('new_position_note', '')}",
            "new_position_gate": gate,
            "buy_shichen": row["buy_shichen"],
            "buy_time": row["buy_time"],
            "sell_shichen": row["sell_shichen"],
            "sell_time": row["sell_time"],
            "intraday_note": row["intraday_note"],
        }
    cash = initial_cash
    holdings: dict[str, float] = {}
    equity_records = []
    trade_records = []
    next_rebalance_idx = 0

    for idx, date in enumerate(dates):
        day_recommended_count = max(0, recommended_count_map.get(date, positions if positions > 0 else 0))
        day_target_count = min(day_recommended_count, positions) if positions > 0 else day_recommended_count
        prices_today = close.loc[date]
        portfolio_value = cash + sum(
            shares * float(prices_today.get(code, math.nan))
            for code, shares in holdings.items()
            if not math.isnan(float(prices_today.get(code, math.nan)))
        )

        if idx >= next_rebalance_idx and date in cand_map:
            day_candidates = cand_map[date]
            available_rows = day_candidates[
                day_candidates["code"].isin(close.columns)
                & day_candidates["code"].map(lambda code: not pd.isna(prices_today.get(code)))
            ]
            if day_target_count <= 0:
                gate_info = buy_gate_map.get(date, {"phase": "观气守仓", "buy_time": "观望", "sell_time": "观望"})
                next_rebalance_idx = idx + 1
                equity_records.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "equity": portfolio_value,
                        "cash": cash,
                        "holding_count": len(holdings),
                        "target_count": day_target_count,
                        "recommended_count": day_recommended_count,
                        "next_rebalance_date": dates[min(next_rebalance_idx, len(dates) - 1)].strftime("%Y-%m-%d"),
                        "planned_hold_days": qi_map.get(date, rebalance_days),
                        "cycle_type": cycle_map.get(date, "观气"),
                        "buy_phase": gate_info["phase"],
                        "buy_time": gate_info.get("buy_time", "观望"),
                        "planned_sell_date": date.strftime("%Y-%m-%d"),
                        "sell_time": gate_info.get("sell_time", "观望"),
                        "timing_note": "仓门闭或日课不取，今日不立新仓",
                        "holdings": "|".join(sorted(holdings)),
                    }
                )
                continue
            if len(available_rows) >= day_target_count:
                target_rows = available_rows.head(day_target_count).copy()
                if hold_mode == "xuan":
                    if cycle_mode == "short":
                        target_rows["effective_hold_days"] = target_rows["short_hold_days"]
                    elif cycle_mode == "long":
                        target_rows["effective_hold_days"] = target_rows["long_hold_days"]
                    elif cycle_mode == "mixed":
                        target_rows["effective_hold_days"] = target_rows["stock_hold_days"]
                    else:
                        target_rows["effective_hold_days"] = target_rows["stock_hold_days"]
                    planned_hold_days = int(round(float(target_rows["effective_hold_days"].median())))
                    cycle_type = "stock-hierarchical" if cycle_mode == "hierarchical" else "stock-mixed" if cycle_mode == "mixed" else cycle_mode
                    buy_time = "|".join(target_rows["stock_buy_time"].astype(str).unique())
                    sell_time = "|".join(target_rows["stock_sell_time"].astype(str).unique())
                else:
                    target_rows["effective_hold_days"] = rebalance_days
                    planned_hold_days = rebalance_days
                    cycle_type = "fixed"
                    buy_time = "09:45"
                    sell_time = "14:45"
            else:
                target_rows = available_rows
                planned_hold_days = qi_map.get(date, rebalance_days) if hold_mode == "xuan" else rebalance_days
                cycle_type = cycle_map.get(date, "fixed") if hold_mode == "xuan" else "fixed"
                buy_time = "09:45"
                sell_time = "14:45"
            planned_exit_idx = min(idx + planned_hold_days, len(dates) - 1)
            planned_sell_date = dates[planned_exit_idx].strftime("%Y-%m-%d")
            gate_info = buy_gate_map.get(
                date,
                {
                    "soft": True,
                    "strict": True,
                    "none": True,
                    "phase": "固定开仓",
                    "note": "固定调仓",
                    "buy_shichen": "巳初",
                    "buy_time": "09:45",
                    "sell_shichen": "未末",
                    "sell_time": "14:45",
                    "intraday_note": "固定调仓",
                },
            )
            buy_allowed = gate_info[buy_gate] if hold_mode == "xuan" else True
            timing_note = timing_map.get(date, f"固定{rebalance_days}日调仓")
            if len(target_rows) < day_target_count:
                next_rebalance_idx = idx + 1
                equity_records.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "equity": portfolio_value,
                        "cash": cash,
                        "holding_count": len(holdings),
                        "target_count": day_target_count,
                        "recommended_count": day_recommended_count,
                        "next_rebalance_date": dates[min(next_rebalance_idx, len(dates) - 1)].strftime("%Y-%m-%d"),
                        "planned_hold_days": planned_hold_days,
                        "cycle_type": cycle_type,
                        "buy_phase": gate_info["phase"],
                        "buy_time": buy_time,
                        "planned_sell_date": planned_sell_date,
                        "sell_time": sell_time,
                        "timing_note": "候选不足，顺延一日",
                        "holdings": "|".join(sorted(holdings)),
                    }
                )
                continue
            target_codes = target_rows["code"].tolist()
            target_by_code = target_rows.set_index("code")
            target_set = set(target_codes)
            buys_executed = 0

            for code in list(holdings):
                price = prices_today.get(code)
                if code not in target_set and not pd.isna(price):
                    proceeds = holdings.pop(code) * float(price) * (1 - fee_rate)
                    cash += proceeds
                    trade_records.append(
                        {
                            "date": date.strftime("%Y-%m-%d"),
                            "action": "SELL",
                            "code": code,
                            "price": float(price),
                            "cash_after": cash,
                            "planned_hold_days": planned_hold_days,
                            "cycle_type": cycle_type,
                            "buy_phase": gate_info["phase"],
                            "buy_time": buy_time,
                            "planned_sell_date": date.strftime("%Y-%m-%d"),
                            "sell_time": sell_time,
                            "timing_note": timing_note,
                        }
                    )

            portfolio_value = cash + sum(
                shares * float(prices_today.get(code, math.nan))
                for code, shares in holdings.items()
                if not math.isnan(float(prices_today.get(code, math.nan)))
            )
            slots_to_fill = max(day_target_count - len(holdings), 0)
            slot_value = portfolio_value / max(day_target_count, 1)
            for code in target_codes:
                if slots_to_fill <= 0:
                    break
                if not buy_allowed:
                    break
                if code in holdings:
                    continue
                price = prices_today.get(code)
                if pd.isna(price) or price <= 0:
                    continue
                budget = min(slot_value, cash)
                if budget <= 0:
                    continue
                shares = budget * (1 - fee_rate) / float(price)
                holdings[code] = shares
                slots_to_fill -= 1
                buys_executed += 1
                cash -= budget
                trade_records.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "action": "BUY",
                        "code": code,
                        "price": float(price),
                        "cash_after": cash,
                        "planned_hold_days": int(target_by_code.loc[code, "effective_hold_days"]),
                        "cycle_type": str(target_by_code.loc[code, "stock_cycle_type"]),
                        "buy_phase": gate_info["phase"],
                        "buy_time": str(target_by_code.loc[code, "stock_buy_time"]),
                        "planned_sell_date": dates[min(idx + int(target_by_code.loc[code, "effective_hold_days"]), len(dates) - 1)].strftime("%Y-%m-%d"),
                        "sell_time": str(target_by_code.loc[code, "stock_sell_time"]),
                        "timing_note": str(target_by_code.loc[code, "stock_timing_reason"]),
                    }
                )
            if buys_executed > 0 or holdings:
                next_rebalance_idx = planned_exit_idx
            else:
                next_rebalance_idx = idx + 1

        portfolio_value = cash + sum(
            shares * float(prices_today.get(code, math.nan))
            for code, shares in holdings.items()
            if not math.isnan(float(prices_today.get(code, math.nan)))
        )
        display_hold_days = qi_map.get(date, rebalance_days) if hold_mode == "xuan" else rebalance_days
        display_buy_time = buy_gate_map.get(date, {"buy_time": "09:45"})["buy_time"] if hold_mode == "xuan" else "09:45"
        display_sell_time = buy_gate_map.get(date, {"sell_time": "14:45"})["sell_time"] if hold_mode == "xuan" else "14:45"
        display_cycle = cycle_map.get(date, "fixed") if hold_mode == "xuan" else "fixed"
        if date in cand_map and hold_mode == "xuan":
            top_rows = cand_map[date].head(day_target_count)
            if not top_rows.empty:
                display_hold_days = int(round(float(top_rows["stock_hold_days"].median())))
                display_buy_time = "|".join(top_rows["stock_buy_time"].astype(str).unique())
                display_sell_time = "|".join(top_rows["stock_sell_time"].astype(str).unique())
                display_cycle = "stock-hierarchical" if cycle_mode == "hierarchical" else "stock-mixed"
        equity_records.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "equity": portfolio_value,
                "cash": cash,
                "holding_count": len(holdings),
                "target_count": day_target_count,
                "recommended_count": day_recommended_count,
                "next_rebalance_date": dates[min(next_rebalance_idx, len(dates) - 1)].strftime("%Y-%m-%d"),
                "planned_hold_days": display_hold_days,
                "cycle_type": display_cycle,
                "buy_phase": buy_gate_map.get(date, {"phase": "固定开仓"})["phase"] if hold_mode == "xuan" else "固定开仓",
                "buy_time": display_buy_time,
                "planned_sell_date": dates[min(idx + display_hold_days, len(dates) - 1)].strftime("%Y-%m-%d"),
                "sell_time": display_sell_time,
                "timing_note": timing_map.get(date, f"固定{rebalance_days}日调仓") if hold_mode == "xuan" else f"固定{rebalance_days}日调仓",
                "holdings": "|".join(sorted(holdings)),
            }
        )

    return pd.DataFrame(equity_records), pd.DataFrame(trade_records)


def write_report(
    output_dir: Path,
    args: argparse.Namespace,
    profiles: pd.DataFrame,
    qi: pd.DataFrame,
    candidates: pd.DataFrame,
    equity: pd.DataFrame,
    trades: pd.DataFrame,
) -> None:
    final_equity = float(equity["equity"].iloc[-1])
    total_return = final_equity / args.initial_cash - 1.0
    drawdown = max_drawdown(equity["equity"])
    days = len(equity)
    years = max(days / 252.0, 1e-9)
    annualized = (final_equity / args.initial_cash) ** (1 / years) - 1
    candidate_counts = candidates.groupby("date").size()
    complete_dates = candidate_counts[candidate_counts >= args.candidate_top_n].index
    latest_complete_date = complete_dates.max() if len(complete_dates) else candidates["date"].max()
    qi_by_date = qi.set_index("date")
    latest_date = candidates["date"].max()
    latest_recommended_count = int(qi_by_date.loc[latest_date, "recommended_count"]) if latest_date in qi_by_date.index else 5
    complete_recommended_count = int(qi_by_date.loc[latest_complete_date, "recommended_count"]) if latest_complete_date in qi_by_date.index else 5
    latest_candidates = candidates[candidates["date"] == latest_date].head(latest_recommended_count)
    latest_complete_candidates = candidates[candidates["date"] == latest_complete_date].head(complete_recommended_count)
    element_dist = profiles["primary_element"].value_counts().reindex(list(ELEMENT_CN.values())).fillna(0).astype(int)

    lines = [
        "# XuanMarket Lab Report",
        "",
        "这是独立的象数学文化模型实验，不构成投资建议。",
        "",
        "## Run Config",
        "",
        f"- start_date: `{args.start_date}`",
        f"- end_date: `{args.end_date or 'latest local date'}`",
        f"- max_stocks: `{args.max_stocks}`",
        f"- positions: `{args.positions}`",
        f"- hold_mode: `{args.hold_mode}`",
        f"- cycle_mode: `{args.cycle_mode}`",
        f"- buy_gate: `{args.buy_gate}`",
        f"- fixed_rebalance_days: `{args.rebalance_days}`",
        f"- candidate_top_n: `{args.candidate_top_n}`",
        "",
        "## Backtest Summary",
        "",
        f"- trading_days: `{days}`",
        f"- initial_cash: `{args.initial_cash:,.2f}`",
        f"- final_equity: `{final_equity:,.2f}`",
        f"- total_return: `{total_return:.2%}`",
        f"- annualized_return: `{annualized:.2%}`",
        f"- max_drawdown: `{drawdown:.2%}`",
        f"- trades: `{len(trades)}`",
        f"- avg_planned_hold_days: `{equity['planned_hold_days'].mean():.2f}`",
        f"- latest_local_candidate_date: `{candidates['date'].max()}`",
        f"- latest_local_candidate_count: `{int(candidate_counts.loc[candidates['date'].max()])}`",
        f"- latest_complete_candidate_date: `{latest_complete_date}`",
        "",
        "## Stock Element Distribution",
        "",
    ]
    for element_cn, count in element_dist.items():
        lines.append(f"- {element_cn}: `{count}`")

    lines.extend(["", "## Latest Qi", ""])
    latest_qi = qi.iloc[-1]
    for col in [
        "date",
        "year_ganzhi",
        "year_qi",
        "day_ganzhi",
        "year_symbol",
        "year_nayin",
        "day_symbol",
        "day_nayin",
        "month_ganzhi",
        "month_element",
        "lunar_month_approx",
        "lunar_day_approx",
        "si_pillar",
        "wu_pillar",
        "wei_pillar",
        "branch_relation_note",
        "kongwang",
        "kongwang_note",
        "nobleman_branches",
        "travel_horse_branch",
        "peach_blossom_branch",
        "huagai_branch",
        "lu_branch",
        "yang_ren_branch",
        "shensha_note",
        "qimen_door",
        "qimen_door_direction",
        "qimen_star",
        "qimen_deity",
        "qimen_note",
        "meihua_hexagram",
        "meihua_moving_line",
        "meihua_body",
        "meihua_use",
        "meihua_note",
        "mansion",
        "mansion_luck",
        "jianchu",
        "day_deity",
        "day_deity_luck",
        "annual_star",
        "annual_star_direction",
        "day_star",
        "day_star_direction",
        "moon_phase",
        "tai_sui_direction",
        "sui_po_direction",
        "san_sha_direction",
        "new_position_gate",
        "new_position_note",
        "astro_note",
        "solar_term",
        "days_since_solar_term",
        "main_qi",
        "secondary_qi",
        "polarity",
        "trigram",
        "short_hold_days",
        "long_hold_days",
        "legacy_cycle_type",
        "legacy_hold_days",
        "hierarchy_type",
        "hierarchy_hold_days",
        "hierarchy_note",
        "cycle_type",
        "xuan_hold_days",
        "buy_phase",
        "buy_note",
        "recommended_count",
        "position_style",
        "sizing_note",
        "recommendation_note",
        "buy_shichen",
        "buy_time",
        "sell_shichen",
        "sell_time",
        "intraday_note",
        "timing_note",
        "daily_note",
    ]:
        lines.append(f"- {col}: `{latest_qi[col]}`")

    lines.extend(["", "## Holding-Time Distribution", ""])
    hold_dist = equity["planned_hold_days"].value_counts().sort_index()
    for hold_days, count in hold_dist.items():
        lines.append(f"- {int(hold_days)} days: `{int(count)}`")

    lines.extend(["", "## Cycle And Buy Phase Distribution", ""])
    for cycle_type, count in equity["cycle_type"].value_counts().items():
        lines.append(f"- cycle `{cycle_type}`: `{int(count)}`")
    for buy_phase, count in equity["buy_phase"].value_counts().items():
        lines.append(f"- buy_phase `{buy_phase}`: `{int(count)}`")

    lines.extend(["", "## Latest Symbolic Candidate Pool", ""])
    for _, row in latest_candidates.iterrows():
        lines.append(
            f"- `{row['code']}` {row['code_name']} | {row['primary_element']} | "
            f"{row.get('registered_region', '')}{row.get('registered_city', '')}/{row.get('registered_direction', '')}方 | "
            f"score `{row['xuan_score']:.4f}` | {row['stock_cycle_type']} hold `{row['stock_hold_days']}` | "
            f"{row['buy_phase']} | buy `{row['stock_buy_time']}` | sell `{row['stock_sell_time']}` | "
            f"{row['mystic_advice']} | {row['stock_timing_reason']} | {row['xuan_reason']}"
        )

    if latest_complete_date != candidates["date"].max():
        lines.extend(
            [
                "",
                f"## Latest Complete Candidate Pool ({latest_complete_date})",
                "",
            ]
        )
        for _, row in latest_complete_candidates.iterrows():
            lines.append(
                f"- `{row['code']}` {row['code_name']} | {row['primary_element']} | "
                f"{row.get('registered_region', '')}{row.get('registered_city', '')}/{row.get('registered_direction', '')}方 | "
                f"score `{row['xuan_score']:.4f}` | {row['stock_cycle_type']} hold `{row['stock_hold_days']}` | "
                f"{row['buy_phase']} | buy `{row['stock_buy_time']}` | sell `{row['stock_sell_time']}` | "
                f"{row['mystic_advice']} | {row['stock_timing_reason']} | {row['xuan_reason']}"
            )

    lines.extend(
        [
            "",
            "## Output Files",
            "",
            "- `stock_xuan_profile.csv`",
            "- `daily_qi_profile.csv`",
            "- `daily_candidates.csv`",
            "- `xuan_trades.csv`",
            "- `xuan_equity_curve.csv`",
            "- `xuan_report.md`",
            "",
            "## Notes",
            "",
            "- 干支日柱和节气用工程化近似，适合实验，不适合当作严肃历法结果。",
            "- 买卖由象数兼容度、买入相位、短长周期持股规则决定，价格只用于成交模拟和收益统计。",
            "- 后续可以增加农历、月相、二十八宿、纳音、脏腑、地域方位和更严格的冲合刑害规则。",
        ]
    )
    (output_dir / "xuan_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    paths = Paths(Path(args.daily_dir), Path(args.labels), Path(args.locations), Path(args.output_dir))
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    labels = pd.read_csv(paths.labels_path)
    locations = load_location_profiles(paths.locations_path)
    profiles = build_stock_profiles(labels, locations)

    files = discover_price_files(paths.daily_dir)
    prices = load_prices(files, args.start_date, args.end_date, args.max_stocks)
    active_codes = set(prices["code"].unique())
    profiles = profiles[profiles["code"].isin(active_codes)].copy()
    prices = prices[prices["code"].isin(set(profiles["code"]))].copy()

    dates = list(prices["date"].drop_duplicates().sort_values())
    qi = build_daily_qi(dates)
    candidates = build_candidates(prices, profiles, qi, args.candidate_top_n)
    equity, trades = run_backtest(
        prices,
        candidates,
        qi,
        args.positions,
        args.rebalance_days,
        args.hold_mode,
        args.cycle_mode,
        args.buy_gate,
        args.initial_cash,
        args.fee_rate,
    )

    profiles.to_csv(paths.output_dir / "stock_xuan_profile.csv", index=False)
    qi.to_csv(paths.output_dir / "daily_qi_profile.csv", index=False)
    candidates.to_csv(paths.output_dir / "daily_candidates.csv", index=False)
    equity.to_csv(paths.output_dir / "xuan_equity_curve.csv", index=False)
    trades.to_csv(paths.output_dir / "xuan_trades.csv", index=False)
    write_report(paths.output_dir, args, profiles, qi, candidates, equity, trades)

    print("XuanMarket Lab completed")
    print(f"stocks: {profiles['code'].nunique()}")
    print(f"trading_days: {len(equity)}")
    print(f"final_equity: {equity['equity'].iloc[-1]:.2f}")
    print(f"report: {paths.output_dir / 'xuan_report.md'}")


if __name__ == "__main__":
    main()
