"""
Web search — all sources are free, no API keys required.
Edit this file to add/remove search providers or tweak result counts.
"""
import re, time, requests, urllib.parse, html as _html
from xml.etree import ElementTree as ET

_EXPLICIT_KEYWORDS = {
    "porn","xxx","cock","dick","penis","vagina","pussy","nude","naked","sex tape",
    "onlyfans","boobs","tits","ass","anal","blowjob","cumshot","hentai","nsfw",
    "adult film","adult video","sex video","erotic",
}

def _clean_text(raw: str) -> str:
    """Decode HTML entities then strip all tags."""
    t = _html.unescape(raw or "")
    t = re.sub(r"<[^>]+>", "", t)
    return t.strip()

def _is_explicit(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in _EXPLICIT_KEYWORDS)

SEARXNG_INSTANCES = [
    "https://searx.be", "https://search.sapti.me", "https://searxng.site",
    "https://searx.tiekoetter.com", "https://searx.fmac.xyz",
    "https://search.mdosch.de", "https://priv.au", "https://paulgo.io",
    "https://searx.work", "https://searx.oloke.org",
]

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ── General web search ─────────────────────────────────────────────────────
def search_ddg(query: str, safe: bool = True) -> list:
    """Mojeek search (no bot-blocking) with HTML fallback."""
    results = []
    try:
        r = requests.get(
            "https://www.mojeek.com/search",
            params={"q": query, "safe": "1" if safe else "0", "fmt": "json"},
            timeout=8, headers={"User-Agent": _UA, "Accept": "application/json, text/html"},
        )
        if r.status_code == 200:
            try:
                for item in r.json().get("results", [])[:5]:
                    results.append({"source": "Mojeek",
                                    "title": _clean_text(item.get("title", "")),
                                    "text": _clean_text(item.get("desc", ""))[:200],
                                    "url": item.get("url", "")})
            except Exception:
                titles = re.findall(r'class="title"[^>]*>(.*?)</a>', r.text, re.DOTALL)
                descs  = re.findall(r'class="s"[^>]*>(.*?)</p>',     r.text, re.DOTALL)
                urls   = re.findall(r'class="ob"[^>]*href="([^"]+)"', r.text)
                for i, t in enumerate(titles[:5]):
                    t = re.sub(r"<[^>]+>", "", t).strip()
                    d = re.sub(r"<[^>]+>", "", descs[i]).strip()[:180] if i < len(descs) else ""
                    u = urls[i] if i < len(urls) else ""
                    if t:
                        results.append({"source": "Mojeek", "title": t, "text": d, "url": u})
    except Exception:
        pass
    return results


def search_searxng(query: str, safe: bool = True) -> list:
    import random
    instances = SEARXNG_INSTANCES[:]
    random.shuffle(instances)
    for instance in instances:
        try:
            r = requests.get(
                f"{instance}/search",
                params={"q": query, "format": "json",
                        "safesearch": "1" if safe else "0", "language": "en"},
                timeout=7, headers={"User-Agent": _UA},
            )
            if r.status_code == 200:
                results = [
                    {"source": "Web", "title": x.get("title", ""),
                     "text": x.get("content", ""), "url": x.get("url", "")}
                    for x in r.json().get("results", [])[:6]
                    if x.get("content") or x.get("title")
                ]
                if results:
                    return results
        except Exception:
            continue
    return []


# ── YouTube / Invidious ────────────────────────────────────────────────────
_invidious_cache: dict = {"instance": None, "checked": 0.0}

def _get_invidious_instance() -> str | None:
    c = _invidious_cache
    if c["instance"] and (time.time() - c["checked"]) < 600:
        return c["instance"]
    fallbacks = [
        "https://invidious.privacydev.net", "https://invidious.fdn.fr",
        "https://inv.tux.pizza", "https://invidious.nerdvpn.de",
        "https://invidious.lunar.icu", "https://yt.cdaut.de",
    ]
    try:
        idx = requests.get("https://api.invidious.io/instances.json",
                           timeout=6, headers={"User-Agent": _UA})
        if idx.status_code == 200:
            live = [
                f"https://{e[0]}" for e in idx.json()
                if isinstance(e, list) and len(e) > 1
                and e[1].get("api") is True and e[1].get("type") == "https"
            ]
            fallbacks = live[:10] + fallbacks
    except Exception:
        pass
    for inst in fallbacks:
        try:
            r = requests.get(f"{inst}/api/v1/trending", timeout=5,
                             headers={"User-Agent": _UA})
            if r.status_code == 200:
                c["instance"] = inst
                c["checked"]  = time.time()
                return inst
        except Exception:
            continue
    return None


