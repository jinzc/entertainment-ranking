#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文娱榜单数据抓取脚本 - 改进版
策略：优先抓取 tophub.today，检测到假数据时自动切换到原始平台直接抓取
"""

import requests
import json
import time
import re
import os
import sys
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

BEIJING_TZ = timezone(timedelta(hours=8))

# ============ 假数据检测关键词 ============
FAKE_KEYWORDS = ["报刊", "设计", "校务", "政务", "专栏", "苹果", "公众号", "小部件", "自定义分组"]

def is_fake_data(items):
    """检测 tophub 是否返回了虚假/导航数据"""
    if not items or len(items) < 3:
        return False
    fake_count = sum(
        1 for item in items[:5]
        if any(kw in item.get("title", "") for kw in FAKE_KEYWORDS)
    )
    return fake_count >= 2


def clean_text(text):
    """清理文本"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


# ============ tophub.today 抓取器 ============
class TopHubSession:
    """带会话管理的 tophub 请求器"""
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })
        self._initialized = False

    def init(self):
        """先访问首页建立会话和 cookie"""
        if self._initialized:
            return
        try:
            resp = self.session.get("https://tophub.today/", timeout=15)
            print(f"    [tophub] 首页状态: {resp.status_code}, 建立会话...")
            time.sleep(1.5)
            self._initialized = True
        except Exception as e:
            print(f"    [tophub] 首页访问失败: {e}")

    def fetch(self, url):
        self.init()
        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            return None, str(e)
        return resp.text, None


def parse_tophub(html, source_name):
    """精确解析 tophub.today 页面"""
    items = []
    if not html:
        return items

    soup = BeautifulSoup(html, "html.parser")

    # 策略1：精确匹配 td.al（参考 CSDN 成功案例）
    al_tds = soup.select("td.al")
    if al_tds:
        print(f"    [tophub] 使用 td.al 精确匹配，找到 {len(al_tds)} 个")
        for idx, td in enumerate(al_tds[:50], 1):
            a_tag = td.find("a", href=True)
            if not a_tag:
                continue
            title = clean_text(a_tag.get_text())
            link = a_tag.get("href", "")

            # 获取热度：找父级 tr 中的所有 td，取非标题/非排名的那一列
            heat = ""
            parent_tr = td.find_parent("tr")
            if parent_tr:
                all_tds = parent_tr.find_all("td")
                for t in all_tds:
                    txt = clean_text(t.get_text())
                    # 排除排名数字和标题本身
                    if txt and txt != title and not txt.isdigit() and len(txt) > 1:
                        # 热度通常包含数字和文字（如 "123万"、"12345"）
                        if re.search(r'[0-9万亿]', txt):
                            heat = txt
                            break
                    elif txt.isdigit() and int(txt) > 100:
                        heat = txt

            if title and len(title) > 1 and title not in ["更多", "下一页", "上一页"]:
                items.append({
                    "rank": idx,
                    "title": title,
                    "heat": heat,
                    "url": link if link.startswith("http") else f"https://tophub.today{link}"
                })

    # 策略2：标准 table 结构
    if not items:
        table = soup.select_one("table.table") or soup.select_one("table")
        if table:
            rows = table.select("tbody tr")
            print(f"    [tophub] 使用标准 table 匹配，找到 {len(rows)} 行")
            for idx, row in enumerate(rows[:50], 1):
                tds = row.find_all("td")
                if len(tds) >= 2:
                    rank_text = clean_text(tds[0].get_text())
                    try:
                        rank = int(rank_text)
                    except:
                        rank = idx

                    title_td = tds[1]
                    a_tag = title_td.find("a", href=True)
                    if a_tag:
                        title = clean_text(a_tag.get_text())
                        link = a_tag.get("href", "")
                    else:
                        title = clean_text(title_td.get_text())
                        link = ""

                    heat = clean_text(tds[-1].get_text()) if len(tds) >= 3 else ""

                    if title and len(title) > 1:
                        items.append({
                            "rank": rank,
                            "title": title,
                            "heat": heat,
                            "url": link if link.startswith("http") else f"https://tophub.today{link}"
                        })

    # 策略3：cc-cd 卡片
    if not items:
        cards = soup.select(".cc-cd")
        if cards:
            print(f"    [tophub] 使用 cc-cd 卡片匹配，找到 {len(cards)} 个")
            for idx, card in enumerate(cards[:50], 1):
                a_tag = card.find("a", href=True)
                if a_tag:
                    title = clean_text(a_tag.get_text())
                    link = a_tag.get("href", "")
                    if title and len(title) > 1:
                        items.append({
                            "rank": idx,
                            "title": title,
                            "heat": "",
                            "url": link if link.startswith("http") else f"https://tophub.today{link}"
                        })

    return items


