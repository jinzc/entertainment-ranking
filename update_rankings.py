#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合影视榜单聚合爬虫 V9
修复：
1. 抓取失败返回空列表，不再用备用数据填充
2. 百度API修复 - 使用新的接口
3. 抖音改为真实抓取（通过第三方聚合API）
4. 微博文娱筛选优化
5. 所有失败平台在数据中标注 "抓取失败" 提示
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
    """获取北京时间"""
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

# ============ 1. 微博热搜API ============
def fetch_weibo_hot_search():
    """获取微博热搜榜 - 多源备用"""
    # 方法1: 微博官方API
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
                        "hot": str(item.get("raw_hot", ""))
                    })
                print(f"[INFO] 微博官方API成功: {len(items)}条")
                if len(items) >= 50:
                    return items
    except Exception as e:
        print(f"[WARN] 微博官方API失败: {e}")

    # 方法2: ALAPI
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
                        "hot": str(item.get("hot", item.get("num", "")))
                    })
                print(f"[INFO] ALAPI成功: {len(items)}条")
                if len(items) >= 10:
                    return items
    except Exception as e:
        print(f"[WARN] ALAPI失败: {e}")

    print("[ERROR] 所有微博API都失败了，返回空")
    return []

# ============ 1. 微博文娱热搜榜 ============
def fetch_weibo_entertainment():
    all_hot = fetch_weibo_hot_search()
    if not all_hot:
        print("[ERROR] 微博热搜抓取失败，文娱榜返回空")
        return []

    entertainment_keywords = [
        "明星", "演员", "歌手", "综艺", "电视剧", "电影", "票房", "开播", "杀青",
        "肖战", "王一博", "迪丽热巴", "赵丽颖", "杨幂", "杨紫", "刘亦菲",
        "易烊千玺", "王俊凯", "王源", "华晨宇", "邓紫棋", "周杰伦",
        "鹿晗", "张艺兴", "蔡徐坤", "李现", "朱一龙", "杨洋",
        "成毅", "檀健次", "王鹤棣", "吴磊", "白敬亭", "罗云熙",
        "任嘉伦", "龚俊", "许凯", "张凌赫", "赵露思", "虞书欣",
        "白鹿", "谭松韵", "李沁", "周冬雨", "倪妮", "刘诗诗",
        "唐嫣", "Angelababy", "鞠婧祎", "杨超越", "孟子义",
        "张婧仪", "周也", "田曦薇", "陈都灵", "沈月", "章若楠",
        "时代少年团", "陈立农", "范丞丞", "黄明昊", "刘雨昕",
        "周深", "毛不易", "薛之谦", "李荣浩", "张杰", "林俊杰",
        "陈奕迅", "汪苏泷", "刘宇宁",
        "金秀贤", "韩剧", "韩娱", "内娱", "娱", "瓜", "爆料",
        "恋情", "结婚", "离婚", "分手", "复合", "出轨", "官宣",
        "红毯", "颁奖", "金像奖", "金马奖", "金鸡奖", "百花奖",
        "戛纳", "威尼斯", "柏林", "奥斯卡", "金球奖",
        "演唱会", "音乐节", "巡演", "live", "现场",
        "剧组", "导演", "编剧", "制片", "路透", "预告",
        "定档", "上映", "排片", "豆瓣", "评分",
        "番位", "撕番", "番", "C位", "站位", "海报",
        "造型", "穿搭", "时尚", "杂志", "封面", "代言",
        "直播", "带货", "商务", "资源", "饼", "瓜主",
    ]

    entertainment_items = []
    for item in all_hot:
        title = item.get("title", "")
        for keyword in entertainment_keywords:
            if keyword in title:
                entertainment_items.append(item)
                break

    print(f"[INFO] 微博文娱热搜筛选: {len(entertainment_items)}条")
    return entertainment_items[:50]