def search_youtube(query: str, safe: bool = True) -> list:
    inst = _get_invidious_instance()
    if not inst:
        return []
    try:
        r = requests.get(f"{inst}/api/v1/search",
                         params={"q": query, "type": "video", "sort_by": "relevance"},
                         timeout=8, headers={"User-Agent": _UA})
        if r.status_code == 200:
            results = []
            for v in r.json()[:5]:
                if not v.get("videoId"):
                    continue
                desc = _clean_text(v.get("description", ""))[:200]
                meta = f"{v.get('author','')} · {v.get('viewCountText','')} · {v.get('publishedText','')}"
                text = f"{meta}\n{desc}" if desc else meta
                results.append({
                    "source": "YouTube",
                    "title":  v.get("title", ""),
                    "text":   text,
                    "url":    f"https://youtube.com/watch?v={v['videoId']}",
                    "video_id": v["videoId"],
                })
            return results
    except Exception:
        pass
    return []


def fetch_youtube_comments(video_id: str, inst: str = None, limit: int = 5) -> str:
    """Return top comments for a video as a plain-text block."""
    inst = inst or _get_invidious_instance()
    if not inst:
        return ""
    try:
        r = requests.get(f"{inst}/api/v1/comments/{video_id}",
                         params={"sort_by": "top"}, timeout=8,
                         headers={"User-Agent": _UA})
        if r.status_code == 200:
            comments = r.json().get("comments", [])[:limit]
            lines = [f'- {_clean_text(c.get("content","")[:200])} ({c.get("likeCount",0)} likes)'
                     for c in comments if c.get("content")]
            return "\n".join(lines)
    except Exception:
        pass
    return ""


def search_youtube_trending() -> list:
    inst = _get_invidious_instance()
    if not inst:
        return []
    try:
        r = requests.get(f"{inst}/api/v1/trending", timeout=8,
                         headers={"User-Agent": _UA})
        if r.status_code == 200:
            return [
                {"source": "YouTube Trending", "title": v.get("title", ""),
                 "text": f"{v.get('author','')} · {v.get('viewCountText','')}",
                 "url":  f"https://youtube.com/watch?v={v['videoId']}"}
                for v in r.json()[:6] if v.get("videoId")
            ]
    except Exception:
        pass
    return []