# ============ 原始平台直接抓取 ============

def fetch_weibo_entertainment():
    """直接抓取微博文娱榜"""
    items = []
    error = None
    try:
        url = "https://s.weibo.com/top/summary?cate=entrank"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://s.weibo.com/",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 微博文娱榜结构
        rows = soup.select("#pl_top_realtimehot tbody tr") or soup.select(".ranklist tbody tr") or soup.select("table tbody tr")
        for row in rows[:50]:
            tds = row.find_all("td")
            if len(tds) >= 2:
                rank = clean_text(tds[0].get_text())
                a_tag = tds[1].find("a")
                if a_tag:
                    title = clean_text(a_tag.get_text())
                    link = a_tag.get("href", "")
                    heat = clean_text(tds[2].get_text()) if len(tds) >= 3 else ""
                    items.append({
                        "rank": rank if rank else len(items)+1,
                        "title": title,
                        "heat": heat,
                        "url": f"https://s.weibo.com{link}" if link and not link.startswith("http") else link
                    })
        print(f"    [weibo] 直接抓取成功: {len(items)} 条")
    except Exception as e:
        error = f"微博直接抓取失败: {e}"
    return items, error


def fetch_baidu_board(tab):
    """直接抓取百度热搜榜（电影/电视剧）"""
    items = []
    error = None
    try:
        # 百度热搜 API
        url = f"https://top.baidu.com/api/board?platform=wise&tab={tab}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"https://top.baidu.com/board?tab={tab}",
            "Accept": "application/json, text/plain, */*",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()

        if data.get("data") and data["data"].get("cards"):
            card = data["data"]["cards"][0]
            for idx, item in enumerate(card.get("content", [])[:50], 1):
                title = item.get("query", "")
                heat = str(item.get("hotScore", ""))
                url_link = item.get("url", "")
                if title:
                    items.append({
                        "rank": idx,
                        "title": title,
                        "heat": heat,
                        "url": url_link
                    })
        print(f"    [baidu] tab={tab} 直接抓取成功: {len(items)} 条")
    except Exception as e:
        error = f"百度直接抓取失败: {e}"
    return items, error


def fetch_bilibili_search_hot():
    """直接抓取B站热搜"""
    items = []
    error = None
    try:
        url = "https://api.bilibili.com/x/web-interface/search/square"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://search.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()

        if data.get("data") and data["data"].get("trending"):
            hot_list = data["data"]["trending"].get("list", [])
            for idx, item in enumerate(hot_list[:50], 1):
                keyword = item.get("keyword", "")
                show_name = item.get("show_name", keyword)
                url_link = item.get("url", "")
                if show_name:
                    items.append({
                        "rank": idx,
                        "title": show_name,
                        "heat": "",
                        "url": url_link if url_link else f"https://search.bilibili.com/all?keyword={keyword}"
                    })
        print(f"    [bilibili] 热搜直接抓取成功: {len(items)} 条")
    except Exception as e:
        error = f"B站直接抓取失败: {e}"
    return items, error


def fetch_douban_chart(chart_type):
    """直接抓取豆瓣榜单"""
    items = []
    error = None
    try:
        if chart_type == "new":
            url = "https://movie.douban.com/chart"
        elif chart_type == "nowplaying":
            url = "https://movie.douban.com/cinema/nowplaying/"
        elif chart_type == "tv":
            # 豆瓣热门剧集使用 API
            url = "https://movie.douban.com/j/search_subjects?type=tv&tag=%E7%83%AD%E9%97%A8&sort=recommend&page_limit=50&page_start=0"
        else:
            return items, "未知豆瓣榜单类型"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://movie.douban.com/",
        }

        if chart_type == "tv":
            # TV 使用 JSON API
            resp = requests.get(url, headers=headers, timeout=15)
            data = resp.json()
            for idx, item in enumerate(data.get("subjects", [])[:50], 1):
                title = item.get("title", "")
                rating = item.get("rate", "")
                link = item.get("url", "")
                if title:
                    items.append({
                        "rank": idx,
                        "title": title,
                        "heat": rating,
                        "url": link
                    })
        else:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            if chart_type == "new":
                # 新片榜
                rows = soup.select(".chart-dv-table tr") or soup.select("table tr")
                for idx, row in enumerate(rows[:50], 1):
                    if idx == 1:
                        continue  # 跳过表头
                    title_a = row.select_one(".pl2 a")
                    if title_a:
                        title = clean_text(title_a.get_text())
                        link = title_a.get("href", "")
                        rating = ""
                        rating_span = row.select_one(".rating_nums")
                        if rating_span:
                            rating = rating_span.get_text(strip=True)
                        items.append({
                            "rank": idx-1,
                            "title": title,
                            "heat": rating,
                            "url": link
                        })

            elif chart_type == "nowplaying":
                # 正在上映
                movies = soup.select("#nowplaying .list-item") or soup.select(".list-item")
                for idx, movie in enumerate(movies[:50], 1):
                    title_a = movie.select_one(".stitle a") or movie.select_one("a")
                    if title_a:
                        title = clean_text(title_a.get_text())
                        link = title_a.get("href", "")
                        rating = ""
                        rate_tag = movie.select_one(".subject-rate") or movie.select_one(".rating_nums")
                        if rate_tag:
                            rating = rate_tag.get_text(strip=True)
                        items.append({
                            "rank": idx,
                            "title": title,
                            "heat": rating,
                            "url": f"https://movie.douban.com{link}" if link and not link.startswith("http") else link
                        })

        print(f"    [douban] chart={chart_type} 直接抓取成功: {len(items)} 条")
    except Exception as e:
        error = f"豆瓣直接抓取失败: {e}"
    return items, error


