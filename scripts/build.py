# -*- coding: utf-8 -*-
"""인조잔디 허브 사이트 생성.

실행:
    python scripts/build.py [--today YYYY-MM-DD]

출력:
    _site/

기사 추가:
    PRESS_ARTICLES 목록 맨 위에 새 기사 정보를 추가한다.
    id는 중복 없이 지정하고 게시 후에는 유지한다.
    published는 확인한 발행일만 YYYY-MM-DD로 입력한다.
    날짜를 모르면 빈 문자열로 둔다.
"""

import csv
import datetime as dt
import hashlib
import html
import json
import os
import shutil
import sys
import unicodedata
import urllib.parse
from collections import defaultdict

import common


OUT = os.path.join(common.ROOT, "_site")
KST = dt.timezone(dt.timedelta(hours=9))
SOURCE_NAMES = {
    "naver": "네이버 블로그",
    "tistory": "티스토리",
}
ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"))
e = html.escape


# ============================================================
# 언론 보도
#
# 새 기사는 이 목록 맨 위에 추가하세요.
# 홈페이지: 앞쪽 3개 표시
# /press/: 전체 표시
#
# 새 기사 예시:
# {
#     "id": "press-016",
#     "media": "언론사명",
#     "title": "기사 제목",
#     "url": "https://언론사주소/기사주소",
#     "summary": "직접 정리한 기사 요약",
#     "published": "",
# },
# ============================================================