# ── News ───────────────────────────────────────────────────────────────────
def search_news(query: str, safe: bool = True) -> list:
    """Google News RSS + GDELT + HackerNews — no key, no limit."""
    results = []
    try:
        r = requests.get(
            f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en&gl=US&ceid=US:en",
            timeout=8, headers={"User-Agent": _UA},
        )
        if r.status_code == 200:
            for item in re.findall(r"<item>(.*?)</item>", r.text, re.DOTALL)[:6]:
                tm = re.search(r"<title>(.*?)</title>",            item, re.DOTALL)
                lm = re.search(r"<link/>(.*?)(?:<|\Z)",            item, re.DOTALL)
                if not lm: lm = re.search(r"<link>(.*?)</link>",  item, re.DOTALL)
                dm = re.search(r"<description>(.*?)</description>", item, re.DOTALL)
                pm = re.search(r"<pubDate>(.*?)</pubDate>",         item)
                sm = re.search(r'<source[^>]*>(.*?)</source>',      item, re.DOTALL)
                t  = _clean_text(tm.group(1)) if tm else ""
                u  = (lm.group(1).strip() if lm else "")
                # strip encoded HTML from description fully
                d  = _clean_text(dm.group(1))[:180] if dm else ""
                p  = (pm.group(1).strip()[:22]) if pm else ""
                s  = _clean_text(sm.group(1)) if sm else "Google News"
                if not t:
                    continue
                if safe and (_is_explicit(t) or _is_explicit(d)):
                    continue
                results.append({"source": s, "title": t,
                                "text": f"{d} [{p}]", "url": u})
    except Exception:
        pass

    if len(results) < 4:
        try:
            r = requests.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params={"query": query, "mode": "artlist", "maxrecords": 6,
                        "format": "json", "sort": "DateDesc"},
                timeout=8, headers={"User-Agent": _UA},
            )
            if r.status_code == 200:
                for a in r.json().get("articles", [])[:4]:
                    results.append({"source": a.get("domain", "GDELT"),
                                    "title": a.get("title", ""),
                                    "text":  a.get("seendate", "")[:16],
                                    "url":   a.get("url", "")})
        except Exception:
            pass

    q = query.lower()
    if any(k in q for k in ["tech", "ai", "software", "code", "startup", "science", "openai", "model", "llm"]):
        try:
            ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json",
                               timeout=5).json()[:8]
            for sid in ids:
                item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                                    timeout=4).json()
                if item and item.get("url"):
                    results.append({"source": "HackerNews",
                                    "title": item.get("title", ""),
                                    "text":  f"{item.get('score',0)} pts · {item.get('descendants',0)} comments",
                                    "url":   item["url"]})
                    if len(results) >= 10: break
        except Exception:
            pass
    return results[:10]


# ── Knowledge / academic ───────────────────────────────────────────────────
def search_wikipedia(query: str) -> list:
    try:
        s = requests.get("https://en.wikipedia.org/w/api.php",
                         params={"action": "query", "list": "search", "srsearch": query,
                                 "format": "json", "srlimit": 1},
                         timeout=6, headers={"User-Agent": _UA})
        if s.status_code == 200:
            hits = s.json().get("query", {}).get("search", [])
            if hits:
                title = hits[0]["title"]
                p = requests.get(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}",
                    timeout=6, headers={"User-Agent": _UA})
                if p.status_code == 200:
                    d = p.json()
                    return [{"source": "Wikipedia", "title": d.get("title", ""),
                             "text": d.get("extract", "")[:400],
                             "url":  d.get("content_urls", {}).get("desktop", {}).get("page", "")}]
    except Exception:
        pass
    return []


def search_arxiv(query: str) -> list:
    try:
        r = requests.get("https://export.arxiv.org/api/query",
                         params={"search_query": query, "max_results": 5,
                                 "sortBy": "submittedDate", "sortOrder": "descending"},
                         timeout=9, headers={"User-Agent": _UA})
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            ns   = {"a": "http://www.w3.org/2005/Atom"}
            out  = []
            for entry in root.findall("a:entry", ns)[:4]:
                title = entry.findtext("a:title", "", ns).strip().replace("\n", " ")
                summ  = entry.findtext("a:summary", "", ns).strip()[:200]
                link  = next((l.get("href", "") for l in entry.findall("a:link", ns)
                              if l.get("type") == "text/html"), "")
                out.append({"source": "ArXiv", "title": title, "text": summ, "url": link})
            return out
    except Exception:
        pass
    return []


def search_github(query: str) -> list:
    try:
        r = requests.get("https://api.github.com/search/repositories",
                         params={"q": query, "sort": "stars", "order": "desc", "per_page": 5},
                         timeout=7, headers={"User-Agent": _UA,
                                             "Accept": "application/vnd.github.v3+json"})
        if r.status_code == 200:
            return [{"source": "GitHub",
                     "title": repo.get("full_name", ""),
                     "text":  f"⭐{repo.get('stargazers_count',0):,} · {(repo.get('description') or '')[:150]}",
                     "url":   repo.get("html_url", "")}
                    for repo in r.json().get("items", [])[:5] if repo.get("full_name")]
    except Exception:
        pass
    return []


