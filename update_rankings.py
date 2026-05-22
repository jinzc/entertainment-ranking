#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合影视榜单聚合爬虫 V11
核心修复：
1. 微博文娱榜使用官方API的flag_desc字段直接筛选（剧集/综艺/电影/演出/音乐）
2. 微博剧集/电影直接使用flag_desc分类，不再关键词匹配
3. 抖音使用dabenshi.cn聚合API（GitHub Actions环境测试通过）
4. 百度保留多源尝试
5. 彻底移除所有写死数据
6. 抓取失败返回空 + error提示
"""

import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

OUTPUT_FILE = "data/all_rankings.json"
HISTORY_FILE = "data/history.json"

def save_json(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(filepath, default=None):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}

def get_timestamp():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

def get_hour_key():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H")

def safe_request(url, headers=None, timeout=15):
    try:
        h = headers or HEADERS
        resp = requests.get(url, headers=h, timeout=timeout)
        if resp.status_code == 200:
            return resp
        else:
            print(f"[WARN] HTTP {resp.status_code}: {url}")
    except Exception as e:
        print(f"[WARN] 请求失败 {url}: {e}")
    return None

# ============ 1. 微博热搜API（官方） ============
def fetch_weibo_hot_search():
    """获取微博热搜榜 - 官方API"""
    try:
        print("[INFO] 尝试微博官方API...")
        resp = requests.get("https://weibo.com/ajax/side/hotSearch",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://weibo.com/hot/search",
                "Cookie": "SUB=_2AkMVWDzQf8NxqwJRmP0Sz2_qZY5_ygvEieKjBAkJRMxHRl-W9XqnYgtP6TVn8hJ3DyLwVDkjGQJ7D9EVp2xO1z7xKDs;"
            }, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data and "realtime" in data.get("data", {}):
                realtime = data["data"]["realtime"]
                items = []
                for i, item in enumerate(realtime):
                    items.append({
                        "rank": i+1,
                        "title": item.get("word", ""),
                        "hot": str(item.get("num", "")),
                        "flag_desc": item.get("flag_desc", ""),
                        "label_name": item.get("label_name", "")
                    })
                print(f"[INFO] 微博官方API成功: {len(items)}条")
                if len(items) >= 50:
                    return items
    except Exception as e:
        print(f"[WARN] 微博官方API失败: {e}")

    # 备用: ALAPI
    try:
        print("[INFO] 尝试ALAPI微博热搜...")
        resp = requests.get("https://v2.alapi.cn/api/new/wbtop",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 200 and data.get("data"):
                items = []
                for i, item in enumerate(data["data"]):
                    items.append({
                        "rank": i+1,
                        "title": item.get("hot_title", item.get("title", "")),
                        "hot": str(item.get("hot", item.get("num", ""))),
                        "flag_desc": "",
                        "label_name": ""
                    })
                print(f"[INFO] ALAPI成功: {len(items)}条")
                if len(items) >= 10:
                    return items
    except Exception as e:
        print(f"[WARN] ALAPI失败: {e}")

    print("[ERROR] 所有微博API都失败了，返回空")
    return []

# ============ 2. 微博文娱热搜榜 ============
def fetch_weibo_entertainment():
    all_hot = fetch_weibo_hot_search()
    if not all_hot:
        print("[ERROR] 微博热搜抓取失败，文娱榜返回空")
        return []

    # 使用官方flag_desc字段筛选文娱内容
    entertainment_types = ["剧集", "综艺", "电影", "演出", "音乐"]
    entertainment_items = []

    for item in all_hot:
        flag_desc = item.get("flag_desc", "")
        if flag_desc in entertainment_types:
            entertainment_items.append(item)

    print(f"[INFO] 微博文娱热搜(flag_desc筛选): {len(entertainment_items)}条")

    # 如果官方分类少于20条，用关键词补充到50条
    if len(entertainment_items) < 20:
        print(f"[WARN] 官方分类仅{len(entertainment_items)}条，用关键词补充")
        seen = {item["title"] for item in entertainment_items}

        keywords = [
            "肖战", "王一博", "迪丽热巴", "赵丽颖", "杨幂", "杨紫", "刘亦菲",
            "易烊千玺", "王俊凯", "王源", "华晨宇", "邓紫棋", "周杰伦",
            "鹿晗", "张艺兴", "蔡徐坤", "李现", "朱一龙", "杨洋",
            "成毅", "檀健次", "王鹤棣", "吴磊", "白敬亭", "罗云熙",
            "任嘉伦", "龚俊", "许凯", "张凌赫", "赵露思", "虞书欣",
            "白鹿", "谭松韵", "李沁", "周冬雨", "倪妮", "刘诗诗",
            "唐嫣", "Angelababy", "鞠婧祎", "杨超越", "孟子义",
            "张婧仪", "周也", "田曦薇", "陈都灵", "沈月", "章若楠",
            "关晓彤", "宋祖儿", "林允", "张天爱", "古力娜扎", "佟丽娅",
            "高圆圆", "林志玲", "舒淇", "章子怡", "巩俐", "张曼玉",
            "周星驰", "成龙", "李连杰", "刘德华", "张学友", "郭富城",
            "梁朝伟", "周润发", "葛优", "黄渤", "徐峥", "沈腾",
            "吴京", "张译", "雷佳音", "于和伟", "陈道明", "张国立",
            "周深", "毛不易", "薛之谦", "李荣浩", "张杰", "林俊杰",
            "陈奕迅", "汪苏泷", "刘宇宁", "许嵩", "华晨宇", "邓紫棋",
            "王菲", "那英", "韩红", "孙燕姿", "蔡依林", "梁静茹",
            "五月天", "苏打绿", "告五人", "凤凰传奇", "TFBOYS",
            "时代少年团", "陈立农", "范丞丞", "黄明昊", "刘雨昕",
            "金秀贤", "宋慧乔", "全智贤", "李敏镐", "朴叙俊", "孔刘",
            "BLACKPINK", "BTS", "EXO", "TWICE", "IVE", "aespa",
            "韩剧", "韩娱", "Kpop", "内娱", "娱", "瓜", "爆料",
            "明星", "演员", "歌手", "综艺", "电视剧", "电影", "票房", "开播", "杀青",
            "导演", "编剧", "制片", "剧组", "路透", "预告", "片花",
            "定档", "上映", "排片", "首映", "点映", "路演",
            "豆瓣", "猫眼", "淘票票", "评分", "口碑", "烂番茄",
            "撤档", "改档", "延期", "重映", "密钥",
            "破亿", "破十亿", "票房冠军", "年度票房", "观影",
            "红毯", "颁奖", "金像奖", "金马奖", "金鸡奖", "百花奖",
            "华表奖", "金鹰奖", "飞天奖", "白玉兰", "金钟奖",
            "戛纳", "威尼斯", "柏林", "奥斯卡", "金球奖", "艾美奖",
            "格莱美", "全英音乐奖", "公告牌", "MTV",
            "恋情", "结婚", "离婚", "分手", "复合", "出轨", "官宣",
            "求婚", "订婚", "婚礼", "蜜月", "怀孕", "生子",
            "绯闻", "八卦", "爆料", "实锤", "澄清", "辟谣",
            "番位", "撕番", "C位", "站位", "海报", "番",
            "应援", "打榜", "控评", "反黑", "站姐", "代拍",
            "粉丝", "黑粉", "路人", "脱粉", "回踩", "塌房",
            "造型", "穿搭", "时尚", "杂志", "封面", "代言",
            "高定", "红毯", "时装周", "巴黎", "米兰", "纽约",
            "直播", "带货", "商务", "资源", "饼", "瓜主",
            "演唱会", "音乐节", "巡演", "live", "现场", "开票",
            "加场", "售罄", "黄牛", "抢票", "大麦", "猫眼",
            "跑男", "极挑", "向往", "快本", "天天", "王牌",
            "声生不息", "乘风破浪", "披荆斩棘", "歌手", "天赐",
            "脱口秀", "喜剧大赛", "德云", "麻花", "开心",
            "恋综", "推理", "密室", "逃脱", "剧本杀",
            "动漫", "动画", "二次元", "Cosplay", "漫展",
            "游戏", "电竞", "LOL", "王者荣耀", "原神", "吃鸡",
            "主播", "UP主", "B站", "抖音", "快手", "小红书",
            "网红", "博主", "达人", "MCN", "直播", "短视频",
            "Vlog", "Plog", "穿搭", "美妆", "护肤", "健身",
            "减肥", "瘦身", "整容", "医美", "颜值", "身材",
            "宠物", "萌宠", "猫", "狗", "动物园", "海洋生物",
        ]

        for item in all_hot:
            if item["title"] in seen:
                continue
            title = item["title"]
            for kw in keywords:
                if kw in title:
                    entertainment_items.append(item)
                    seen.add(title)
                    break
            if len(entertainment_items) >= 50:
                break

    return entertainment_items[:50]

# ============ 3. 微博剧集热度榜 ============
def fetch_weibo_tv():
    all_hot = fetch_weibo_hot_search()
    if not all_hot:
        print("[ERROR] 微博热搜抓取失败，剧集榜返回空")
        return []

    # 使用官方flag_desc="剧集"筛选
    tv_items = [item for item in all_hot if item.get("flag_desc") == "剧集"]

    result = []
    seen = set()
    for item in tv_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            result.append({
                "rank": len(result) + 1,
                "title": item["title"],
                "hot": item.get("hot", ""),
                "score": "",
                "platform": "",
                "cast": "",
                "source": "热搜"
            })

    print(f"[INFO] 微博剧集(flag_desc=剧集): {len(result)}条")
    return result

# ============ 4. 微博电影热度榜 ============
def fetch_weibo_movie():
    all_hot = fetch_weibo_hot_search()
    if not all_hot:
        print("[ERROR] 微博热搜抓取失败，电影榜返回空")
        return []

    # 使用官方flag_desc="电影"筛选
    movie_items = [item for item in all_hot if item.get("flag_desc") == "电影"]

    result = []
    seen = set()
    for item in movie_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            result.append({
                "rank": len(result) + 1,
                "title": item["title"],
                "hot": item.get("hot", ""),
                "score": "",
                "region": "",
                "genre": "",
                "cast": "",
                "source": "热搜"
            })

    print(f"[INFO] 微博电影(flag_desc=电影): {len(result)}条")
    return result

# ============ 5. 豆瓣实时热门电影榜 ============
def fetch_douban_movies():
    url = "https://m.douban.com/rexxar/api/v2/subject_collection/movie_real_time_hotest/items?start=0&count=50"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Referer": "https://m.douban.com/subject_collection/movie_real_time_hotest",
        "Accept": "application/json",
    }
    resp = safe_request(url, headers=headers)

    if resp:
        try:
            data = resp.json()
            items_data = data.get("subject_collection_items", data.get("items", []))
            items = []
            for i, item in enumerate(items_data):
                rating = item.get("rating", {})
                score = str(rating.get("value", "")) if rating else ""
                items.append({
                    "rank": i + 1,
                    "title": item.get("title", ""),
                    "score": score,
                    "rating_count": "",
                    "cover": item.get("cover_url", item.get("pic", {}).get("normal", "")),
                    "url": item.get("url", ""),
                    "types": ", ".join(item.get("genres", [])[:3]),
                    "regions": ", ".join(item.get("countries", [])[:2]),
                    "release_date": item.get("year", ""),
                    "actors": ", ".join([a.get("name", "") for a in item.get("actors", [])[:3]]),
                })
            print(f"[INFO] 豆瓣实时热门电影: {len(items)}条")
            return items
        except Exception as e:
            print(f"[ERROR] 豆瓣电影解析失败: {e}")

    print("[ERROR] 豆瓣电影抓取失败，返回空")
    return []

# ============ 6. 豆瓣实时热门电视榜 ============
def fetch_douban_tv():
    url = "https://m.douban.com/rexxar/api/v2/subject_collection/tv_real_time_hotest/items?start=0&count=50"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        "Referer": "https://m.douban.com/subject_collection/tv_real_time_hotest",
        "Accept": "application/json",
    }
    resp = safe_request(url, headers=headers)

    if resp:
        try:
            data = resp.json()
            items_data = data.get("subject_collection_items", data.get("items", []))
            items = []
            for i, item in enumerate(items_data):
                rating = item.get("rating", {})
                score = str(rating.get("value", "")) if rating else ""
                items.append({
                    "rank": i + 1,
                    "title": item.get("title", ""),
                    "score": score,
                    "rating_count": "",
                    "cover": item.get("cover_url", item.get("pic", {}).get("normal", "")),
                    "url": item.get("url", ""),
                    "types": ", ".join(item.get("genres", [])[:3]),
                    "regions": ", ".join(item.get("countries", [])[:2]),
                    "release_date": item.get("year", ""),
                    "actors": ", ".join([a.get("name", "") for a in item.get("actors", [])[:3]]),
                })
            print(f"[INFO] 豆瓣实时热门电视: {len(items)}条")
            return items
        except Exception as e:
            print(f"[ERROR] 豆瓣电视解析失败: {e}")

    print("[ERROR] 豆瓣电视抓取失败，返回空")
    return []

# ============ 7. 抖音院线电影 ============
def fetch_douyin_movies():
    """抖音影视榜 - 通过聚合API获取"""
    # 尝试多个聚合API
    apis = [
        "https://api.aa1.cn/api/douyin-hot",
        "https://dabenshi.cn/other/api/hot.php?type=douyinhot",
    ]

    for api_url in apis:
        try:
            print(f"[INFO] 尝试抖音API: {api_url}...")
            resp = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = []

                # 处理不同API的数据格式
                if isinstance(data, list):
                    all_items = data
                elif isinstance(data, dict):
                    all_items = data.get("data", data.get("result", []))
                else:
                    continue

                movie_keywords = ["电影", "票房", "上映", "首映", "影片", "导演", "主演", "影院", "院线"]
                for i, item in enumerate(all_items):
                    if isinstance(item, dict):
                        title = item.get("word", item.get("title", ""))
                        hot = str(item.get("hot_value", item.get("hot", item.get("num", ""))))
                    else:
                        continue

                    for kw in movie_keywords:
                        if kw in title:
                            items.append({
                                "rank": len(items) + 1,
                                "title": title,
                                "hot": hot,
                                "score": "",
                                "want_count": "",
                                "types": "",
                                "actors": ""
                            })
                            break

                if len(items) >= 3:
                    print(f"[INFO] 抖音电影数据: {len(items)}条")
                    return items[:10]
        except Exception as e:
            print(f"[WARN] {api_url} 失败: {e}")
            continue

    print("[ERROR] 所有抖音API都失败了，返回空")
    return []

# ============ 8. 抖音剧集 ============
def fetch_douyin_tv():
    """抖音剧集榜"""
    apis = [
        "https://api.aa1.cn/api/douyin-hot",
        "https://dabenshi.cn/other/api/hot.php?type=douyinhot",
    ]

    for api_url in apis:
        try:
            print(f"[INFO] 尝试抖音API: {api_url}...")
            resp = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = []

                if isinstance(data, list):
                    all_items = data
                elif isinstance(data, dict):
                    all_items = data.get("data", data.get("result", []))
                else:
                    continue

                tv_keywords = ["剧", "电视剧", "剧集", "开播", "大结局", "预告", "定档", "主角", "追剧", "剧情"]
                for i, item in enumerate(all_items):
                    if isinstance(item, dict):
                        title = item.get("word", item.get("title", ""))
                        hot = str(item.get("hot_value", item.get("hot", item.get("num", ""))))
                    else:
                        continue

                    for kw in tv_keywords:
                        if kw in title:
                            items.append({
                                "rank": len(items) + 1,
                                "title": title,
                                "hot": hot,
                                "score": "",
                                "want_count": "",
                                "types": "",
                                "actors": ""
                            })
                            break

                if len(items) >= 3:
                    print(f"[INFO] 抖音剧集数据: {len(items)}条")
                    return items[:10]
        except Exception as e:
            print(f"[WARN] {api_url} 失败: {e}")
            continue

    print("[ERROR] 所有抖音API都失败了，返回空")
    return []

# ============ 9. 百度热搜-电影榜 ============
def fetch_baidu_movies():
    """获取百度热搜电影榜 - 多源尝试"""
    # 方法1: 百度官方API
    try:
        print("[INFO] 尝试百度官方API...")
        url = "https://top.baidu.com/api/board?platform=wise&tab=movie"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://top.baidu.com/board?tab=movie",
        }
        resp = safe_request(url, headers=headers)
        if resp:
            data = resp.json()
            if "data" in data and "cards" in data["data"]:
                cards = data["data"]["cards"]
                if cards and len(cards) > 0:
                    content = cards[0].get("content", [])
                    items = []
                    for i, item in enumerate(content):
                        items.append({
                            "rank": i + 1,
                            "title": item.get("word", ""),
                            "hot_score": str(item.get("hotScore", "")),
                            "hot_desc": str(item.get("hotScore", "")),
                            "cover": item.get("img", ""),
                            "url": item.get("url", ""),
                            "desc": item.get("desc", "")[:80] + "..." if len(item.get("desc", "")) > 80 else item.get("desc", ""),
                        })
                    if len(items) > 0:
                        print(f"[INFO] 百度电影榜: {len(items)}条")
                        return items
    except Exception as e:
        print(f"[WARN] 百度官方API失败: {e}")

    # 方法2: 通过百度搜索风云榜网页版
    try:
        print("[INFO] 尝试百度搜索风云榜...")
        resp = requests.get("https://top.baidu.com/board?tab=movie",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if resp.status_code == 200:
            html = resp.text
            pattern = r'"content":(\[.*?\])'
            match = re.search(pattern, html)
            if match:
                try:
                    content = json.loads(match.group(1))
                    items = []
                    for i, item in enumerate(content):
                        items.append({
                            "rank": i + 1,
                            "title": item.get("word", ""),
                            "hot_score": str(item.get("hotScore", "")),
                            "hot_desc": str(item.get("hotScore", "")),
                            "cover": item.get("img", ""),
                            "url": item.get("url", ""),
                            "desc": item.get("desc", "")[:80] + "..." if len(item.get("desc", "")) > 80 else item.get("desc", ""),
                        })
                    if len(items) > 0:
                        print(f"[INFO] 百度搜索风云榜: {len(items)}条")
                        return items
                except:
                    pass
    except Exception as e:
        print(f"[WARN] 百度搜索风云榜失败: {e}")

    print("[ERROR] 百度电影抓取失败，返回空")
    return []

# ============ 10. 百度热搜-电视剧榜 ============
def fetch_baidu_tv():
    """获取百度热搜电视剧榜"""
    # 方法1: 百度官方API
    try:
        print("[INFO] 尝试百度官方API...")
        url = "https://top.baidu.com/api/board?platform=wise&tab=teleplay"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://top.baidu.com/board?tab=teleplay",
        }
        resp = safe_request(url, headers=headers)
        if resp:
            data = resp.json()
            if "data" in data and "cards" in data["data"]:
                cards = data["data"]["cards"]
                if cards and len(cards) > 0:
                    content = cards[0].get("content", [])
                    items = []
                    for i, item in enumerate(content):
                        items.append({
                            "rank": i + 1,
                            "title": item.get("word", ""),
                            "hot_score": str(item.get("hotScore", "")),
                            "hot_desc": str(item.get("hotScore", "")),
                            "cover": item.get("img", ""),
                            "url": item.get("url", ""),
                            "desc": item.get("desc", "")[:80] + "..." if len(item.get("desc", "")) > 80 else item.get("desc", ""),
                        })
                    if len(items) > 0:
                        print(f"[INFO] 百度电视剧榜: {len(items)}条")
                        return items
    except Exception as e:
        print(f"[WARN] 百度官方API失败: {e}")

    print("[ERROR] 百度电视剧抓取失败，返回空")
    return []

# ============ 主流程 ============
def main():
    print(f"[{get_timestamp()}] 开始采集9个影视榜单...")

    weibo_entertainment = fetch_weibo_entertainment()
    print(f"  微博文娱热搜: {len(weibo_entertainment)} 条")

    weibo_tv = fetch_weibo_tv()
    print(f"  微博剧集热度: {len(weibo_tv)} 条")

    weibo_movie = fetch_weibo_movie()
    print(f"  微博电影热度: {len(weibo_movie)} 条")

    douban_movies = fetch_douban_movies()
    print(f"  豆瓣电影: {len(douban_movies)} 条")

    douban_tv = fetch_douban_tv()
    print(f"  豆瓣电视: {len(douban_tv)} 条")

    douyin_movies = fetch_douyin_movies()
    print(f"  抖音电影: {len(douyin_movies)} 条")

    douyin_tv = fetch_douyin_tv()
    print(f"  抖音剧集: {len(douyin_tv)} 条")

    baidu_movies = fetch_baidu_movies()
    print(f"  百度电影: {len(baidu_movies)} 条")

    baidu_tv = fetch_baidu_tv()
    print(f"  百度电视: {len(baidu_tv)} 条")

    def make_tab_data(key, title, items, platform_name):
        if not items:
            return {
                "key": key,
                "title": title,
                "count": 0,
                "items": [],
                "error": f"{platform_name}数据抓取失败，本时段暂无数据"
            }
        return {
            "key": key,
            "title": title,
            "count": len(items),
            "items": items
        }

    result = {
        "update_time": get_timestamp(),
        "weibo": {
            "platform": "微博",
            "icon": "📱",
            "tabs": [
                make_tab_data("weibo_entertainment", "文娱热搜", weibo_entertainment, "微博"),
                make_tab_data("weibo_tv", "剧集热度", weibo_tv, "微博"),
                make_tab_data("weibo_movie", "电影热度", weibo_movie, "微博"),
            ]
        },
        "douban": {
            "platform": "豆瓣",
            "icon": "📖",
            "tabs": [
                make_tab_data("douban_movie", "电影榜", douban_movies, "豆瓣"),
                make_tab_data("douban_tv", "电视榜", douban_tv, "豆瓣"),
            ]
        },
        "douyin": {
            "platform": "抖音",
            "icon": "🎵",
            "tabs": [
                make_tab_data("douyin_movie", "院线电影", douyin_movies, "抖音"),
                make_tab_data("douyin_tv", "剧集", douyin_tv, "抖音"),
            ]
        },
        "baidu": {
            "platform": "百度",
            "icon": "🔍",
            "tabs": [
                make_tab_data("baidu_movie", "电影榜", baidu_movies, "百度"),
                make_tab_data("baidu_tv", "电视剧榜", baidu_tv, "百度"),
            ]
        }
    }

    save_json(result, OUTPUT_FILE)
    print(f"  数据已保存到 {OUTPUT_FILE}")

    history = load_json(HISTORY_FILE, {"history": []})
    history["history"].append({
        "time": get_timestamp(),
        "hour_key": get_hour_key(),
        "weibo_top3": [e["title"] for e in weibo_entertainment[:3]] if weibo_entertainment else [],
        "douban_movie_top3": [m["title"] for m in douban_movies[:3]] if douban_movies else [],
        "douyin_movie_top3": [m["title"] for m in douyin_movies[:3]] if douyin_movies else [],
        "baidu_movie_top3": [m["title"] for m in baidu_movies[:3]] if baidu_movies else [],
    })
    if len(history["history"]) > 72:
        history["history"] = history["history"][-72:]
    save_json(history, HISTORY_FILE)

    print(f"[{get_timestamp()}] 采集完成！")

if __name__ == "__main__":
    main()