PRESS_ARTICLES = [
    {
        "id": "press-001",
        "media": "이넷뉴스",
        "title": "주목씨지알, 가루 안 나는 ‘ESG 코팅’ 적용···인조잔디 자를 때 떨어지는 검은가루 원인은 ‘라텍스 코팅’",
        "url": "https://www.enetnews.co.kr/news/articleView.html?idxno=56259",
        "summary": (
            "주목씨지알이 인조잔디 절단 시 발생하는 검은 코팅 부스러기를 "
            "줄이기 위해 라텍스 대신 PET 섬유를 열융착하는 ESG 코팅 기술을 "
            "소개했습니다. 등록특허 제10-1966419호에 기반한 기술로, "
            "숨터프에 처음 적용했으며 자사 제품으로 적용을 확대할 계획입니다."
        ),
        "published": "",
    },
    {
        "id": "press-002",
        "media": "한국목재신문",
        "title": "주목씨지알, ‘ESG 열융착 인조잔디’ 대안 제시…규격별 공급 확대",
        "url": "https://www.woodkorea.co.kr/news/articleView.html?idxno=92273",
        "summary": (
            "주목씨지알이 파크골프장 그린·페어웨이·러프에 맞춘 "
            "킹터프 에어 20·35·55mm 인조잔디 공급을 확대합니다. "
            "상층 PP 기포지와 하층 PET 원단을 열융착한 ESG 백코팅으로 "
            "굴곡진 지면 밀착성과 배수·통기성을 높였다고 설명했습니다."
        ),
        "published": "",
    },
    {
        "id": "press-003",
        "media": "한국목재신문",
        "title": "주목씨지알, 미세플라스틱 배출 막는 무충진 스포츠 인조잔디 상용화… ‘K터프·신터프’ 양산",
        "url": "https://www.woodkorea.co.kr/news/articleView.html?idxno=92210",
        "summary": (
            "주목씨지알이 고무·플라스틱 충진재 없이 사용하는 스포츠 "
            "인조잔디 K터프와 신터프의 양산을 양저우 코리아 공장에서 "
            "시작했습니다. K터프에는 KDK 공법, 신터프에는 ATY 공법을 "
            "적용해 원사의 굴곡과 밀도로 완충 구조를 구현했다고 설명했습니다."
        ),
        "published": "",
    },
    {
        "id": "press-004",
        "media": "이넷뉴스",
        "title": "주목씨지알, 중국 ‘양저우코리아’ 생산기지 구축···인조잔디 공급 경쟁력 강화",
        "url": "https://www.enetnews.co.kr/news/articleView.html?idxno=54471",
        "summary": (
            "주목씨지알이 중국에 양저우코리아 생산기지를 구축하고 "
            "가정용부터 스포츠 시설용까지 인조잔디 공급 확대에 나섰습니다. "
            "생산 규모 확대를 바탕으로 공급 경쟁력을 강화한다는 내용입니다."
        ),
        "published": "",
    },
    {
        "id": "press-005",
        "media": "잡포스트",
        "title": "주목씨지알, 중국 ‘양저우코리아’ 생산공장 설립…국내 인조잔디 공급 확대",
        "url": "https://www.job-post.co.kr/news/articleView.html?idxno=227416",
        "summary": (
            "주목씨지알이 중국 양저우코리아 생산공장을 설립하고 국내 "
            "가정용·스포츠용 인조잔디 공급을 확대합니다. 마당·옥상·테라스용 "
            "롤·매트부터 전문 구장용 제품까지 공급하며, 회사는 KCL의 "
            "49개 항목 유해 성분 검사 통과와 품질 관리 강화 방침을 밝혔습니다."
        ),
        "published": "",
    },
    {
        "id": "press-006",
        "media": "피앤피뉴스",
        "title": "주목씨지알, 중국 ‘양저우코리아’ 설립 기념 킹터프 인조잔디 테니스장 시스템 할인 시공",
        "url": "https://www.gosiweek.com/article/1065598158911434",
        "summary": (
            "주목씨지알이 양저우코리아 설립 기념 테니스장 할인 시공 행사를 "
            "소개했습니다. 기사에 안내된 가격은 킹터프 20mm 인조잔디와 "
            "㎡당 규사 25kg, 시공비를 포함해 ㎡당 16,000원입니다. "
            "ITF 코트 페이스 개념을 참고하고 KS 인조잔디 시스템 기준을 "
            "적용했다고 설명했습니다."
        ),
        "published": "",
    },
    {
        "id": "press-007",
        "media": "한국목재신문",
        "title": "주목씨지알, ‘숨터프 인조잔디’ 동티모르 축구장 프로젝트 진행... 해외 시장 주목",
        "url": "https://www.woodkorea.co.kr/news/articleView.html?idxno=80852",
        "summary": (
            "주목씨지알이 동티모르 축구장에 스포츠용 숨터프 55mm "
            "인조잔디를 시공한 해외 프로젝트를 소개했습니다. 잔디 배치와 "
            "라인 재단, 규사·SEBS 충진재 포설을 진행했으며, 섬유 기반 "
            "백코팅의 배수성과 원사 고정력을 주요 특징으로 설명했습니다."
        ),
        "published": "",
    },
    {
        "id": "press-008",
        "media": "데일리시큐",
        "title": "주목씨지알, 숨을 쉬는 인조잔디 ‘숨터프’로 친환경 스포츠구장 보급",
        "url": "https://www.dailysecu.com/news/articleView.html?idxno=143295",
        "summary": (
            "주목씨지알이 친환경 인증을 받은 스포츠용 숨터프의 보급 계획을 "
            "소개했습니다. 폴리계열 소재와 PET를 활용한 백코팅으로 "
            "새활용 가능성을 높이고, 특허 기술을 적용해 배수 성능과 "
            "침수 후 원사 고정력을 개선했다고 설명했습니다."
        ),
        "published": "",
    },
    {
        "id": "press-009",
        "media": "라이브뉴스",
        "title": "인조잔디의 패러다임을 바꾸다… 숨터프, ‘숨 쉬는 기술’ 도입",
        "url": "https://www.livesnews.com/news/article.html?no=58491",
        "summary": (
            "숨터프가 라텍스 대신 PET 기반 ESG 백코팅을 적용한 인조잔디 "
            "기술을 소개했습니다. 통기·배수 구조와 모노·클림프 원사를 "
            "조합한 고밀도 제직을 주요 특징으로 설명하며, 복원력과 "
            "관리 편의성 향상에 초점을 맞췄습니다."
        ),
        "published": "",
    },
    {
        "id": "press-010",
        "media": "파이낸스투데이",
        "title": "인조잔디 전문기업 SCM(에스시엠), 특허 기반 숨터프 인조잔디로 스포츠 구장 혁신 선도",
        "url": "https://www.fntoday.co.kr/news/articleView.html?idxno=339793",
        "summary": (
            "에스시엠이 등록특허 제10-1966419호와 제10-1929204호를 "
            "기반으로 한 스포츠용 숨터프를 소개했습니다. PET 백코팅으로 "
            "원사 고정력과 배수 성능을 높였다고 설명하며, 축구장·테니스장 "
            "등의 경기 환경 개선과 유지관리 부담 절감을 목표로 합니다."
        ),
        "published": "",
    },
    {
        "id": "press-011",
        "media": "데일리시큐",
        "title": "인조잔디 전문 기업 SCM, 신제품 ‘신터프’ 출시",
        "url": "https://www.dailysecu.com/news/articleView.html?idxno=153880",
        "summary": (
            "에스시엠이 충격흡수패드와 인조잔디를 일체형으로 결합한 "
            "신터프를 출시했습니다. 회사는 규사와 충진재 없이 사용하는 "
            "구조로 충격흡수 성능을 확보하고, 별도 패드 설치 과정을 줄여 "
            "시공 시간과 비용을 절감할 수 있다고 설명했습니다."
        ),
        "published": "",
    },
    {
        "id": "press-012",
        "media": "시선뉴스",
        "title": "신터프, 실내 풋살장에 최적화된 인조잔디 시스템 개발",
        "url": "https://www.sisunnews.co.kr/news/articleView.html?idxno=219473",
        "summary": (
            "에스시엠이 충격흡수패드와 인조잔디를 결합한 실내 풋살장용 "
            "신터프를 개발했습니다. 고밀도 클림프 원사와 모노 원사를 함께 "
            "적용했으며, 회사는 무충진 구조로 충격흡수성과 일정한 공 구름을 "
            "구현하고 시공 공정을 단순화했다고 설명했습니다."
        ),
        "published": "",
    },
    {
        "id": "press-013",
        "media": "K스피릿",
        "title": "인조잔디 전문 기업 ‘SCM(에스시엠)’, 무충진 실내 풋살장 인조잔디 K-터프 출시",
        "url": "https://www.ikoreanspirit.com/news/articleView.html?idxno=81914",
        "summary": (
            "에스시엠이 규사와 고무칩을 사용하지 않는 실내 풋살장용 "
            "K-터프를 출시했습니다. KDK 가공 기술과 S자 형태의 원사를 "
            "적용해 내구성과 복원력을 높였다고 설명했으며, 충진재 "
            "운반·포설 공정과 유지관리 부담을 줄이는 데 초점을 맞췄습니다."
        ),
        "published": "",
    },
    {
        "id": "press-014",
        "media": "이넷뉴스",
        "title": "실내 풋살장, 무충진 인조잔디 ‘K-터프’ 이목 집중",
        "url": "https://www.enetnews.co.kr/news/articleView.html?idxno=44225",
        "summary": (
            "에스시엠이 무충진 인조잔디와 구조물·휀스·그물망·보호패드를 "
            "통합한 K-터프 실내풋살장시스템을 소개했습니다. 생산부터 "
            "시공·사후관리까지 일괄 제공하며, 충진재 관리 부담을 줄여 "
            "신규 창업과 노후 구장 개선을 지원한다고 설명했습니다."
        ),
        "published": "",
    },
    {
        "id": "press-015",
        "media": "이투데이",
        "title": "SCM(에스시엠), 특허 3중 구조 인조잔디로 테니스장 패러다임을 바꾸다",
        "url": "https://www.etoday.co.kr/news/view/2410935",
        "summary": (
            "에스시엠이 등록특허 제10-1977176호에 기반한 테니스장용 "
            "3중 구조 인조잔디를 소개했습니다. 직모와 두 종류의 클림프 "
            "원사를 조합해 공의 움직임과 충격 분산을 고려했으며, "
            "배수 관련 토목특허 제10-2436740호를 통한 유지관리 효율 "
            "향상도 설명했습니다."
        ),
        "published": "",
    },
]