def search_devto(query: str) -> list:
    try:
        r = requests.get("https://dev.to/api/articles",
                         params={"per_page": 5, "tag": query.split()[0].lower(), "state": "fresh"},
                         timeout=7, headers={"User-Agent": _UA})
        if r.status_code == 200:
            return [{"source": "Dev.to", "title": a.get("title", ""),
                     "text": a.get("description", "")[:200], "url": a.get("url", "")}
                    for a in r.json()[:5] if a.get("title")]
    except Exception:
        pass
    return []


def search_pypi(query: str) -> list:
    try:
        r = requests.get(f"https://pypi.org/pypi/{urllib.parse.quote(query.strip())}/json",
                         timeout=6, headers={"User-Agent": _UA})
        if r.status_code == 200:
            info = r.json().get("info", {})
            return [{"source": "PyPI",
                     "title": f"{info.get('name','')} v{info.get('version','')}",
                     "text":  info.get("summary", "")[:200],
                     "url":   info.get("project_url", f"https://pypi.org/project/{query}")}]
    except Exception:
        pass
    return []


# ── Real-time data ─────────────────────────────────────────────────────────
def get_weather(query: str) -> list:
    loc = re.sub(r'\b(weather|forecast|temperature|rain|sunny|cloudy|cold|hot|humidity|wind|today|tomorrow|now|in|the|what|is|like)\b',
                 '', query, flags=re.I).strip() or "New York"
    try:
        geo = requests.get("https://nominatim.openstreetmap.org/search",
                           params={"q": loc, "format": "json", "limit": 1},
                           timeout=6, headers={"User-Agent": "ACS/1.0 (contact@acs.app)"})
        if geo.status_code == 200 and geo.json():
            g    = geo.json()[0]
            lat, lon = g["lat"], g["lon"]
            city = g.get("display_name", "").split(",")[0]
            w    = requests.get("https://api.open-meteo.com/v1/forecast",
                                params={"latitude": lat, "longitude": lon,
                                        "current_weather": True,
                                        "hourly": "precipitation_probability",
                                        "forecast_days": 1, "timezone": "auto"},
                                timeout=6)
            if w.status_code == 200:
                cw   = w.json().get("current_weather", {})
                wmap = {0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
                        45:"Foggy",51:"Light drizzle",61:"Light rain",71:"Light snow",
                        80:"Rain showers",95:"Thunderstorm"}
                return [{"source": "OpenMeteo", "title": f"Weather in {city}",
                         "text":  f"{cw.get('temperature','?')}°C · {wmap.get(cw.get('weathercode',0),'')} · Wind {cw.get('windspeed','?')} km/h",
                         "url":   "https://open-meteo.com"}]
    except Exception:
        pass
    return []


def get_crypto_prices(query: str) -> list:
    coin_map = {
        "bitcoin":"bitcoin","btc":"bitcoin","ethereum":"ethereum","eth":"ethereum",
        "solana":"solana","sol":"solana","cardano":"cardano","ada":"cardano",
        "dogecoin":"dogecoin","doge":"dogecoin","xrp":"ripple","ripple":"ripple",
        "bnb":"binancecoin","polygon":"matic-network","matic":"matic-network",
        "litecoin":"litecoin","ltc":"litecoin","shiba":"shiba-inu","shib":"shiba-inu",
    }
    q     = query.lower()
    coins = list({v for k, v in coin_map.items() if k in q}) or ["bitcoin", "ethereum", "solana"]
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                         params={"ids": ",".join(coins[:6]), "vs_currencies": "usd",
                                 "include_24hr_change": "true"},
                         timeout=8, headers={"User-Agent": _UA})
        if r.status_code == 200:
            out = []
            for cid, data in r.json().items():
                price  = data.get("usd", 0)
                change = data.get("usd_24h_change", 0) or 0
                sign   = "+" if change >= 0 else ""
                out.append({"source": "CoinGecko",
                             "title": f"{cid.capitalize()}: ${price:,.2f}",
                             "text":  f"24h: {sign}{change:.2f}%",
                             "url":   f"https://coingecko.com/en/coins/{cid}"})
            return out
    except Exception:
        pass
    return []


