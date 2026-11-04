# -*- coding: utf-8 -*-
"""글 수집: 네이버 블로그 RSS(최근 약 50개), 티스토리 RSS, 그리고 처음 한 번 예전 글 전체.

사용법
  python scripts/fetch.py            # 매일 실행: RSS로 새 글만 추가
  python scripts/fetch.py --backfill # 처음 한 번: 네이버 예전 글 전체 목록까지 가져오기
"""
import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

import common

KST = dt.timezone(dt.timedelta(hours=9))
BAD_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')


def rss_date(text):
    try:
        return email.utils.parsedate_to_datetime(text).astimezone(KST).date().isoformat()
    except Exception:
        return ""


def parse_rss(xml_text, source, blog_label, excerpt_len):
    """RSS 글을 허브 글 카드 형식으로 바꾼다. 본문은 짧은 요약만 남긴다."""
    root = ET.fromstring(xml_text)
    posts = []
    for item in root.findall("./channel/item"):
        link = (item.findtext("link") or "").strip()
        title = common.clean_text(item.findtext("title") or "")
        if not link or not title:
            continue
        if source == "naver":
            key = common.naver_key(link)
            if not key:
                continue
            url = common.naver_mobile_url(*key)
        else:
            url = link.split("?")[0]
        posts.append({
            "id": common.post_id(source, url),
            "source": source,
            "blog": blog_label,
            "url": url,
            "title": title,
            "category": common.clean_text(item.findtext("category") or ""),
            "date": rss_date(item.findtext("pubDate") or ""),
            "excerpt": common.make_excerpt(item.findtext("description") or "", excerpt_len),
        })
    return posts


def list_date(text):
    """네이버 글 목록의 날짜("2026. 9. 4." 또는 "3시간 전")를 YYYY-MM-DD로."""
    m = re.match(r"\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", text or "")
    if m:
        return "%04d-%02d-%02d" % tuple(int(x) for x in m.groups())
    return dt.datetime.now(KST).date().isoformat()


def parse_naver_list(json_text, blog_id):
    """네이버 글 목록 응답에서 공개·검색허용 글만 고른다."""
    data = json.loads(BAD_ESCAPE.sub("", json_text))
    out = []
    for p in data.get("postList") or []:
        if str(p.get("openType")) != "2" or str(p.get("searchYn")).lower() != "true":
            continue
        url = common.naver_mobile_url(blog_id, p["logNo"])
        out.append({
            "id": common.post_id("naver", url),
            "source": "naver",
            "blog": blog_id,
            "url": url,
            "title": html.unescape(urllib.parse.unquote_plus(p.get("title", ""))).strip(),
            "category_no": str(p.get("categoryNo", "")),
            "date": list_date(p.get("addDate", "")),
            "excerpt": "",
        })
    return out


def fetch_naver_all(blog_id, max_pages=300):
    """예전 글 전체 목록. 네이버 공식 기능이 아니므로 실패해도 RSS 글은 그대로 둔다."""
    posts, seen = [], set()
    for page in range(1, max_pages + 1):
        url = ("https://blog.naver.com/PostTitleListAsync.naver?blogId=%s&viewdate="
               "&currentPage=%d&categoryNo=0&parentCategoryNo=&countPerPage=30" % (blog_id, page))
        chunk = parse_naver_list(common.http_get(url, referer="https://blog.naver.com/" + blog_id), blog_id)
        fresh = [p for p in chunk if p["id"] not in seen]
        if not fresh:
            break
        seen.update(p["id"] for p in fresh)
        posts.extend(fresh)
        time.sleep(0.5)
    return posts


CATEGORY_CACHE = os.path.join(common.DATA_DIR, "categories.json")
CATEGORY_NAME_RE = re.compile(r'categoryName\s*=\s*["\']([^"\']+)["\']')


def fetch_category_name(blog_id, log_no):
    """글 하나를 열어 그 글의 카테고리 이름을 읽는다(네이버 공식 기능 아님)."""
    page = common.http_get("https://blog.naver.com/PostView.naver?blogId=%s&logNo=%s" % (blog_id, log_no),
                           referer="https://blog.naver.com/" + blog_id)
    m = CATEGORY_NAME_RE.search(page)
    return urllib.parse.unquote_plus(m.group(1)).strip() if m else ""


def learn_categories(store, fetch_missing=True):
    """전체 목록에는 카테고리 번호만 있다. 이름을 채우는 순서:
    1) RSS에 함께 나온 글로 '번호 → 이름'을 배운다
    2) 그래도 모르는 번호는 그 카테고리 글 하나를 열어 이름을 읽는다(번호마다 한 번, 결과는 저장)"""
    names = {tuple(k.split("|", 1)): v for k, v in common.load_json(CATEGORY_CACHE, {}).items()}
    for p in store.values():
        if p.get("category_no") and p.get("category"):
            names[(p["blog"], p["category_no"])] = p["category"]
    missing = {}
    for p in store.values():
        key = (p.get("blog", ""), p.get("category_no", ""))
        if p.get("category_no") and key not in names:
            missing.setdefault(key, common.naver_key(p["url"])[1])
    looked_up = 0
    if fetch_missing:
        for (blog_id, cat_no), log_no in missing.items():
            try:
                name = fetch_category_name(blog_id, log_no)
            except Exception:
                name = ""
            if name:
                names[(blog_id, cat_no)] = name
                looked_up += 1
            time.sleep(0.4)
    for p in store.values():
        if p.get("category_no") and not p.get("category"):
            p["category"] = names.get((p["blog"], p["category_no"]), "")
    common.save_json(CATEGORY_CACHE, {"%s|%s" % k: v for k, v in names.items()})
    return looked_up, len(missing) - looked_up


def main(argv):
    cfg = common.load_config()
    store = common.load_posts()
    n = cfg.get("excerpt_length", 180)
    report = []

    for blog_id in cfg.get("naver_blog_ids", []):
        try:
            got = parse_rss(common.http_get("https://rss.blog.naver.com/%s.xml" % blog_id), "naver", blog_id, n)
            report.append("네이버 %s RSS: %d개, 새 글 %d개" % (blog_id, len(got), common.merge_posts(store, got)))
        except Exception as e:
            report.append("네이버 %s RSS 실패: %s" % (blog_id, e))
        if "--backfill" in argv:
            try:
                got = fetch_naver_all(blog_id)
                report.append("네이버 %s 전체 목록: %d개, 새 글 %d개" % (blog_id, len(got), common.merge_posts(store, got)))
            except Exception as e:
                report.append("네이버 %s 전체 목록 실패(RSS 글은 유지): %s" % (blog_id, e))

    for name in cfg.get("tistory_blogs", []):
        try:
            got = parse_rss(common.http_get("https://%s.tistory.com/rss" % name), "tistory", name, n)
            report.append("티스토리 %s RSS: %d개, 새 글 %d개" % (name, len(got), common.merge_posts(store, got)))
        except Exception as e:
            report.append("티스토리 %s RSS 실패: %s" % (name, e))

    found, failed = learn_categories(store)
    if found or failed:
        report.append("카테고리 이름 새로 찾음 %d개, 못 찾음 %d개" % (found, failed))
    common.save_json(common.POSTS_PATH, store)
    print("\n".join(report) or "설정에 블로그가 없습니다 (config.json 확인)")
    print("저장된 글 합계: %d개" % len(store))


if __name__ == "__main__":
    main(sys.argv[1:])