def today_kst(argv):
    if "--today" in argv:
        return dt.date.fromisoformat(
            argv[argv.index("--today") + 1]
        )
    return dt.datetime.now(KST).date()


def norm_cat(name):
    """카테고리 이름의 공백과 보이지 않는 문자를 정리한다."""
    text = unicodedata.normalize(
        "NFKC", name or ""
    ).translate(ZERO_WIDTH)
    return " ".join(text.split())


def slug_for(category, cfg):
    category = norm_cat(category)
    if not category:
        return "etc"

    table = {
        norm_cat(key): value
        for key, value in cfg.get("category_slugs", {}).items()
    }
    mapped = table.get(category)
    if mapped:
        return mapped

    return (
        "c-"
        + hashlib.sha1(
            category.encode("utf-8")
        ).hexdigest()[:6]
    )


def pinned_post_ids(cfg):
    """기존 고정 글의 비교군 제외 설정을 유지한다."""
    ids = []
    for url in cfg.get("featured", {}).get("pinned_urls", []):
        key = common.naver_key(url)
        ids.append(
            common.post_id(
                "naver", common.naver_mobile_url(*key)
            )
            if key else common.post_id("tistory", url)
        )
    return ids


def is_holdout(post, cfg, pinned):
    """기존 측정용 비교군 설정을 유지한다."""
    return (
        post["id"] not in pinned
        and common.in_holdout(
            post["id"],
            cfg.get("measurement", {}).get(
                "holdout_percent", 0
            ),
        )
    )


