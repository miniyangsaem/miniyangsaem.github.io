# -*- coding: utf-8 -*-
"""허브 페이지 만들기: 홈·카테고리·월별 목록, 사이트맵, robots.txt, 측정표.

글별 페이지는 만들지 않는다(얇은 대량 페이지 방지). 결과는 _site/ 폴더에 생긴다.
사용법: python scripts/build.py [--today YYYY-MM-DD]
"""
import csv
import datetime as dt
import hashlib
import html
import json
import os
import shutil
import sys
import urllib.parse
from collections import defaultdict

import common

OUT = os.path.join(common.ROOT, "_site")
KST = dt.timezone(dt.timedelta(hours=9))
SOURCE_NAMES = {"naver": "네이버 블로그", "tistory": "티스토리"}
e = html.escape


def today_kst(argv):
    if "--today" in argv:
        return dt.date.fromisoformat(argv[argv.index("--today") + 1])
    return dt.datetime.now(KST).date()


def slug_for(category, cfg):
    if not category:
        return "etc"
    mapped = cfg.get("category_slugs", {}).get(category)
    if mapped:
        return mapped
    return "c-" + hashlib.sha1(category.encode("utf-8")).hexdigest()[:6]


def pinned_post_ids(cfg):
    ids = []
    for u in cfg.get("featured", {}).get("pinned_urls", []):
        key = common.naver_key(u)
        ids.append(common.post_id("naver", common.naver_mobile_url(*key)) if key
                   else common.post_id("tistory", u))
    return ids


def is_holdout(p, cfg, pinned):
    """비교군 여부. 직접 고정한 대표 글은 항상 허브에 싣는다."""
    return p["id"] not in pinned and common.in_holdout(p["id"], cfg.get("measurement", {}).get("holdout_percent", 0))


def pick_featured(posts, cfg, state, today):
    """대표 글: 고정 글 + 하루 한 번 돌아가며 노출(키워드 든 글, 오래 안 나온 글 먼저)."""
    fc = cfg.get("featured", {})
    count = fc.get("count", 7)
    if state.get("featured_date") == today.isoformat():
        by_id = {p["id"]: p for p in posts}
        kept = [by_id[i] for i in state.get("featured_ids", []) if i in by_id]
        if kept:
            return kept
    pinned_ids = pinned_post_ids(cfg)
    by_id = {p["id"]: p for p in posts}
    pinned = [by_id[i] for i in pinned_ids if i in by_id]
    pinned_set = {p["id"] for p in pinned}
    cutoff = (today - dt.timedelta(days=fc.get("min_age_days", 30))).isoformat()
    pool = [p for p in posts if p["id"] not in pinned_set and p.get("date", "") <= cutoff] or \
           [p for p in posts if p["id"] not in pinned_set]
    words = fc.get("keywords", [])
    history = state.setdefault("featured_history", {})

    def score(p):
        has_kw = any(w in p["title"] for w in words)
        return (0 if has_kw else 1, history.get(p["id"], "0000-00-00"), p.get("date", ""))

    chosen = pinned[:count] + sorted(pool, key=score)[:max(0, count - len(pinned))]
    for p in chosen:
        history[p["id"]] = today.isoformat()
    state["featured_date"] = today.isoformat()
    state["featured_ids"] = [p["id"] for p in chosen]
    return chosen


class Site:
    def __init__(self, cfg):
        self.cfg = cfg
        self.url = cfg["site_url"].rstrip("/")
        self.base = urllib.parse.urlparse(self.url).path.rstrip("/")
        self.pages = []  # (경로, 최신 날짜) — 사이트맵용

    def href(self, path):
        return self.base + path

    def card(self, p):
        meta = " · ".join(x for x in [p.get("date", ""), SOURCE_NAMES.get(p["source"], p["source"]),
                                       p.get("category", "")] if x)
        excerpt = '<p class="ex">%s</p>' % e(p["excerpt"]) if p.get("excerpt") else ""
        return ('<li class="card"><div class="meta">%s</div>'
                '<h3><a href="%s">%s</a></h3>%s</li>' % (e(meta), e(p["url"]), e(p["title"]), excerpt))

    def cards(self, posts):
        return '<ul class="cards">%s</ul>' % "".join(self.card(p) for p in posts)

    def page(self, path, title, description, body, posts_on_page):
        cfg = self.cfg
        verify = ""
        if cfg.get("google_site_verification"):
            verify += '<meta name="google-site-verification" content="%s">\n' % e(cfg["google_site_verification"])
        if cfg.get("naver_site_verification"):
            verify += '<meta name="naver-site-verification" content="%s">\n' % e(cfg["naver_site_verification"])
        ld = {
            "@context": "https://schema.org", "@type": "CollectionPage",
            "name": title, "url": self.url + path, "inLanguage": "ko-KR",
            "mainEntity": {"@type": "ItemList", "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": p["url"], "name": p["title"]}
                for i, p in enumerate(posts_on_page[:100])]},
        }
        if cfg.get("author"):
            ld["author"] = {"@type": "Person", "name": cfg["author"]}
        full_title = title if title == cfg["site_title"] else "%s | %s" % (title, cfg["site_title"])
        doc = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<meta name="description" content="%s">
