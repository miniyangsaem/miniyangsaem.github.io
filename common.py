# -*- coding: utf-8 -*-
"""허브 공용 도구: 설정 읽기, 글 저장소, 주소 정리, 요약 만들기, 측정 그룹 나누기."""
import hashlib
import html
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
POSTS_PATH = os.path.join(DATA_DIR, "posts.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 turf-hub")

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
NAVER_RE = re.compile(r"blog\.naver\.com/(?:PostView\.naver\?blogId=)?([A-Za-z0-9_-]+)(?:/|&logNo=)(\d+)")


def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def http_get(url, referer=None, timeout=25):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def naver_key(url):
    """네이버 글 주소(PC·모바일·PostView 형식)에서 (블로그ID, 글번호)를 꺼낸다."""
    m = NAVER_RE.search(url or "")
    return (m.group(1), m.group(2)) if m else None


def naver_mobile_url(blog_id, log_no):
    return "https://m.blog.naver.com/%s/%s" % (blog_id, log_no)


def post_id(source, url):
    """글마다 바뀌지 않는 고유 번호. 같은 글이 두 번 들어오지 않게 한다."""
    if source == "naver":
        k = naver_key(url)
        if k:
            return "naver:%s:%s" % k
    return "%s:%s" % (source, url.split("?")[0].rstrip("/"))


def clean_text(raw):
    text = html.unescape(TAG_RE.sub(" ", raw or ""))
    return SPACE_RE.sub(" ", text).strip()


def make_excerpt(raw, length):
    """원문을 짧게만 인용한다(중복문서 방지). 길면 자르고 … 를 붙인다."""
    text = clean_text(raw)
    if length <= 0:
        return ""
    if len(text) <= length:
        return text
    cut = text[:length]
    space = cut.rfind(" ")
    if space > length * 0.6:
        cut = cut[:space]
    return cut.rstrip(" ,.·") + "…"


def in_holdout(pid, percent):
    """측정용 비교군. 글 번호로 정해지므로 매일 실행해도 그룹이 바뀌지 않는다."""
    if percent <= 0:
        return False
    h = int(hashlib.sha256(pid.encode("utf-8")).hexdigest()[:8], 16)
    return (h % 100) < percent


def load_posts():
    return load_json(POSTS_PATH, {})


def merge_posts(store, incoming):
    """새 글은 추가하고, 이미 있는 글은 비어 있던 칸만 채운다. 한 번 들어온 글은 지우지 않는다."""
    added = 0
    for p in incoming:
        pid = p["id"]
        if pid not in store:
            store[pid] = p
            added += 1
            continue
        old = store[pid]
        for k, v in p.items():
            if v and not old.get(k):
                old[k] = v
    return added