def prepare_press(articles):
    """기사 필수값·중복·주소·발행일을 검사한다."""
    result = []
    urls = set()
    ids = set()

    for number, original in enumerate(articles, 1):
        article = dict(original)

        for key in ("id", "media", "title", "url", "summary"):
            value = article.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    "기사 %d: %s 항목을 확인하세요."
                    % (number, key)
                )
            article[key] = value.strip()

        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
        if any(
            char not in allowed
            for char in article["id"]
        ):
            raise ValueError(
                "기사 ID는 영문 소문자·숫자·하이픈·밑줄만 사용하세요."
            )

        url = urllib.parse.urlsplit(article["url"])
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or any(
                char.isspace()
                for char in article["url"]
            )
        ):
            raise ValueError(
                "기사 원문은 올바른 HTTPS 주소로 입력하세요."
            )

        article["url"] = urllib.parse.urlunsplit(
            url._replace(fragment="")
        )

        if (
            article["url"] in urls
            or article["id"] in ids
        ):
            raise ValueError(
                "기사 주소 또는 ID가 중복됐습니다."
            )

        urls.add(article["url"])
        ids.add(article["id"])

        date = article.get("published", "")
        if not isinstance(date, str):
            raise ValueError(
                "기사 발행일은 문자열로 입력하세요."
            )

        date = date.strip()
        if (
            date
            and dt.date.fromisoformat(date).isoformat() != date
        ):
            raise ValueError(
                "기사 발행일은 YYYY-MM-DD로 입력하세요."
            )

        article["published"] = date
        result.append(article)

    return result


def press_post(article):
    """구조화 데이터의 기사 목록에 사용할 정보를 만든다."""
    return {
        "title": article["title"],
        "url": article["url"],
        "excerpt": article["summary"],
        "source": article["media"],
        "date": article["published"],
    }


def press_cards(site, articles, heading="h3"):
    """기사 제목·출처·요약·원문 링크를 HTML로 출력한다."""
    cards = []

    for article in articles:
        date = article["published"]
        date_html = (
            ' · <time datetime="%s">%s</time>'
            % (e(date), e(date))
        ) if date else ""

        cards.append(
            '<li class="card" id="%s">'
            '<article aria-labelledby="%s-title">'
            '<div class="meta">출처: %s%s</div>'
            '<%s id="%s-title"><a href="%s">%s</a></%s>'
            '<p class="ex">%s</p>'
            '<p><a href="%s">기사 원문 보기 ↗</a>'
            ' · <a href="%s">요약 고정 링크</a></p>'
            '</article></li>'
            % (
                e(article["id"]),
                e(article["id"]),
                e(article["media"]),
                date_html,
                heading,
                e(article["id"]),
                e(article["url"]),
                e(article["title"]),
                heading,
                e(article["summary"]),
                e(article["url"]),
                e(
                    site.href("/press/")
                    + "#"
                    + article["id"]
                ),
            )
        )

    return '<ul class="cards">%s</ul>' % "".join(cards)