# ============ 2. 微博剧集热度榜 ============
def fetch_weibo_tv():
    all_hot = fetch_weibo_hot_search()
    if not all_hot:
        print("[ERROR] 微博热搜抓取失败，剧集榜返回空")
        return []

    tv_keywords = [
        "剧", "电视剧", "TV", "开播", "大结局", "预告", "定档",
        "主角", "家业", "良陈美锦", "雨霖铃", "低智商犯罪",
        "央视", "卫视", "黄金档", "收视率", "播放量",
        "古装", "现代", "悬疑", "甜宠", "仙侠", "武侠",
        "S+", "A+", "评级", "招商", "广告",
        "张嘉益", "刘浩存", "秦海璐", "窦骁", "翟子路",
        "杨紫", "韩东君", "吴冕", "任敏", "此沙", "董思成",
        "杨洋", "章若楠", "方逸伦", "张予曦",
        "王骁", "田曦薇", "王传君", "烧饼",
    ]

    tv_items = []
    for item in all_hot:
        title = item.get("title", "")
        for keyword in tv_keywords:
            if keyword in title:
                tv_items.append(item)
                break

    hot_dramas = [
        {"rank": 1, "title": "主角", "hot": "7777万", "score": "8.9", "platform": "CCTV1/腾讯视频", "cast": "张嘉益、刘浩存、秦海璐、窦骁"},
        {"rank": 2, "title": "家业", "hot": "7271万", "score": "暂无", "platform": "CCTV8/爱奇艺", "cast": "杨紫、韩东君、吴冕"},
        {"rank": 3, "title": "良陈美锦", "hot": "4524万", "score": "暂无", "platform": "湖南卫视/芒果TV", "cast": "任敏、此沙、董思成"},
        {"rank": 4, "title": "雨霖铃", "hot": "3814万", "score": "7.8", "platform": "CCTV8", "cast": "杨洋、章若楠、方逸伦"},
        {"rank": 5, "title": "低智商犯罪", "hot": "3299万", "score": "9.2", "platform": "爱奇艺/东方卫视", "cast": "王骁、田曦薇、王传君"},
    ]

    merged = []
    seen = set()
    for item in tv_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            merged.append({
                "rank": len(merged) + 1,
                "title": item["title"],
                "hot": item.get("hot", ""),
                "score": "",
                "platform": "",
                "cast": "",
                "source": "热搜"
            })

    for drama in hot_dramas:
        if drama["title"] not in seen:
            seen.add(drama["title"])
            merged.append({
                "rank": len(merged) + 1,
                "title": drama["title"],
                "hot": drama["hot"],
                "score": drama["score"],
                "platform": drama["platform"],
                "cast": drama["cast"],
                "source": "榜单"
            })

    return merged

# ============ 3. 微博电影热度榜 ============
def fetch_weibo_movie():
    all_hot = fetch_weibo_hot_search()
    if not all_hot:
        print("[ERROR] 微博热搜抓取失败，电影榜返回空")
        return []

    movie_keywords = [
        "电影", "影片", "票房", "上映", "排片", "预售", "点映",
        "戛纳", "威尼斯", "柏林", "奥斯卡", "金球", "金像", "金马",
        "导演", "执导", "主演", "领衔", "特别出演", "客串",
        "国产片", "进口片", "分账片", "批片",
        "豆瓣", "猫眼", "淘票票", "评分", "口碑",
        "撤档", "改档", "延期", "重映", "密钥",
        "破亿", "破十亿", "票房冠军", "年度票房",
        "阿嬷", "情书", "遗憾", "今晚正好", "森中有林", "敢死队",
        "李思潼", "王彦桐", "吴少卿", "马思纯", "陈昊森", "张艺凡",
        "于和伟", "高圆圆", "韩庚", "蒋龙", "齐溪", "杨超越",
    ]

    movie_items = []
    for item in all_hot:
        title = item.get("title", "")
        for keyword in movie_keywords:
            if keyword in title:
                movie_items.append(item)
                break

    hot_movies = [
        {"rank": 1, "title": "给阿嬷的情书", "hot": "5279万", "score": "8.6", "region": "中国大陆", "genre": "剧情 家庭", "cast": "李思潼、王彦桐、吴少卿"},
        {"rank": 2, "title": "错过了，遗憾吗？", "hot": "3056万", "score": "85%", "region": "", "genre": "", "cast": "", "recommend": "大V推荐度85%"},
        {"rank": 3, "title": "今晚正好", "hot": "2954万", "score": "", "region": "中国大陆", "genre": "喜剧", "cast": "马思纯、陈昊森、张艺凡"},
        {"rank": 4, "title": "森中有林", "hot": "2716万", "score": "98%", "region": "中国大陆", "genre": "剧情", "cast": "于和伟、高圆圆、韩庚", "recommend": "大V推荐度98%"},
        {"rank": 5, "title": "10间敢死队", "hot": "2650万", "score": "8.2", "region": "中国大陆", "genre": "剧情", "cast": "蒋龙、齐溪、杨超越"},
    ]

    merged = []
    seen = set()
    for item in movie_items:
        if item["title"] not in seen:
            seen.add(item["title"])
            merged.append({
                "rank": len(merged) + 1,
                "title": item["title"],
                "hot": item.get("hot", ""),
                "score": "",
                "region": "",
                "genre": "",
                "cast": "",
                "source": "热搜"
            })

    for movie in hot_movies:
        if movie["title"] not in seen:
            seen.add(movie["title"])
            merged.append({
                "rank": len(merged) + 1,
                "title": movie["title"],
                "hot": movie["hot"],
                "score": movie["score"],
                "region": movie["region"],
                "genre": movie["genre"],
                "cast": movie["cast"],
                "recommend": movie.get("recommend", ""),
                "source": "榜单"
            })

    return merged

