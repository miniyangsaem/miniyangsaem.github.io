# -*- coding: utf-8 -*-
"""허브 시험: 샘플 RSS(티스토리는 실제 RSS 내용, 네이버는 [샘플])로 수집부터 페이지 생성까지 확인."""
import csv
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
FIX = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.join(PROJECT, "scripts"))

import common  # noqa: E402
import fetch  # noqa: E402


def read(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


def test_naver_rss_links_become_mobile_and_excerpt_is_short():
    posts = fetch.parse_rss(read("naver_rss.xml"), "naver", "jmcgr", 180)
    assert len(posts) == 12
    for p in posts:
        assert re.fullmatch(r"https://m\.blog\.naver\.com/jmcgr/\d+", p["url"])
        assert "?" not in p["url"]
        assert len(p["excerpt"]) <= 181
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["date"])


def test_tistory_rss_real_content():
    posts = fetch.parse_rss(read("tistory_rss.xml"), "tistory", "jmcgr", 180)
    assert len(posts) == 10
    assert posts[0]["title"] == "바닥 인조잔디 깔기 시공 사례"
    assert posts[0]["date"] == "2022-12-07"
    assert "&nbsp;" not in "".join(p["excerpt"] for p in posts)


def test_naver_list_keeps_only_public_searchable_posts():
    posts = fetch.parse_naver_list(read("naver_list.json"), "jmcgr")
    assert [p["title"] for p in posts] == ["[샘플] 예전 글 공개"]
    assert posts[0]["date"] == "2024-03-05"


def test_merge_never_duplicates_and_fills_blanks():
    store = {}
    rss = fetch.parse_rss(read("naver_rss.xml"), "naver", "jmcgr", 180)
    assert common.merge_posts(store, rss) == 12
    assert common.merge_posts(store, rss) == 0
    pc_form = dict(rss[0], id=common.post_id("naver", "https://blog.naver.com/jmcgr/%s" % rss[0]["url"].rsplit("/", 1)[1]))
    assert pc_form["id"] == rss[0]["id"]


def test_holdout_is_stable_and_near_requested_share():
    ids = ["naver:x:%d" % i for i in range(2000)]
    first = [common.in_holdout(i, 30) for i in ids]
    assert first == [common.in_holdout(i, 30) for i in ids]
    assert 0.25 < sum(first) / len(ids) < 0.35


@pytest.fixture()
def project(tmp_path):
    dst = tmp_path / "hub"
    shutil.copytree(PROJECT, dst, ignore=shutil.ignore_patterns("_site", "data", "__pycache__", ".pytest_cache"))
    cfg = json.loads((dst / "config.json").read_text(encoding="utf-8"))
    cfg["site_url"] = "https://example.github.io"
    cfg["google_site_verification"] = "GTEST123"
    cfg["measurement"]["holdout_percent"] = 30
    cfg["featured"]["pinned_urls"] = ["https://jmcgr.tistory.com/entry/%EC%9D%B8%EC%A1%B0%EC%9E%94%EB%94%94%EC%8B%9C%EA%B3%B5%EB%B9%84-%EA%B8%B0%EC%A4%80%EC%9D%80"]
    (dst / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    store = {}
    common.merge_posts(store, fetch.parse_rss(read("naver_rss.xml"), "naver", "jmcgr", 180))
    common.merge_posts(store, fetch.parse_rss(read("tistory_rss.xml"), "tistory", "jmcgr", 180))
    os.makedirs(dst / "data")
    (dst / "data" / "posts.json").write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    return dst


def run_build(project, day):
    r = subprocess.run([sys.executable, "scripts/build.py", "--today", day], cwd=project,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_build_makes_pages_sitemap_robots_and_hides_holdout(project):
    run_build(project, "2026-11-04")
    site = project / "_site"
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "인조잔디의 모든 것" in home
    assert '<meta name="google-site-verification" content="GTEST123">' in home
    assert "jmcgr.co.kr/495150" in home
    assert (site / "robots.txt").read_text().endswith("Sitemap: https://example.github.io/sitemap.xml\n")
    sitemap = (site / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://example.github.io/</loc>" in sitemap
    assert "/artificial-turf/pet/" in sitemap and "/archive/2022-12/" in sitemap

    store = json.loads((project / "data" / "posts.json").read_text(encoding="utf-8"))
    every_page = "".join(p.read_text(encoding="utf-8") for p in site.rglob("index.html"))
    import build
    cfg = json.loads((project / "config.json").read_text(encoding="utf-8"))
    pinned = set(build.pinned_post_ids(cfg))
    hidden = 0
    for p in store.values():
        shown = 'href="%s"' % p["url"].replace("&", "&amp;") in every_page
        assert shown == (not build.is_holdout(p, cfg, pinned)), p["title"]
        hidden += not shown
    assert hidden > 0
    assert not list(site.rglob("*.html"))[0].name.startswith("post")  # 글별 페이지 없음


def test_featured_rotates_daily_and_pinned_stays_first(project):
    def featured(day):
        run_build(project, day)
        home = (project / "_site" / "index.html").read_text(encoding="utf-8")
        block = home.split("<h2>대표 글</h2>")[1].split("<h2>최신 글</h2>")[0]
        return re.findall(r'<h3><a href="([^"]+)"', block)
    d1 = featured("2026-11-04")
    assert d1 and "%EC%8B%9C%EA%B3%B5%EB%B9%84" in d1[0]
    assert featured("2026-11-04") == d1          # 같은 날은 그대로
    d2 = featured("2026-11-05")
    assert d2[0] == d1[0] and d2[1:] != d1[1:]    # 고정 글은 유지, 나머지는 교체


def test_no_holdout_shows_every_post(project):
    cfg = json.loads((project / "config.json").read_text(encoding="utf-8"))
    cfg["measurement"]["holdout_percent"] = 0
    (project / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    out = run_build(project, "2026-11-04")
    assert "비교군 0개" in out
    rows = list(csv.DictReader(open(project / "data" / "measure.csv", encoding="utf-8-sig")))
    assert {r["그룹"] for r in rows} == {"허브"}


def test_measure_table_excel_saved_as_cp949_keeps_checks_and_has_search_link(project):
    run_build(project, "2026-11-04")
    path = project / "data" / "measure.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    assert rows[0]["구글 검색"].startswith('=HYPERLINK("https://www.google.com/search?q=%22')
    rows[1]["구글 노출 확인일"] = "2026-11-21"
    with open(path, "w", encoding="cp949", errors="replace", newline="") as f:   # 엑셀 기본 저장
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    run_build(project, "2026-11-05")
    again = {r["글 번호"]: r for r in csv.DictReader(open(path, encoding="utf-8-sig"))}
    assert again[rows[1]["글 번호"]]["구글 노출 확인일"] == "2026-11-21"


def test_measure_table_keeps_manual_checks(project):
    run_build(project, "2026-11-04")
    path = project / "data" / "measure.csv"
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    assert {r["그룹"] for r in rows} == {"허브", "비교군(허브 제외)"}
    rows[0]["구글 노출 확인일"] = "2026-11-20"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    run_build(project, "2026-11-05")
    again = {r["글 번호"]: r for r in csv.DictReader(open(path, encoding="utf-8-sig"))}
    assert again[rows[0]["글 번호"]]["구글 노출 확인일"] == "2026-11-20"