def get_exchange_rates(query: str) -> list:
    currencies = ["USD","EUR","GBP","JPY","INR","CNY","AUD","CAD","CHF","SGD","KRW"]
    base = next((c for c in currencies if c in query.upper()), "USD")
    try:
        r = requests.get(f"https://open.er-api.com/v6/latest/{base}", timeout=6)
        if r.status_code == 200:
            rates  = r.json().get("rates", {})
            common = [c for c in ["USD","EUR","GBP","JPY","INR","CNY","AUD","CAD"] if c != base]
            text   = " · ".join(f"{c}:{rates[c]:.3f}" for c in common if c in rates)
            return [{"source": "ExchangeRate-API",
                     "title": f"{base} exchange rates", "text": text,
                     "url":   "https://open.er-api.com"}]
    except Exception:
        pass
    return []


# ── Entertainment / lifestyle ──────────────────────────────────────────────
def search_anime(query: str) -> list:
    try:
        r = requests.get("https://api.jikan.moe/v4/anime",
                         params={"q": query, "limit": 4, "order_by": "popularity"},
                         timeout=8, headers={"User-Agent": _UA})
        if r.status_code == 200:
            return [{"source": "MyAnimeList", "title": a.get("title", ""),
                     "text":  f"Score:{a.get('score','?')} · {a.get('episodes','?')} eps · {(a.get('synopsis') or '')[:150]}",
                     "url":   a.get("url", "")}
                    for a in r.json().get("data", [])[:4] if a.get("title")]
    except Exception:
        pass
    return []


def search_open_library(query: str) -> list:
    try:
        r = requests.get("https://openlibrary.org/search.json",
                         params={"q": query, "limit": 4,
                                 "fields": "title,author_name,first_publish_year"},
                         timeout=7, headers={"User-Agent": _UA})
        if r.status_code == 200:
            return [{"source": "Open Library", "title": b.get("title", ""),
                     "text":  f"By {', '.join((b.get('author_name') or ['Unknown'])[:2])} · {b.get('first_publish_year','')}",
                     "url":   f"https://openlibrary.org/search?q={urllib.parse.quote(b.get('title',''))}"}
                    for b in r.json().get("docs", [])[:4] if b.get("title")]
    except Exception:
        pass
    return []


def search_music(query: str) -> list:
    try:
        r = requests.get("https://itunes.apple.com/search",
                         params={"term": query, "media": "music", "limit": 4, "entity": "song"},
                         timeout=7)
        if r.status_code == 200:
            return [{"source": "iTunes",
                     "title": f"{t.get('trackName','')} — {t.get('artistName','')}",
                     "text":  f"Album: {t.get('collectionName','')} · {t.get('releaseDate','')[:10]}",
                     "url":   t.get("trackViewUrl", "")}
                    for t in r.json().get("results", [])[:4] if t.get("trackName")]
    except Exception:
        pass
    return []


def get_country_info(query: str) -> list:
    loc = re.sub(r'\b(country|capital|population|currency|language|info|about|tell me|what is)\b',
                 '', query, flags=re.I).strip()
    try:
        r = requests.get(f"https://restcountries.com/v3.1/name/{urllib.parse.quote(loc)}",
                         params={"fields": "name,capital,population,currencies,languages,region"},
                         timeout=6, headers={"User-Agent": _UA})
        if r.status_code == 200:
            out = []
            for c in r.json()[:2]:
                curr = ", ".join(v.get("name", "") for v in c.get("currencies", {}).values())
                lang = ", ".join(c.get("languages", {}).values())
                out.append({"source": "REST Countries",
                             "title": c.get("name", {}).get("common", ""),
                             "text":  f"Capital: {', '.join(c.get('capital',[]))} · Pop: {c.get('population',0):,} · {lang} · {curr}",
                             "url":   ""})
            return out
    except Exception:
        pass
    return []


def search_civitai_models(query: str) -> list:
    try:
        r = requests.get("https://civitai.com/api/v1/models",
                         params={"query": query, "limit": 5, "sort": "Most Downloaded"},
                         timeout=8, headers={"User-Agent": _UA})
        if r.status_code == 200:
            return [{"source": "CivitAI", "title": m.get("name", ""),
                     "text":  (m.get("description") or "")[:200],
                     "url":   f"https://civitai.com/models/{m.get('id','')}"}
                    for m in r.json().get("items", [])[:5]]
    except Exception:
        pass
    return []