<link rel="canonical" href="%s">
%s<link rel="stylesheet" href="%s">
<script type="application/ld+json">%s</script>
</head>
<body>
<header class="top"><a class="brand" href="%s">%s</a></header>
<main>
%s
</main>
<footer class="foot">%s</footer>
</body>
</html>
""" % (e(full_title), e(description), e(self.url + path), verify, self.href("/style.css"),
       json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"), self.href("/"), e(cfg["site_title"]),
       body, self.footer())
        target = os.path.join(OUT, path.strip("/"), "index.html")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(doc)
        newest = max((p.get("date", "") for p in posts_on_page), default="")
        self.pages.append((path, newest))

    def footer(self):
        who = " · ".join(x for x in [self.cfg.get("author", ""), self.cfg.get("affiliation", "")] if x)
        note = "각 글의 원문은 작성자의 블로그에 있습니다. 이 페이지는 제목과 짧은 요약만 보여 줍니다."
        return "%s<p>%s</p>" % ("<p>%s</p>" % e(who) if who else "", e(note))


def build(argv):
    cfg = common.load_config()
    today = today_kst(argv)
    store = common.load_posts()
    state = common.load_json(common.STATE_PATH, {})
    pinned = set(pinned_post_ids(cfg))

    all_posts = sorted((p for p in store.values() if common.passes_blog_filter(p, cfg)),
                       key=lambda p: (p.get("date", ""), p["id"]), reverse=True)
    filtered_out = len(store) - len(all_posts)
    posts = [p for p in all_posts if not is_holdout(p, cfg, pinned)]

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copy(os.path.join(common.ROOT, "static", "style.css"), os.path.join(OUT, "style.css"))
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    site = Site(cfg)

    by_cat = defaultdict(list)
    for p in posts:
        by_cat[p.get("category") or "기타"].append(p)
    by_month = defaultdict(list)
    for p in posts:
        if p.get("date"):
            by_month[p["date"][:7]].append(p)

    cat_base = "/" + cfg.get("category_base", "artificial-turf").strip("/")
    cat_links = "".join('<li><a href="%s">%s</a> <span class="n">%d</span></li>' % (
        site.href("%s/%s/" % (cat_base, slug_for(c, cfg))), e(c), len(v))
        for c, v in sorted(by_cat.items(), key=lambda kv: -len(kv[1])))
    month_links = "".join('<li><a href="%s">%s</a> <span class="n">%d</span></li>' % (
        site.href("/archive/%s/" % m), m.replace("-", "년 ") + "월", len(v))
        for m, v in sorted(by_month.items(), reverse=True))

    featured = pick_featured(posts, cfg, state, today)
    latest = posts[:cfg.get("home_latest_count", 20)]
    related = "".join('<li><a href="%s">%s</a> <span class="n">%s</span></li>' % (
        e(s["url"]), e(s["name"]), e(s.get("note", ""))) for s in cfg.get("related_sites", []))
    empty = "<p>아직 글이 없습니다.</p>"
    home = "".join([
        '<section class="hero"><h1>%s</h1><p>%s</p></section>' % (e(cfg["site_title"]), e(cfg.get("site_tagline", ""))),
        '<section><h2>대표 글</h2>' + (site.cards(featured) if featured else empty) + '</section>',
        '<section><h2>최신 글</h2>' + (site.cards(latest) if latest else empty) + '</section>',
        ('<section><h2>함께 보기</h2><ul class="links">' + related + '</ul></section>') if related else "",
        '<section class="cols"><div><h2>카테고리</h2><ul class="links">' + cat_links + '</ul></div>',
        '<div><h2>월별 글</h2><ul class="links">' + month_links + '</ul></div></section>',
    ])
    site.page("/", cfg["site_title"], cfg.get("site_tagline", cfg["site_title"]), home, featured + latest)

    size = cfg.get("list_page_size", 100)
    for cat, items in by_cat.items():
        slug = slug_for(cat, cfg)
        chunks = [items[i:i + size] for i in range(0, len(items), size)]
        for n, chunk in enumerate(chunks, 1):
            path = "%s/%s/" % (cat_base, slug) + ("" if n == 1 else "page/%d/" % n)
            nav = "".join('<a href="%s"%s>%d</a>' % (
                site.href("%s/%s/" % (cat_base, slug) + ("" if i == 1 else "page/%d/" % i)),
                ' class="on"' if i == n else "", i) for i in range(1, len(chunks) + 1)) if len(chunks) > 1 else ""
            body = '<h1>%s 글 모음</h1><p class="sub">%d개의 글</p>%s%s' % (
                e(cat), len(items), site.cards(chunk), '<nav class="pager">%s</nav>' % nav if nav else "")
            site.page(path, "%s 글 모음" % cat, "%s 관련 글 %d개 모음" % (cat, len(items)), body, chunk)

    for month, items in by_month.items():
        label = month.replace("-", "년 ") + "월"
        body = '<h1>%s 글</h1><p class="sub">%d개의 글</p>%s' % (e(label), len(items), site.cards(items))
        site.page("/archive/%s/" % month, "%s 글" % label, "%s에 쓴 인조잔디 글 %d개" % (label, len(items)), body, items)

    with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for path, newest in site.pages:
            lastmod = "<lastmod>%s</lastmod>" % newest if newest else ""
            f.write("  <url><loc>%s</loc>%s</url>\n" % (e(site.url + path), lastmod))
        f.write("</urlset>\n")
    with open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % site.url)

    unmapped = sorted({c for c in by_cat if c != "기타" and c not in cfg.get("category_slugs", {})})
    write_measure_table(all_posts, cfg, pinned)
    state["last_build"] = dt.datetime.now(KST).isoformat(timespec="seconds")
    common.save_json(common.STATE_PATH, state)

    print("허브에 실린 글 %d개 / 비교군 %d개 / 카테고리 거름으로 뺀 글 %d개 / 페이지 %d장" % (
        len(posts), len(all_posts) - len(posts), filtered_out, len(site.pages)))
    print("블로그별 실린 글: " + ", ".join("%s %d개" % (b, n) for b, n in sorted(
        defaultdict_count(posts).items(), key=lambda kv: -kv[1])))
    if unmapped:
        print("주소 이름이 정해지지 않은 카테고리(config.json의 category_slugs에 추가 권장): " + ", ".join(unmapped))


def defaultdict_count(posts):
    counts = defaultdict(int)
    for p in posts:
        counts[p.get("blog", "")] += 1
    return counts


def read_measure_checks(path):
    """사람이 적어 둔 '구글 노출 확인일'을 읽는다.
    엑셀은 그냥 저장하면 한글을 CP949로, 'CSV UTF-8'로 저장하면 UTF-8로 쓰므로 둘 다 받는다."""
    if not os.path.exists(path):
        return {}
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", "replace")
    checked = {}
    for row in csv.DictReader(text.splitlines()):
        if row.get("글 번호") and (row.get("구글 노출 확인일") or "").strip():
            checked[row["글 번호"]] = row["구글 노출 확인일"].strip()
    return checked


def google_search_cell(title):
    """엑셀에서 누르면 구글 검색이 열리는 칸(HYPERLINK 수식). 검색은 사람이 눈으로 확인한다."""
    url = "https://www.google.com/search?q=" + urllib.parse.quote('"%s"' % title)
    return '=HYPERLINK("%s","검색")' % url.replace('"', '""')


def write_measure_table(all_posts, cfg, pinned):
    """측정표(엑셀용 CSV). 사람이 '구글 노출 확인일' 칸만 채우면 된다.
    이미 적어 둔 확인일은 다시 만들어도 지워지지 않는다."""
    path = os.path.join(common.DATA_DIR, "measure.csv")
    checked = read_measure_checks(path)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["글 번호", "그룹", "발행일", "블로그", "제목", "구글 검색", "구글 노출 확인일", "원문 주소"])
        for p in all_posts:
            group = "비교군(허브 제외)" if is_holdout(p, cfg, pinned) else "허브"
            w.writerow([p["id"], group, p.get("date", ""), p.get("blog", ""), p["title"],
                        google_search_cell(p["title"]), checked.get(p["id"], ""), p["url"]])


if __name__ == "__main__":
    build(sys.argv[1:])
