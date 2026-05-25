#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文娱榜单数据抓取脚本
支持来源：微博、抖音、百度、哔哩哔哩、豆瓣（通过 tophub.today 聚合）
抓取失败返回空数据，不保留历史缓存
"""

import requests
import json
import time
import os
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# 北京时区
BEIJING_TZ = timezone(timedelta(hours=8))

# 榜单配置
SOURCES = {
    "weibo_entertainment": {
        "name": "微博·文娱榜",
        "url": "https://tophub.today/n/3QeLwJEd7k",
        "category": "微博",
        "icon": "🔥",
        "color": "#E6162D"
    },
    "douyin_entertainment": {
        "name": "抖音·娱乐榜",
        "url": "https://tophub.today/n/2me33NBewj",
        "category": "抖音",
        "icon": "🎵",
        "color": "#000000"
    },
    "douyin_star": {
        "name": "抖音·明星榜",
        "url": "https://tophub.today/n/RrvWy7Re5z",
        "category": "抖音",
        "icon": "⭐",
        "color": "#000000"
    },
    "baidu_movie": {
        "name": "百度·电影榜",
        "url": "https://tophub.today/n/4KvxRL1ekx",
        "category": "百度",
        "icon": "🎬",
        "color": "#2932E1"
    },
    "baidu_tv": {
        "name": "百度·电视剧榜",
        "url": "https://tophub.today/n/ENeYp23dY4",
        "category": "百度",
        "icon": "📺",
        "color": "#2932E1"
    },
    "bilibili_movie": {
        "name": "哔哩哔哩·影视榜",
        "url": "https://tophub.today/n/MZd77ypdrO",
        "category": "哔哩哔哩",
        "icon": "📽️",
        "color": "#FB7299"
    },
    "bilibili_entertainment": {
        "name": "哔哩哔哩·娱乐榜",
        "url": "https://tophub.today/n/YKd67qneaP",
        "category": "哔哩哔哩",
        "icon": "🎮",
        "color": "#FB7299"
    },
    "douban_new": {
        "name": "豆瓣·新片榜",
        "url": "https://tophub.today/n/mDOvnyBoEB",
        "category": "豆瓣",
        "icon": "🆕",
        "color": "#007722"
    },
    "douban_nowplaying": {
        "name": "豆瓣·正在上映",
        "url": "https://tophub.today/n/m4ejbjyexE",
        "category": "豆瓣",
        "icon": "🎟️",
        "color": "#007722"
    },
    "douban_hot_tv": {
        "name": "豆瓣·热门剧集",
        "url": "https://tophub.today/n/nBe0JLBv37",
        "category": "豆瓣",
        "icon": "📺",
        "color": "#007722"
    }
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://tophub.today/",
    "Connection": "keep-alive",
}


def fetch_list(source_key, source_info):
    """抓取单个榜单，失败返回空数据"""
    url = source_info["url"]
    items = []
    error = None

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        response.encoding = "utf-8"
        html = response.text

        soup = BeautifulSoup(html, "html.parser")

        # 策略1: 标准 table 结构
        rows = soup.select("table.table tbody tr")

        # 策略2: 通用 tbody tr
        if not rows:
            rows = soup.select("tbody tr")

        # 策略3: cc-cd 卡片结构（部分页面使用）
        if not rows:
            cards = soup.select(".cc-cd")
            for idx, card in enumerate(cards[:50], 1):
                try:
                    a_tag = card.find("a")
                    if not a_tag:
                        continue
                    title = a_tag.get_text(strip=True)
                    link = a_tag.get("href", "")
                    heat_elem = card.select_one(".heat, .num, td:last-child")
                    heat = heat_elem.get_text(strip=True) if heat_elem else ""

                    if title and len(title) > 1:
                        items.append({
                            "rank": idx,
                            "title": title,
                            "heat": heat,
                            "url": link if link.startswith("http") else ("https://tophub.today" + link if link else "")
                        })
                except Exception:
                    continue

        # 策略4: 通用 tr 解析
        if not rows and not items:
            rows = soup.select("tr")

        # 解析 table 行
        for idx, row in enumerate(rows[:50], 1):
            try:
                tds = row.find_all("td")
                if len(tds) >= 2:
                    # 提取排名
                    rank_text = tds[0].get_text(strip=True)
                    rank = int(rank_text) if rank_text.isdigit() else idx

                    # 提取标题和链接
                    title_td = tds[1]
                    a_tag = title_td.find("a")
                    if a_tag:
                        title = a_tag.get_text(strip=True)
                        link = a_tag.get("href", "")
                    else:
                        title = title_td.get_text(strip=True)
                        link = ""

                    # 提取热度（最后一列或第三列）
                    heat = ""
                    if len(tds) >= 3:
                        heat = tds[-1].get_text(strip=True)

                    # 清理链接
                    if link and not link.startswith("http"):
                        link = "https://tophub.today" + link

                    if title and len(title) > 1:
                        items.append({
                            "rank": rank,
                            "title": title,
                            "heat": heat,
                            "url": link
                        })
            except Exception:
                continue

        # 策略5: 如果以上都失败，尝试正则兜底
        if not items:
            pattern = r'<a[^>]*href="([^"]*)"[^>]*>([^<]{2,50})</a>'
            matches = re.findall(pattern, html)
            seen = set()
            for link, title in matches[:50]:
                title = title.strip()
                if title and title not in seen and not title.startswith(("<", "script", "function")):
                    seen.add(title)
                    items.append({
                        "rank": len(items) + 1,
                        "title": title,
                        "heat": "",
                        "url": link if link.startswith("http") else ("https://tophub.today" + link if link else "")
                    })

        if not items:
            error = "页面解析未获取到数据，结构可能已变更"

    except requests.exceptions.Timeout:
        error = "请求超时，目标站点响应缓慢"
    except requests.exceptions.HTTPError as e:
        error = f"HTTP错误: {e.response.status_code}"
    except requests.exceptions.RequestException as e:
        error = f"网络请求失败: {str(e)}"
    except Exception as e:
        error = f"解析异常: {str(e)}"

    return {
        "source_key": source_key,
        "source_name": source_info["name"],
        "category": source_info["category"],
        "icon": source_info["icon"],
        "color": source_info["color"],
        "items": items,
        "error": error,
        "item_count": len(items),
        "update_time": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    }


def main():
    print(f"[{datetime.now(BEIJING_TZ).strftime('%H:%M:%S')}] 开始抓取文娱榜单...")

    data = {
        "update_time": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "sources": {}
    }

    success_count = 0
    fail_count = 0

    for key, info in SOURCES.items():
        print(f"  → 正在抓取: {info['name']} ...", end=" ")
        result = fetch_list(key, info)
        data["sources"][key] = result

        if result["error"]:
            print(f"❌ 失败 ({result['error'][:30]})")
            fail_count += 1
        else:
            print(f"✅ 成功 ({result['item_count']}条)")
            success_count += 1

        time.sleep(1.5)  # 礼貌延迟，避免请求过快

    # 确保目录存在
    os.makedirs("data", exist_ok=True)

    # 写入数据
    output_path = "data/entertainment_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[{datetime.now(BEIJING_TZ).strftime('%H:%M:%S')}] 抓取完成")
    print(f"  成功: {success_count} / 失败: {fail_count}")
    print(f"  数据已保存至: {output_path}")


if __name__ == "__main__":
    main()