def get_fun_fact() -> list:
    try:
        r = requests.get("https://uselessfacts.jsph.pl/random.json?language=en", timeout=5)
        if r.status_code == 200:
            return [{"source": "Fun Fact", "title": "Random Fact",
                     "text": r.json().get("text", ""), "url": ""}]
    except Exception:
        pass
    return []


def search_lobsters(query: str = "") -> list:
    try:
        r = requests.get("https://lobste.rs/newest.json", timeout=6,
                         headers={"User-Agent": _UA})
        if r.status_code == 200:
            q     = query.lower()
            items = [x for x in r.json()
                     if not q or any(t in x.get("title", "").lower() for t in q.split())]
            return [{"source": "Lobsters", "title": x.get("title", ""),
                     "text":  f"⬆{x.get('score',0)} · {', '.join(x.get('tags',[]))}",
                     "url":   x.get("url", x.get("comments_url", ""))}
                    for x in items[:4]]
    except Exception:
        pass
    return []


# ── Reddit ─────────────────────────────────────────────────────────────────
def search_reddit(query: str, subreddit: str = "") -> list:
    """Reddit public JSON API — no auth required for read."""
    try:
        if subreddit:
            url    = f"https://www.reddit.com/r/{subreddit}/search.json"
            params = {"q": query, "restrict_sr": "on", "sort": "relevance", "limit": 5, "t": "all"}
        else:
            url    = "https://www.reddit.com/search.json"
            params = {"q": query, "sort": "relevance", "limit": 6, "t": "all", "type": "link"}
        r = requests.get(url, params=params, timeout=8,
                         headers={"User-Agent": "ACS/1.0 search-aggregator (local)"})
        if r.status_code == 200:
            posts = r.json().get("data", {}).get("children", [])
            return [
                {"source": f"Reddit/r/{p['data'].get('subreddit','')}",
                 "title": p["data"].get("title", ""),
                 "text":  f"⬆{p['data'].get('score',0):,} · {p['data'].get('num_comments',0)} comments",
                 "url":   "https://reddit.com" + p["data"].get("permalink", "")}
                for p in posts if p.get("data", {}).get("title")
            ][:5]
    except Exception:
        pass
    return []


# ── Twitter / X via Nitter ─────────────────────────────────────────────────
NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.1d4.us",
    "https://n.l5.ca",
    "https://nitter.cz",
    "https://twiiit.com",
    "https://nitter.space",
    "https://nitter.mint.lgbt",
    "https://nitter.bird.froth.zone",
]
_nitter_cache: dict = {"instance": None, "checked": 0.0}

def _get_nitter_instance() -> str | None:
    c = _nitter_cache
    if c["instance"] and (time.time() - c["checked"]) < 300:
        return c["instance"]
    for inst in NITTER_INSTANCES:
        try:
            r = requests.head(inst, timeout=4, headers={"User-Agent": _UA},
                              allow_redirects=True)
            if r.status_code < 400:
                c.update({"instance": inst, "checked": time.time()})
                return inst
        except Exception:
            continue
    return None

def search_twitter(query: str) -> list:
    """Search Twitter/X via Nitter open-source frontend."""
    inst = _get_nitter_instance()
    if not inst:
        return []
    try:
        r = requests.get(f"{inst}/search",
                         params={"q": query, "f": "tweets"},
                         timeout=10, headers={"User-Agent": _UA})
        if r.status_code == 200:
            results = []
            # Extract tweet text blocks (class varies by instance)
            content_blocks = re.findall(
                r'class="[^"]*tweet-content[^"]*"[^>]*>([\s\S]*?)</div>', r.text)
            usernames  = re.findall(r'class="username"[^>]*>\s*@?([^\s<]+)', r.text)
            tweet_links = re.findall(r'class="[^"]*tweet-link[^"]*"\s+href="([^"]+)"', r.text)
            for i, block in enumerate(content_blocks[:8]):
                text = re.sub(r'<[^>]+>', '', block).strip()
                if not text or len(text) < 10:
                    continue
                user = usernames[i].strip() if i < len(usernames) else ""
                path = tweet_links[i].strip() if i < len(tweet_links) else ""
                url  = f"https://x.com{path.replace(inst, '')}" if path else ""
                results.append({
                    "source": "X/Twitter",
                    "title":  f"@{user}: {text[:80]}" if user else text[:80],
                    "text":   text[:220],
                    "url":    f"{inst}{path}" if path.startswith("/") else url,
                })
                if len(results) == 5:
                    break
            return results
    except Exception:
        pass
    return []