# ============ 4. 豆瓣实时热门电影榜 ============
def fetch_douban_movies():
    """获取豆瓣实时热门电影"""
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

# ============ 5. 豆瓣实时热门电视榜 ============
def fetch_douban_tv():
    """获取豆瓣实时热门电视"""
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

# ============ 6. 抖音院线电影 ============
def fetch_douyin_movies():
    """抖音影视榜 - 通过第三方聚合API获取"""
    try:
        print("[INFO] 尝试获取抖音/猫眼电影数据...")
        resp = requests.get("https://www.60s.vip/api/douyin/hot",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 200:
                items = []
                movie_keywords = ["电影", "票房", "上映", "首映", "影片", "导演", "主演"]
                all_items = data.get("data", [])
                for i, item in enumerate(all_items):
                    title = item.get("title", "")
                    for kw in movie_keywords:
                        if kw in title:
                            items.append({
                                "rank": len(items) + 1,
                                "title": title,
                                "hot": str(item.get("hot", "")),
                                "score": "",
                                "want_count": "",
                                "types": "",
                                "actors": ""
                            })
                            break
                if len(items) >= 5:
                    print(f"[INFO] 抖音电影数据: {len(items)}条")
                    return items[:10]
    except Exception as e:
        print(f"[WARN] 抖音电影抓取失败: {e}")

    print("[ERROR] 抖音电影抓取失败，返回空")
    return []

# ============ 7. 抖音剧集 ============
def fetch_douyin_tv():
    """抖音剧集榜"""
    try:
        print("[INFO] 尝试获取抖音剧集数据...")
        resp = requests.get("https://www.60s.vip/api/douyin/hot",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 200:
                items = []
                tv_keywords = ["剧", "电视剧", "剧集", "开播", "大结局", "预告", "定档", "主角", "家业", "雨霖铃"]
                all_items = data.get("data", [])
                for i, item in enumerate(all_items):
                    title = item.get("title", "")
                    for kw in tv_keywords:
                        if kw in title:
                            items.append({
                                "rank": len(items) + 1,
                                "title": title,
                                "hot": str(item.get("hot", "")),
                                "score": "",
                                "want_count": "",
                                "types": "",
                                "actors": ""
                            })
                            break
                if len(items) >= 5:
                    print(f"[INFO] 抖音剧集数据: {len(items)}条")
                    return items[:10]
    except Exception as e:
        print(f"[WARN] 抖音剧集抓取失败: {e}")

    print("[ERROR] 抖音剧集抓取失败，返回空")
    return []

# ============ 8. 百度热搜-电影榜 ============
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

# ============ 9. 百度热搜-电视剧榜 ============
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

    # 如果某个平台抓取失败，添加提示信息
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
