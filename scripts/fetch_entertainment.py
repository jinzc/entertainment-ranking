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
            return resp.text, None
        except Exception as e:
            return None, str(e)


def parse_tophub(html, source_name):
    """精确解析 tophub.today 页面"""
    items = []
    if not html:
        return items
    
    soup = BeautifulSoup(html, "html.parser")
    
    # 策略1：标准 table tbody tr（抖音等大部分榜单用这个结构）
    rows = soup.select("table tbody tr")
    if rows:
        print(f"    [tophub] table tbody tr 匹配到 {len(rows)} 行")
        for idx, row in enumerate(rows[:50], 1):
            tds = row.find_all("td")
            if len(tds) < 2:
                continue
            
            # 第0列：排名
            rank_text = clean_text(tds[0].get_text())
            try:
                rank = int(rank_text.rstrip('.'))  # 处理 "1." 这种格式
            except:
                rank = idx
            
            # 找到包含标题的 td（通常有 class="al" 且包含 a 标签）
            title_td = None
            for td in tds:
                if td.find("a", href=True):
                    title_td = td
                    break
            
            if not title_td:
                continue
            
            a_tag = title_td.find("a", href=True)
            title = clean_text(a_tag.get_text()) if a_tag else clean_text(title_td.get_text())
            link = a_tag.get("href", "") if a_tag else ""
            
            # 智能提取 author 和 heat
            # tophub 不同榜单结构不同：
            # 抖音：.item-desc=作者名, .item-extra=播放量
            # B站：.item-desc=播放量, .item-extra=重复标题
            author = ""
            heat = ""
            
            desc_div = title_td.select_one(".item-desc")
            extra_div = title_td.select_one(".item-extra")
            
            desc_text = clean_text(desc_div.get_text()) if desc_div else ""
            extra_text = clean_text(extra_div.get_text()) if extra_div else ""
            
            # 判断 desc 是播放量还是作者
            def is_heat_text(text):
                return bool(re.search(r'\d+\.?\d*[万亿]', text) or re.search(r'\d+次播放', text) or re.search(r'^\d+\.?\d*$', text))
            
            if desc_text:
                if is_heat_text(desc_text):
                    heat = desc_text
                else:
                    author = desc_text
            
            if extra_text:
                if is_heat_text(extra_text):
                    heat = extra_text
                elif extra_text != title and len(extra_text) < 30:
                    # 如果 author 还没找到，extra 可能是作者
                    if not author:
                        author = extra_text
            
            # 兜底：从 td 中其他 div 找遗漏的 author
            if not author:
                for div in title_td.find_all("div"):
                    div_text = clean_text(div.get_text())
                    if div_text and div_text != title and div_text != heat and len(div_text) < 30:
                        if not is_heat_text(div_text):
                            author = div_text
                            break
            
            # 兜底：从其他 td 找遗漏的 heat
            if not heat:
                for td in tds:
                    txt = clean_text(td.get_text())
                    if txt and txt != title and txt != author and is_heat_text(txt):
                        heat = txt
                        break
            
            if link and not link.startswith("http"):
                link = "https://tophub.today" + link
            
            if title and len(title) > 1:
                items.append({
                    "rank": rank,
                    "title": title,
                    "author": author,
                    "heat": heat,
                    "url": link
                })
                if idx <= 3:
                    print(f"    [tophub-debug] 提取: title='{title[:25]}' author='{author}' heat='{heat[:20]}'")
    
    # 策略2：td.al 精确匹配（备用）
    if not items:
        al_tds = soup.select("td.al")
        if al_tds:
            print(f"    [tophub] td.al 匹配到 {len(al_tds)} 个")
            for idx, td in enumerate(al_tds[:50], 1):
                a_tag = td.find("a", href=True)
                if not a_tag:
                    continue
                title = clean_text(a_tag.get_text())
                link = a_tag.get("href", "")
                
                author = ""
                heat = ""
                desc_div = td.select_one(".item-desc")
                extra_div = td.select_one(".item-extra")
                
                if desc_div:
                    desc_text = clean_text(desc_div.get_text())
                    if re.search(r'\d+\.?\d*[万亿]', desc_text) or re.search(r'\d+次播放', desc_text):
                        heat = desc_text
                    else:
                        author = desc_text
                
                if extra_div:
                    extra_text = clean_text(extra_div.get_text())
                    if re.search(r'\d+\.?\d*[万亿]', extra_text) or re.search(r'\d+次播放', extra_text):
                        heat = extra_text
                
                if title and len(title) > 1:
                    items.append({
                        "rank": idx,
                        "title": title,
                        "author": author,
                        "heat": heat,
                        "url": link if link.startswith("http") else f"https://tophub.today{link}"
                    })
    
    # 策略3：cc-cd 卡片（备用）
    if not items:
        cards = soup.select(".cc-cd")
        if cards:
            print(f"    [tophub] cc-cd 匹配到 {len(cards)} 个")
            for idx, card in enumerate(cards[:50], 1):
                a_tag = card.find("a", href=True)
                if a_tag:
                    title = clean_text(a_tag.get_text())
                    link = a_tag.get("href", "")
                    
                    author = ""
                    desc_div = card.select_one(".item-desc")
                    if desc_div:
                        desc_text = clean_text(desc_div.get_text())
                        if not re.search(r'\d+\.?\d*[万亿]', desc_text) and not re.search(r'\d+次播放', desc_text):
                            author = desc_text
                    
                    if title and len(title) > 1:
                        items.append({
                            "rank": idx,
                            "title": title,
                            "author": author,
                            "heat": "",
                            "url": link if link.startswith("http") else f"https://tophub.today{link}"
                        })
    
    print(f"    [tophub] 最终提取 {len(items)} 条")
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
                        "author": "",
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
                        "author": "",
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
                        "author": "",
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
                        "author": "",
                        "heat": rating,
                        "url": link
                    })
        else:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            
            if chart_type == "new":
                rows = soup.select(".chart-dv-table tr") or soup.select("table tr")
                for idx, row in enumerate(rows[:50], 1):
                    if idx == 1:
                        continue
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
                            "author": "",
                            "heat": rating,
                            "url": link
                        })
            
            elif chart_type == "nowplaying":
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
                            "author": "",
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
        
        hot_items = soup.select("[data-e2e='hot-list-item']") or soup.select(".hot-list-item") or soup.select(".challenge-item")
        
        if not hot_items:
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
                            "author": "",
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
                            "author": "",
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
        "color": "#DC2626",
        "tophub_url": "https://tophub.today/n/3QeLwJEd7k",
        "fallback": fetch_weibo_entertainment,
    },
    "douyin_entertainment": {
        "name": "抖音·娱乐榜",
        "category": "抖音",
        "icon": "🎵",
        "color": "#F59E0B",
        "tophub_url": "https://tophub.today/n/2me33NBewj",
        "fallback": fetch_douyin_hot,
    },
    "douyin_star": {
        "name": "抖音·明星榜",
        "category": "抖音",
        "icon": "⭐",
        "color": "#F59E0B",
        "tophub_url": "https://tophub.today/n/RrvWy7Re5z",
        "fallback": fetch_douyin_hot,
    },
    "baidu_movie": {
        "name": "百度·电影榜",
        "category": "百度",
        "icon": "🎬",
        "color": "#3B82F6",
        "tophub_url": "https://tophub.today/n/4KvxRL1ekx",
        "fallback": lambda: fetch_baidu_board("movie"),
    },
    "baidu_tv": {
        "name": "百度·电视剧榜",
        "category": "百度",
        "icon": "📺",
        "color": "#3B82F6",
        "tophub_url": "https://tophub.today/n/ENeYp23dY4",
        "fallback": lambda: fetch_baidu_board("teleplay"),
    },
    "bilibili_movie": {
        "name": "哔哩哔哩·影视榜",
        "category": "哔哩哔哩",
        "icon": "📽️",
        "color": "#EC4899",
        "tophub_url": "https://tophub.today/n/MZd77ypdrO",
        "fallback": fetch_bilibili_search_hot,
    },
    "bilibili_entertainment": {
        "name": "哔哩哔哩·娱乐榜",
        "category": "哔哩哔哩",
        "icon": "🎮",
        "color": "#EC4899",
        "tophub_url": "https://tophub.today/n/YKd67qneaP",
        "fallback": fetch_bilibili_search_hot,
    },
    "douban_new": {
        "name": "豆瓣·新片榜",
        "category": "豆瓣",
        "icon": "🆕",
        "color": "#10B981",
        "tophub_url": "https://tophub.today/n/mDOvnyBoEB",
        "fallback": lambda: fetch_douban_chart("new"),
    },
    "douban_nowplaying": {
        "name": "豆瓣·正在上映",
        "category": "豆瓣",
        "icon": "🎟️",
        "color": "#10B981",
        "tophub_url": "https://tophub.today/n/m4ejbjyexE",
        "fallback": lambda: fetch_douban_chart("nowplaying"),
    },
    "douban_hot_tv": {
        "name": "豆瓣·热门剧集",
        "category": "豆瓣",
        "icon": "📺",
        "color": "#10B981",
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
        
        time.sleep(2)
    
    print("\n" + "=" * 60)
    print(f"抓取完成: 成功 {success_count} / 失败 {fail_count}")
    
    os.makedirs("data", exist_ok=True)
    output_path = "data/entertainment_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"数据已保存至: {output_path}")
    
    if fail_count > 0:
        print(f"\n注意: {fail_count} 个榜单抓取失败，已记录错误信息")


if __name__ == "__main__":
    main()