# ── Instagram via public viewers ───────────────────────────────────────────
def search_instagram(query: str) -> list:
    """Search Instagram via imginn / picuki viewer (no login required)."""
    # Strategy 1: imginn.com
    try:
        r = requests.get("https://imginn.com/search/",
                         params={"q": query}, timeout=10,
                         headers={"User-Agent": _UA, "Referer": "https://imginn.com/"})
        if r.status_code == 200:
            handles = re.findall(r'href="/([A-Za-z0-9_.]+)/"\s[^>]*', r.text)
            names   = re.findall(r'class="[^"]*name[^"]*"[^>]*>(.*?)</(?:p|span|div|h)', r.text, re.DOTALL)
            results = []
            for i, h in enumerate(dict.fromkeys(handles[:6])):  # deduplicate
                n = re.sub(r'<[^>]+>', '', names[i]).strip() if i < len(names) else ""
                results.append({
                    "source": "Instagram",
                    "title":  f"@{h}" + (f"  —  {n}" if n and n != h else ""),
                    "text":   "",
                    "url":    f"https://www.instagram.com/{h}/",
                })
            if results:
                return results
    except Exception:
        pass
    # Strategy 2: picuki.com
    try:
        r = requests.get(f"https://www.picuki.com/search/{urllib.parse.quote(query)}",
                         timeout=10, headers={"User-Agent": _UA})
        if r.status_code == 200:
            users = re.findall(r'href="/profile/([A-Za-z0-9_.]+)"', r.text)
            names = re.findall(r'class="profile-name[^"]*"[^>]*>(.*?)</(?:h2|h3|div|p)', r.text, re.DOTALL)
            return [
                {"source": "Instagram",
                 "title":  f"@{u}" + (f"  —  {re.sub(chr(60)+'[^>]+>','',names[i]).strip()}" if i < len(names) else ""),
                 "text":   "",
                 "url":    f"https://www.instagram.com/{u}/"}
                for i, u in enumerate(dict.fromkeys(users[:6]))
            ]
    except Exception:
        pass
    return []



# ── Page reader ────────────────────────────────────────────────────────────
def fetch_page_content(url: str, max_chars: int = 2000) -> str:
    """Fetch a URL and return readable plain text (no API key needed)."""
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": _UA})
        if r.status_code != 200:
            return ""
        text = re.sub(r'<style[^>]*>.*?</style>', '', r.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'(Cookie Policy|Accept All|Privacy Policy|Subscribe|Newsletter).{0,100}',
                      '', text, flags=re.I)
        return text.strip()[:max_chars]
    except Exception:
        return ""


def search_huggingface(query: str) -> list:
    """Search Hugging Face models (free public API)."""
    try:
        r = requests.get("https://huggingface.co/api/models",
                         params={"search": query, "limit": 6, "sort": "downloads", "direction": -1},
                         timeout=8, headers={"User-Agent": _UA})
        if r.status_code != 200:
            return []
        out = []
        for m in r.json()[:6]:
            mid = m.get("id") or m.get("modelId") or ""
            if not mid:
                continue
            dl = m.get("downloads", 0)
            out.append({"source": "HuggingFace", "title": mid,
                        "text": f"{dl:,} downloads · {m.get('pipeline_tag','model')}",
                        "url": f"https://huggingface.co/{mid}"})
        return out
    except Exception:
        return []