class Site:
    def __init__(self, cfg):
        self.cfg = cfg
        self.url = cfg["site_url"].rstrip("/")
        self.base = urllib.parse.urlparse(
            self.url
        ).path.rstrip("/")
        self.pages = []

    def href(self, path):
        return self.base + path

    def card(self, post):
        meta = " · ".join(
            value for value in [
                post.get("date", ""),
                SOURCE_NAMES.get(
                    post["source"], post["source"]
                ),
                post.get("category", ""),
            ] if value
        )

        excerpt = (
            '<p class="ex">%s</p>' % e(post["excerpt"])
            if post.get("excerpt") else ""
        )

        return (
            '<li class="card"><div class="meta">%s</div>'
            '<h3><a href="%s">%s</a></h3>%s</li>'
            % (
                e(meta),
                e(post["url"]),
                e(post["title"]),
                excerpt,
            )
        )

    def cards(self, posts):
        return '<ul class="cards">%s</ul>' % "".join(
            self.card(post) for post in posts
        )

    def page(
        self,
        path,
        title,
        description,
        body,
        posts_on_page,
        modified="",
    ):
        cfg = self.cfg
        verify = ""

        if cfg.get("google_site_verification"):
            verify += (
                '<meta name="google-site-verification" content="%s">\n'
                % e(cfg["google_site_verification"])
            )

        if cfg.get("naver_site_verification"):
            verify += (
                '<meta name="naver-site-verification" content="%s">\n'
                % e(cfg["naver_site_verification"])
            )

        # このサイトではなく原文のURLを一覧として示す。
        # 각 원문의 URL을 목록으로 표시한다.
        # 언론사 기사를 이 사이트가 발행한 기사로 표시하지 않는다.
        ld = {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": title,
            "url": self.url + path,
            "inLanguage": "ko-KR",
            "mainEntity": {
                "@type": "ItemList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": index + 1,
                        "url": post["url"],
                        "name": post["title"],
                    }
                    for index, post in enumerate(posts_on_page)
                ],
            },
        }

        if modified:
            ld["dateModified"] = modified

        if cfg.get("author"):
            ld["author"] = {
                "@type": "Person",
                "name": cfg["author"],
            }

        full_title = (
            title if title == cfg["site_title"]
            else "%s | %s" % (
                title, cfg["site_title"]
            )
        )

        og = "".join(
            '<meta property="og:%s" content="%s">\n'
            % (key, e(value))
            for key, value in [
                ("type", "website"),
                ("locale", "ko_KR"),
                ("site_name", cfg["site_title"]),
                ("title", full_title),
                ("description", description),
                ("url", self.url + path),
            ]
        )
        verify = og + verify

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
""" % (
            e(full_title),
            e(description),
            e(self.url + path),
            verify,
            self.href("/style.css"),
            json.dumps(
                ld, ensure_ascii=False
            ).replace("<", "\\u003c"),
            self.href("/"),
            e(cfg["site_title"]),
            body,
            self.footer(),
        )

        target = os.path.join(
            OUT, path.strip("/"), "index.html"
        )
        os.makedirs(
            os.path.dirname(target), exist_ok=True
        )

        with open(
            target, "w", encoding="utf-8"
        ) as file:
            file.write(doc)

        newest = max(
            [modified]
            + [
                post.get("date", "")
                for post in posts_on_page
            ]
        )
        self.pages.append((path, newest))

    def footer(self):
        who = " · ".join(
            value for value in [
                self.cfg.get("author", ""),
                self.cfg.get("affiliation", ""),
            ] if value
        )
        note = (
            "각 글과 기사의 원문은 해당 블로그 및 언론사에 있습니다. "
            "이 사이트는 제목·요약·원문 링크를 제공합니다. "
            "기사 속 제품 사양과 가격·행사는 보도 당시 내용으로 "
            "현재 조건과 다를 수 있습니다."
        )

        return "%s<p>%s</p>" % (
            "<p>%s</p>" % e(who) if who else "",
            e(note),
        )


def build(argv):
    cfg = common.load_config()
    today = today_kst(argv)
    store = common.load_posts()
    state = common.load_json(common.STATE_PATH, {})
    pinned = set(pinned_post_ids(cfg))

    all_posts = sorted(
        (
            post for post in store.values()
            if common.passes_blog_filter(post, cfg)
        ),
        key=lambda post: (
            post.get("date", ""), post["id"]
        ),
        reverse=True,
    )

    filtered_out = len(store) - len(all_posts)
    posts = [
        post for post in all_posts
        if not is_holdout(post, cfg, pinned)
    ]

    articles = prepare_press(PRESS_ARTICLES)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    shutil.copy(
        os.path.join(
            common.ROOT, "static", "style.css"
        ),
        os.path.join(OUT, "style.css"),
    )
    open(os.path.join(OUT, ".nojekyll"), "w").close()

    site = Site(cfg)

    by_cat = defaultdict(list)
    for post in posts:
        by_cat[
            norm_cat(post.get("category")) or "기타"
        ].append(post)

    by_month = defaultdict(list)
    for post in posts:
        if post.get("date"):
            by_month[
                post["date"][:7]
            ].append(post)

    cat_base = "/" + cfg.get(
        "category_base", "artificial-turf"
    ).strip("/")

    cat_links = "".join(
        '<li><a href="%s">%s</a> '
        '<span class="n">%d</span></li>'
        % (
            site.href(
                "%s/%s/" % (
                    cat_base,
                    slug_for(category, cfg),
                )
            ),
            e(category),
            len(items),
        )
        for category, items in sorted(
            by_cat.items(),
            key=lambda pair: -len(pair[1]),
        )
    )

    month_links = "".join(
        '<li><a href="%s">%s</a> '
        '<span class="n">%d</span></li>'
        % (
            site.href("/archive/%s/" % month),
            month.replace("-", "년 ") + "월",
            len(items),
        )
        for month, items in sorted(
            by_month.items(), reverse=True
        )
    )

    latest = posts[
        :cfg.get("home_latest_count", 20)
    ]

    related = "".join(
        '<li><a href="%s">%s</a> '
        '<span class="n">%s</span></li>'
        % (
            e(item["url"]),
            e(item["name"]),
            e(item.get("note", "")),
        )
        for item in cfg.get("related_sites", [])
    )

    empty = "<p>아직 글이 없습니다.</p>"

    # 기사 내용이 바뀌었을 때만 갱신일을 변경한다.
    fingerprint = hashlib.sha256(
        json.dumps(
            articles,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    if (
        state.get("press_fingerprint") != fingerprint
        or not state.get("press_modified")
    ):
        state["press_fingerprint"] = fingerprint
        state["press_modified"] = today.isoformat()

    press_modified = state["press_modified"]
    preview = articles[:3]

    press_preview = (
        '<section><h2>언론 보도</h2>'
        '<p>관련 기사 요약입니다.</p>'
        + press_cards(site, preview)
        + (
            '<p><a href="%s">'
            '언론 보도 전체 %d건 보기 →'
            '</a></p></section>'
        ) % (
            e(site.href("/press/")),
            len(articles),
        )
    ) if articles else ""

    index = "".join(
        '<li><a href="#%s">%s — %s</a></li>'
        % (
            e(article["id"]),
            e(article["title"]),
            e(article["media"]),
        )
        for article in articles
    )

    press_body = (
        '<p><a href="%s">홈으로</a></p>'
        '<h1>주목씨지알·에스시엠 언론 보도</h1>'
        '<p>관련 기사 %d건 · 요약 목록 갱신일: '
        '<time datetime="%s">%s</time></p>'
        '<p>인조잔디 제품·기술·생산기지·시공 사례에 관한 '
        '기사 요약과 원문입니다. 성능과 계획에 관한 내용은 '
        '기사에 소개된 회사 측 설명을 바탕으로 정리했습니다. '
        '기사의 사양·가격·행사는 보도 당시 내용으로 '
        '현재 조건과 다를 수 있습니다.</p>'
        '<nav aria-label="기사 목차">'
        '<h2>기사 목록</h2><ol>%s</ol></nav>%s'
    ) % (
        e(site.href("/")),
        len(articles),
        e(press_modified),
        e(press_modified),
        index,
        press_cards(site, articles, heading="h2"),
    )

    site.page(
        "/press/",
        "주목씨지알·에스시엠 언론 보도",
        "인조잔디 제품·ESG 백코팅·생산 및 시공 관련 언론 보도 요약과 원문 모음",
        press_body,
        [press_post(article) for article in articles],
        modified=press_modified,
    )

    # 대표 글을 제거하고 언론 보도와 최신 글을 표시한다.
    home = "".join([
        (
            '<section class="hero">'
            '<h1>%s</h1><p>%s</p></section>'
        ) % (
            e(cfg["site_title"]),
            e(cfg.get("site_tagline", "")),
        ),
        press_preview,
        (
            '<section><h2>최신 글</h2>'
            + (
                site.cards(latest)
                if latest else empty
            )
            + '</section>'
        ),
        (
            '<section><h2>함께 보기</h2>'
            '<ul class="links">'
            + related
            + '</ul></section>'
        ) if related else "",
        (
            '<section class="cols">'
            '<div><h2>카테고리</h2>'
            '<ul class="links">'
            + cat_links
            + '</ul></div>'
        ),
        (
            '<div><h2>월별 글</h2>'
            '<ul class="links">'
            + month_links
            + '</ul></div></section>'
        ),
    ])

    home_hash = hashlib.sha256(
        home.encode("utf-8")
    ).hexdigest()

    if (
        state.get("home_fingerprint") != home_hash
        or not state.get("home_modified")
    ):
        state["home_fingerprint"] = home_hash
        state["home_modified"] = today.isoformat()

    site.page(
        "/",
        cfg["site_title"],
        cfg.get(
            "site_tagline", cfg["site_title"]
        ),
        home,
        [
            press_post(article)
            for article in preview
        ] + latest,
        modified=state["home_modified"],
    )

    # 카테고리 페이지.
    size = cfg.get("list_page_size", 100)
    if (
        not isinstance(size, int)
        or isinstance(size, bool)
        or size < 1
    ):
        raise ValueError(
            "list_page_size는 1 이상의 정수여야 합니다."
        )

    for category, items in by_cat.items():
        slug = slug_for(category, cfg)
        chunks = [
            items[index:index + size]
            for index in range(0, len(items), size)
        ]

        for number, chunk in enumerate(chunks, 1):
            path = "%s/%s/" % (
                cat_base, slug
            ) + (
                "" if number == 1
                else "page/%d/" % number
            )

            nav = "".join(
                '<a href="%s"%s>%d</a>'
                % (
                    site.href(
                        "%s/%s/" % (cat_base, slug)
                        + (
                            "" if page == 1
                            else "page/%d/" % page
                        )
                    ),
                    (
                        ' class="on"'
                        if page == number else ""
                    ),
                    page,
                )
                for page in range(
                    1, len(chunks) + 1
                )
            ) if len(chunks) > 1 else ""

            body = (
                '<h1>%s 글 모음</h1>'
                '<p class="sub">%d개의 글</p>%s%s'
            ) % (
                e(category),
                len(items),
                site.cards(chunk),
                (
                    '<nav class="pager">%s</nav>'
                    % nav
                ) if nav else "",
            )

            site.page(
                path,
                "%s 글 모음" % category,
                "%s 관련 글 %d개 모음"
                % (category, len(items)),
                body,
                chunk,
            )

    # 월별 페이지.
    for month, items in by_month.items():
        label = month.replace("-", "년 ") + "월"
        body = (
            '<h1>%s 글</h1>'
            '<p class="sub">%d개의 글</p>%s'
        ) % (
            e(label),
            len(items),
            site.cards(items),
        )

        site.page(
            "/archive/%s/" % month,
            "%s 글" % label,
            "%s에 쓴 인조잔디 글 %d개"
            % (label, len(items)),
            body,
            items,
        )

    # 사이트맵.
    with open(
        os.path.join(OUT, "sitemap.xml"),
        "w",
        encoding="utf-8",
    ) as file:
        file.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        )

        for path, newest in site.pages:
            lastmod = (
                "<lastmod>%s</lastmod>" % newest
                if newest else ""
            )
            file.write(
                "  <url><loc>%s</loc>%s</url>\n"
                % (
                    e(site.url + path),
                    lastmod,
                )
            )

        file.write("</urlset>\n")

    # 크롤링 허용 및 사이트맵 안내.
    with open(
        os.path.join(OUT, "robots.txt"),
        "w",
        encoding="utf-8",
    ) as file:
        file.write(
            "User-agent: *\nAllow: /\n\n"
            "Sitemap: %s/sitemap.xml\n"
            % site.url
        )

    unmapped = sorted({
        category
        for category in by_cat
        if (
            category != "기타"
            and slug_for(
                category, cfg
            ).startswith("c-")
        )
    })

    write_measure_table(
        all_posts, cfg, pinned
    )

    state["last_build"] = (
        dt.datetime.now(KST).isoformat(
            timespec="seconds"
        )
    )
    common.save_json(common.STATE_PATH, state)

    print(
        "허브에 실린 글 %d개 / 비교군 %d개 / "
        "카테고리 거름으로 뺀 글 %d개 / 페이지 %d장"
        % (
            len(posts),
            len(all_posts) - len(posts),
            filtered_out,
            len(site.pages),
        )
    )
    print(
        "블로그별 실린 글: "
        + ", ".join(
            "%s %d개" % (blog, count)
            for blog, count in sorted(
                defaultdict_count(posts).items(),
                key=lambda pair: -pair[1],
            )
        )
    )

    if unmapped:
        print(
            "주소 이름이 정해지지 않은 카테고리"
            "(config.json의 category_slugs에 추가 권장): "
            + ", ".join(unmapped)
        )


def defaultdict_count(posts):
    counts = defaultdict(int)
    for post in posts:
        counts[post.get("blog", "")] += 1
    return counts


def read_measure_checks(path):
    """기존 측정표에 적어 둔 구글 노출 확인일을 읽는다."""
    if not os.path.exists(path):
        return {}

    with open(path, "rb") as file:
        raw = file.read()

    for encoding in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", "replace")

    checked = {}

    for row in csv.DictReader(text.splitlines()):
        date = (
            row.get("구글 노출 확인일") or ""
        ).strip()
        if row.get("글 번호") and date:
            checked[row["글 번호"]] = date

    return checked


def google_search_cell(title):
    """엑셀에서 제목으로 구글 검색을 여는 수식."""
    url = (
        "https://www.google.com/search?q="
        + urllib.parse.quote('"%s"' % title)
    )
    return '=HYPERLINK("%s","검색")' % (
        url.replace('"', '""')
    )


def write_measure_table(all_posts, cfg, pinned):
    """기존 확인일을 보존하면서 측정표를 갱신한다."""
    path = os.path.join(
        common.DATA_DIR, "measure.csv"
    )
    checked = read_measure_checks(path)

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.writer(file)
        writer.writerow([
            "글 번호",
            "그룹",
            "발행일",
            "블로그",
            "제목",
            "구글 검색",
            "구글 노출 확인일",
            "원문 주소",
        ])

        for post in all_posts:
            group = (
                "비교군(허브 제외)"
                if is_holdout(post, cfg, pinned)
                else "허브"
            )
            writer.writerow([
                post["id"],
                group,
                post.get("date", ""),
                post.get("blog", ""),
                post["title"],
                google_search_cell(post["title"]),
                checked.get(post["id"], ""),
                post["url"],
            ])


if __name__ == "__main__":
    build(sys.argv[1:])