def fetch_douyin_hot():
    """尝试直接抓取抖音热榜"""
    items = []
    error = None
    try:
        # 抖音网页版热榜
        url = "https://www.douyin.com/hot"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.douyin.com/",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 抖音热榜页面结构（可能变化）
        hot_items = soup.select("[data-e2e='hot-list-item']") or soup.select(".hot-list-item") or soup.select(".challenge-item")

        if not hot_items:
            # 尝试通用 a 标签匹配，限制在主要内容区
            main_area = soup.select_one("main") or soup.select_one("[class*='hot']") or soup.body
            if main_area:
                links = main_area.find_all("a", href=True)
                seen = set()
                for a in links[:50]:
                    title = clean_text(a.get_text())
                    if title and title not in seen and len(title) > 1 and not any(kw in title for kw in ["登录", "注册", "关于", "帮助"]):
                        seen.add(title)
                        items.append({
                            "rank": len(items)+1,
                            "title": title,
                            "heat": "",
                            "url": a.get("href", "") if a.get("href", "").startswith("http") else f"https://www.douyin.com{a.get('href', '')}"
                        })
        else:
            for idx, item in enumerate(hot_items[:50], 1):
                a_tag = item.find("a", href=True)
                if a_tag:
                    title = clean_text(a_tag.get_text())
                    link = a_tag.get("href", "")
                    if title:
                        items.append({
                            "rank": idx,
                            "title": title,
                            "heat": "",
                            "url": link if link.startswith("http") else f"https://www.douyin.com{link}"
                        })

        print(f"    [douyin] 直接抓取成功: {len(items)} 条")
    except Exception as e:
        error = f"抖音直接抓取失败: {e}"
    return items, error


# ============ 榜单配置与抓取路由 ============

SOURCES = {
    "weibo_entertainment": {
        "name": "微博·文娱榜",
        "category": "微博",
        "icon": "🔥",
        "color": "#E6162D",
        "tophub_url": "https://tophub.today/n/3QeLwJEd7k",
        "fallback": fetch_weibo_entertainment,
    },
    "douyin_entertainment": {
        "name": "抖音·娱乐榜",
        "category": "抖音",
        "icon": "🎵",
        "color": "#000000",
        "tophub_url": "https://tophub.today/n/2me33NBewj",
        "fallback": fetch_douyin_hot,
    },
    "douyin_star": {
        "name": "抖音·明星榜",
        "category": "抖音",
        "icon": "⭐",
        "color": "#000000",
        "tophub_url": "https://tophub.today/n/RrvWy7Re5z",
        "fallback": fetch_douyin_hot,
    },
    "baidu_movie": {
        "name": "百度·电影榜",
        "category": "百度",
        "icon": "🎬",
        "color": "#2932E1",
        "tophub_url": "https://tophub.today/n/4KvxRL1ekx",
        "fallback": lambda: fetch_baidu_board("movie"),
    },
    "baidu_tv": {
        "name": "百度·电视剧榜",
        "category": "百度",
        "icon": "📺",
        "color": "#2932E1",
        "tophub_url": "https://tophub.today/n/ENeYp23dY4",
        "fallback": lambda: fetch_baidu_board("teleplay"),
    },
    "bilibili_movie": {
        "name": "哔哩哔哩·影视榜",
        "category": "哔哩哔哩",
        "icon": "📽️",
        "color": "#FB7299",
        "tophub_url": "https://tophub.today/n/MZd77ypdrO",
        "fallback": fetch_bilibili_search_hot,
    },
    "bilibili_entertainment": {
        "name": "哔哩哔哩·娱乐榜",
        "category": "哔哩哔哩",
        "icon": "🎮",
        "color": "#FB7299",
        "tophub_url": "https://tophub.today/n/YKd67qneaP",
        "fallback": fetch_bilibili_search_hot,
    },
    "douban_new": {
        "name": "豆瓣·新片榜",
        "category": "豆瓣",
        "icon": "🆕",
        "color": "#007722",
        "tophub_url": "https://tophub.today/n/mDOvnyBoEB",
        "fallback": lambda: fetch_douban_chart("new"),
    },
    "douban_nowplaying": {
        "name": "豆瓣·正在上映",
        "category": "豆瓣",
        "icon": "🎟️",
        "color": "#007722",
        "tophub_url": "https://tophub.today/n/m4ejbjyexE",
        "fallback": lambda: fetch_douban_chart("nowplaying"),
    },
    "douban_hot_tv": {
        "name": "豆瓣·热门剧集",
        "category": "豆瓣",
        "icon": "📺",
        "color": "#007722",
        "tophub_url": "https://tophub.today/n/nBe0JLBv37",
        "fallback": lambda: fetch_douban_chart("tv"),
    },
}