# ── Combined search (called by chat routes) ────────────────────────────────
def combined_search(query: str, safe: bool = True) -> list:
    results = search_searxng(query, safe) + search_ddg(query, safe)
    results += search_news(query, safe)          # always include news
    q = query.lower()

    if any(k in q for k in ["youtube","tutorial","how to","watch","review","demo","video","trending"]):
        yt = search_youtube_trending() if ("trending" in q and "search" not in q) else search_youtube(query, safe)
        # If user asks for comments/description, fetch top comments for first result
        if any(k in q for k in ["comment","comments","what do people say","reactions","description","desc"]):
            inst = _get_invidious_instance()
            for v in yt[:1]:
                vid = v.get("video_id") or ""
                if vid:
                    cmt = fetch_youtube_comments(vid, inst)
                    if cmt:
                        v["text"] = v.get("text","") + f"\nTop comments:\n{cmt}"
        results += yt

    if any(k in q for k in ["what is","who is","who was","explain","define","meaning of","history of",
                              "invented","discovered","born","died","wikipedia"]):
        results += search_wikipedia(query)

    if any(k in q for k in ["research","paper","arxiv","study","academic","published","machine learning",
                              "neural network","transformer","diffusion model","ai model"]):
        results += search_arxiv(query)

    if any(k in q for k in ["dev.to","tutorial","programming","coding","developer","frontend","backend",
                              "react","python","javascript","typescript","rust","golang","nextjs"]):
        results += search_devto(query)

    if any(k in q for k in ["weather","forecast","temperature","rain","sunny","cloudy","wind","humidity",
                              "cold","hot","snow","storm"]):
        results += get_weather(query)

    if any(k in q for k in ["crypto","bitcoin","btc","ethereum","eth","solana","dogecoin","price","coin",
                              "blockchain","defi","nft","token","binance","coingecko"]):
        results += get_crypto_prices(query)

    if any(k in q for k in ["exchange rate","currency","usd","eur","gbp","inr","jpy","forex","convert",
                              "dollar","euro","pound","rupee","yen"]):
        results += get_exchange_rates(query)

    if any(k in q for k in ["anime","manga","myanimelist","jikan","isekai","one piece","naruto","attack on titan"]):
        results += search_anime(query)

    if any(k in q for k in ["github","repo","repository","open source","stars","fork","library","framework","sdk"]):
        results += search_github(query)

    if any(k in q for k in ["book","novel","author","isbn","fiction","biography","bestseller"]):
        results += search_open_library(query)

    if any(k in q for k in ["song","music","artist","album","band","singer","track","spotify","itunes"]):
        results += search_music(query)

    if any(k in q for k in ["country","capital","population","flag","currency of","language of","nation"]):
        results += get_country_info(query)

    if any(k in q for k in ["pypi","pip install","python package","python library","module"]):
        results += search_pypi(query)

    if any(k in q for k in ["model","lora","checkpoint","civitai","safetensors","gguf","download"]):
        results += search_civitai_models(query)

    if any(k in q for k in ["lobsters","hacker news","tech news","programming news","dev news"]):
        results += search_lobsters(query)

    if any(k in q for k in ["fun fact","random fact","did you know","trivia"]):
        results += get_fun_fact()

    # Social platforms
    if any(k in q for k in ["reddit","r/","subreddit","upvote","karma","ama"]):
        results += search_reddit(query)
    elif any(k in q for k in ["discussion","community","what do people think","thoughts on","opinion on"]):
        results += search_reddit(query)

    if any(k in q for k in ["twitter","tweet","x.com","trending on twitter","elon musk post","viral tweet","retweet"]):
        results += search_twitter(query)

    if any(k in q for k in ["instagram","insta post","ig post","instagram reel","influencer"]):
        results += search_instagram(query)

    if any(k in q for k in ["huggingface","hugging face","hf model","hf dataset","transformers library",
                              "bert","gpt","llama","mistral","flux model","stable diffusion download",
                              "model card","safetensors download","gguf download","ai model hub"]):
        results += search_huggingface(query)


    # Deduplicate by URL/title
    seen, unique = set(), []
    for r in results:
        key = r.get("url") or r.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:20]