def fetch_single_source(tophub_session, key, config):
    """抓取单个榜单：先 tophub，失败则 fallback 到原始平台"""
    print(f"\n  → [{config['name']}] 开始抓取...")

    items = []
    error = None
    source_used = "tophub"

    # ===== 第一步：尝试 tophub.today =====
    try:
        html, err = tophub_session.fetch(config["tophub_url"])
        if html:
            items = parse_tophub(html, config["name"])
            print(f"    [tophub] 解析到 {len(items)} 条")

            # 检测假数据
            if is_fake_data(items):
                print(f"    ⚠️ 检测到假数据（反爬拦截），切换到原始平台...")
                items = []
                error = "tophub返回虚假数据"
            elif len(items) == 0:
                print(f"    ⚠️ tophub 无数据，切换到原始平台...")
                error = "tophub无数据"
            else:
                print(f"    ✅ tophub 数据正常")
        else:
            print(f"    ⚠️ tophub 请求失败: {err}，切换到原始平台...")
            error = f"tophub请求失败: {err}"
    except Exception as e:
        print(f"    ⚠️ tophub 异常: {e}，切换到原始平台...")
        error = f"tophub异常: {e}"

    # ===== 第二步：fallback 到原始平台 =====
    if not items and config.get("fallback"):
        try:
            fb_items, fb_error = config["fallback"]()
            if fb_items and len(fb_items) > 0:
                items = fb_items
                source_used = "original"
                error = None
                print(f"    ✅ 原始平台抓取成功 ({len(items)} 条)")
            else:
                if fb_error:
                    error = fb_error
                print(f"    ❌ 原始平台也失败: {fb_error}")
        except Exception as e:
            print(f"    ❌ 原始平台异常: {e}")
            if error:
                error += f" | fallback异常: {e}"
            else:
                error = f"fallback异常: {e}"

    return {
        "source_key": key,
        "source_name": config["name"],
        "category": config["category"],
        "icon": config["icon"],
        "color": config["color"],
        "items": items,
        "error": error,
        "item_count": len(items),
        "source_used": source_used,
        "update_time": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    }


def main():
    print(f"[{datetime.now(BEIJING_TZ).strftime('%H:%M:%S')}] 开始抓取文娱榜单 (改进版)...")
    print("=" * 60)

    tophub_session = TopHubSession()
    data = {
        "update_time": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "sources": {}
    }

    success_count = 0
    fail_count = 0

    for key, config in SOURCES.items():
        result = fetch_single_source(tophub_session, key, config)
        data["sources"][key] = result

        if result["error"] or result["item_count"] == 0:
            fail_count += 1
            print(f"  ❌ 最终结果: 失败 - {result['error']}")
        else:
            success_count += 1
            print(f"  ✅ 最终结果: 成功 ({result['item_count']} 条, 来源: {result['source_used']})")

        time.sleep(2)  # 礼貌延迟

    print("\n" + "=" * 60)
    print(f"抓取完成: 成功 {success_count} / 失败 {fail_count}")

    # 写入数据
    os.makedirs("data", exist_ok=True)
    output_path = "data/entertainment_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"数据已保存至: {output_path}")

    # 如果有失败项，返回非零退出码（可选，用于 GitHub Actions 告警）
    if fail_count > 0:
        print(f"\n注意: {fail_count} 个榜单抓取失败，已记录错误信息")


if __name__ == "__main__":
    main()
