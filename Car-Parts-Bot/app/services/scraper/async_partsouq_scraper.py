# import asyncio
# import aiohttp
# import urllib.parse
# import time
# from typing import Dict, List, Optional
# from bs4 import BeautifulSoup
# from rapidfuzz import process, fuzz
# from urllib.parse import urljoin

# # ---------------- CONFIG ----------------

# BASE_URL = "https://partsouq.com"
# MAX_DEPTH = 3   # reduced for speed

# SCRAPE_DO_TOKEN = "df06f5d1c7a34c0cb706c4d6c745e2249da1d30fbb9"
# SCRAPE_DO_API = "http://api.scrape.do"

# CATEGORY_MAP = {
#     "anti-freeze": ["cooling", "radiator", "maintenance"],
#     "oil": ["lubrication", "engine", "maintenance", "service"],
#     "oil filter": ["lubrication", "oil supply", "filter", "maintenance"],
#     "brake": ["brake", "wheel", "caliper"],
#     "brake pad": ["brake", "lining", "repair kit"],
#     "belt": ["belt drive", "cooling", "alternator"],
#     "spark plug": ["ignition", "engine electric"],
#     "suspension": ["front axle", "rear axle", "steering"],
#     "shock": ["suspension", "damper", "strut"],
# }

# LINK_BLACKLIST = ["home", "search", "back", "next", "previous"]

# HEADERS = {
#     "User-Agent": "Mozilla/5.0",
#     "Accept-Language": "en-US,en;q=0.9",
# }

# # ---------------- CACHE ----------------

# RESULT_CACHE: Dict[str, tuple] = {}
# RESULT_CACHE_TTL = 60 * 60        # 1 hour

# PAGE_CACHE: Dict[str, tuple] = {}
# PAGE_CACHE_TTL = 10 * 60          # 10 minutes


# def _expired(ts: float, ttl: int) -> bool:
#     return (time.time() - ts) > ttl


# # ---------------- SCRAPER ----------------

# class AsyncPartSouqScraper:

#     async def _get(self, session, target_url, render=False):
#         cache_key = f"{target_url}|render={render}"

#         cached = PAGE_CACHE.get(cache_key)
#         if cached:
#             ts, soup = cached
#             if not _expired(ts, PAGE_CACHE_TTL):
#                 return soup
#             del PAGE_CACHE[cache_key]

#         encoded = urllib.parse.quote(target_url, safe="")
#         scrape_url = (
#             f"{SCRAPE_DO_API}"
#             f"?token={SCRAPE_DO_TOKEN}"
#             f"&url={encoded}"
#             f"&super=true"
#         )

#         if render:
#             scrape_url += "&render=true"

#         try:
#             async with session.get(scrape_url, headers=HEADERS) as resp:
#                 if resp.status != 200:
#                     return None
#                 html = await resp.text()
#                 soup = BeautifulSoup(html, "html.parser")
#                 PAGE_CACHE[cache_key] = (time.time(), soup)
#                 return soup
#         except Exception:
#             return None

#     # ---------------- PUBLIC API ----------------

#     async def search_part(self, vin: str, part_name: str) -> Dict:
#         part_name = part_name.lower().strip()
#         visited = set()

#         result_key = f"{vin}:{part_name}"
#         cached = RESULT_CACHE.get(result_key)
#         if cached:
#             ts, data = cached
#             if not _expired(ts, RESULT_CACHE_TTL):
#                 return data
#             del RESULT_CACHE[result_key]

#         timeout = aiohttp.ClientTimeout(total=60)

#         async with aiohttp.ClientSession(timeout=timeout) as session:
#             soup = await self._get(
#                 session,
#                 f"{BASE_URL}/en/search/all?q={vin}",
#                 render=True
#             )
#             if not soup:
#                 return {"error": "VIN not found or blocked"}

#             anchors = soup.select("div.caption a, td a, a[href*='cid=']")
#             link_map = {
#                 a.get_text(" ", strip=True): urljoin(BASE_URL, a.get("href"))
#                 for a in anchors if a.get("href")
#             }

#             targets = self._identify_targets(part_name, link_map)
#             if not targets:
#                 return {"error": "No matching diagram"}

#             keywords = part_name.split()

#             tasks = [
#                 asyncio.create_task(
#                     self._recursive_dive(
#                         session, url, keywords, 1, visited
#                     )
#                 )
#                 for _, url, _ in targets
#             ]

#             done, pending = await asyncio.wait(
#                 tasks, return_when=asyncio.FIRST_COMPLETED
#             )

#             for p in pending:
#                 p.cancel()

#             flat_parts = []
#             for d in done:
#                 flat_parts.extend(d.result())

#             verified = self._verify_relevance(flat_parts, part_name)
#             if not verified:
#                 return {"error": "No matching parts found"}

#             result = {
#                 "vin": vin,
#                 "query": part_name,
#                 "parts": verified,
#             }

#             RESULT_CACHE[result_key] = (time.time(), result)
#             return result

#     # ---------------- CATEGORY LOGIC ----------------

#     def _identify_targets(self, query: str, link_map: Dict[str, str]):
#         targets = []
#         q = query.lower()

#         for key, synonyms in CATEGORY_MAP.items():
#             if key in q:
#                 for syn in synonyms:
#                     match = process.extractOne(
#                         syn, link_map.keys(), scorer=fuzz.token_set_ratio
#                     )
#                     if match and match[1] > 60:
#                         targets.append((match[0], link_map[match[0]], match[1]))

#         matches = process.extract(
#             query, link_map.keys(), scorer=fuzz.token_set_ratio, limit=5
#         )
#         for name, score, _ in matches:
#             if score > 55:
#                 targets.append((name, link_map[name], score))

#         seen = set()
#         unique = []
#         for n, u, s in targets:
#             if u not in seen:
#                 unique.append((n, u, s))
#                 seen.add(u)

#         unique.sort(key=lambda x: x[2], reverse=True)
#         return unique[:3]

#     # ---------------- RECURSIVE DIVE ----------------

#     async def _recursive_dive(self, session, url, keywords, depth, visited):
#         if depth > MAX_DEPTH or url in visited:
#             return []

#         visited.add(url)
#         soup = await self._get(session, url)
#         if not soup:
#             return []

#         parts = []
#         for r in soup.select("table tr"):
#             cols = r.find_all("td")
#             if len(cols) < 2:
#                 continue
#             a = cols[0].find("a")
#             if not a:
#                 continue

#             num = a.get_text(strip=True)
#             name = cols[1].get_text(" ", strip=True)

#             if num and name:
#                 parts.append({"number": num, "name": name})

#         if parts:
#             return parts

#         candidates = []
#         for a in soup.select("div.caption a, td.illustration a"):
#             text = a.get_text(" ", strip=True).lower()
#             href = a.get("href")
#             if not text or not href:
#                 continue
#             if any(b in text for b in LINK_BLACKLIST):
#                 continue

#             score = fuzz.partial_ratio(" ".join(keywords), text)
#             if any(k in text for k in keywords):
#                 score += 50
#             if score > 50:
#                 candidates.append((score, urljoin(BASE_URL, href)))

#         candidates.sort(reverse=True)

#         for _, next_url in candidates[:3]:
#             res = await self._recursive_dive(
#                 session, next_url, keywords, depth + 1, visited
#             )
#             if res:
#                 return res

#         return []

#     # ---------------- FINAL FILTER ----------------

#     def _verify_relevance(self, parts, query):
#         verified = []
#         q = query.lower()
#         keys = q.split()

#         for p in parts:
#             name = p["name"].lower()
#             num = p["number"].lower()

#             if (
#                 q in num
#                 or all(k in name for k in keys)
#                 or fuzz.partial_ratio(q, name) > 65
#             ):
#                 verified.append(p)

#         return verified


# # ---------------- SINGLETON ----------------

# _scraper_instance: Optional[AsyncPartSouqScraper] = None

# def get_scraper() -> AsyncPartSouqScraper:
#     global _scraper_instance
#     if _scraper_instance is None:
#         _scraper_instance = AsyncPartSouqScraper()
#     return _scraper_instance
import asyncio
import aiohttp
import urllib.parse
import time
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
from urllib.parse import urljoin

# ---------------- CONFIG ----------------

BASE_URL = "https://partsouq.com"
MAX_DEPTH = 3

SCRAPE_DO_API = "http://api.scrape.do"

SCRAPE_DO_TOKENS = [
    "b8b82944bdde4e5e84d9ef4379bf4cc64521475f2ef",#aditya
    "92bfe481a83b4ecaaf25ce81169aeb33c6e4520174a",#client account
    "4faceb5bd9a04e57bc54ecb9cedf0215e10d0e18fe3",#mann.soni@koncpt.ai
    "edbbff97228147c4b05fbb1f809eee93e62420330ab",
    "145c2d55e6df46faaabae263f3a788a4f8d6c8d2441",
    "5a1d4c188e984a31a895675264b7f16e6e04b00cb25",
]

CATEGORY_MAP = {
    "anti-freeze": ["cooling", "radiator", "maintenance"],
    "oil": ["lubrication", "engine", "maintenance", "service"],
    "oil filter": ["lubrication", "oil supply", "filter", "maintenance"],
    "brake": ["brake", "wheel", "caliper"],
    "brake pad": ["brake", "lining", "repair kit"],
    "belt": ["belt drive", "cooling", "alternator"],
    "spark plug": ["ignition", "engine electric"],
    "suspension": ["front axle", "rear axle", "steering"],
    "shock": ["suspension", "damper", "strut"],
}

LINK_BLACKLIST = ["home", "search", "back", "next", "previous"]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}

# ---------------- CACHE ----------------

RESULT_CACHE: Dict[str, tuple] = {}
RESULT_CACHE_TTL = 60 * 60

PAGE_CACHE: Dict[str, tuple] = {}
PAGE_CACHE_TTL = 10 * 60


def _expired(ts: float, ttl: int) -> bool:
    return (time.time() - ts) > ttl


# ---------------- TOKEN SWITCH LOGIC ----------------

class TokenState:
    def __init__(self, token: str, idx: int):
        self.token = token
        self.idx = idx
        self.exhausted = False
        self.last_used = 0

    def short(self):
        return self.token[:6] + "..."


TOKEN_POOL = [
    TokenState(t, i)
    for i, t in enumerate(SCRAPE_DO_TOKENS, start=1)
]


def get_next_token() -> TokenState:
    active = [t for t in TOKEN_POOL if not t.exhausted]
    if not active:
        raise RuntimeError("ALL SCRAPE.DO TOKENS EXHAUSTED")

    token = min(active, key=lambda t: t.last_used)
    token.last_used = time.time()
    print(f"[TOKEN] Using token #{token.idx} ({token.short()})")
    return token


def is_quota_error(status: int, body: str) -> bool:
    if status in (401, 402, 403, 429):
        body = body.lower()
        return any(x in body for x in ["quota", "credit", "limit", "exceeded"])
    return False


# ---------------- SCRAPER ----------------

class AsyncPartSouqScraper:

    async def _get(self, session, target_url, render=False):
        cache_key = f"{target_url}|render={render}"

        cached = PAGE_CACHE.get(cache_key)
        if cached:
            ts, soup = cached
            if not _expired(ts, PAGE_CACHE_TTL):
                return soup
            del PAGE_CACHE[cache_key]

        encoded = urllib.parse.quote(target_url, safe="")
        attempts = 0

        while attempts < len(TOKEN_POOL):
            token_state = get_next_token()
            attempts += 1

            scrape_url = (
                f"{SCRAPE_DO_API}"
                f"?token={token_state.token}"
                f"&url={encoded}"
                f"&render=true"
            )

            try:
                async with session.get(scrape_url, headers=HEADERS) as resp:
                    html = await resp.text()

                    if is_quota_error(resp.status, html):
                        token_state.exhausted = True
                        print(
                            f"[TOKEN] Token #{token_state.idx} "
                            f"({token_state.short()}) exhausted → switching"
                        )
                        continue

                    if resp.status != 200:
                        return None

                    soup = BeautifulSoup(html, "html.parser")
                    PAGE_CACHE[cache_key] = (time.time(), soup)
                    return soup

            except Exception:
                return None

        raise RuntimeError("All tokens exhausted or blocked")

    # ---------------- PUBLIC API ----------------

    async def search_part(self, vin: str, part_name: str) -> Dict:
        part_name = part_name.lower().strip()
        visited = set()

        result_key = f"{vin}:{part_name}"
        cached = RESULT_CACHE.get(result_key)
        if cached:
            ts, data = cached
            if not _expired(ts, RESULT_CACHE_TTL):
                return data
            del RESULT_CACHE[result_key]

        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            soup = await self._get(
                session,
                f"{BASE_URL}/en/search/all?q={vin}",
                render=True
            )
            if not soup:
                return {"error": "VIN not found or blocked"}

            anchors = soup.select("div.caption a, td a, a[href*='cid=']")
            link_map = {
                a.get_text(" ", strip=True): urljoin(BASE_URL, a.get("href"))
                for a in anchors if a.get("href")
            }

            targets = self._identify_targets(part_name, link_map)
            if not targets:
                return {"error": "No matching diagram"}

            keywords = part_name.split()

            tasks = [
                asyncio.create_task(
                    self._recursive_dive(
                        session, url, keywords, 1, visited
                    )
                )
                for _, url, _ in targets
            ]

            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            for p in pending:
                p.cancel()

            flat_parts = []
            for d in done:
                flat_parts.extend(d.result())

            verified = self._verify_relevance(flat_parts, part_name)
            if not verified:
                return {"error": "No matching parts found"}

            result = {
                "vin": vin,
                "query": part_name,
                "parts": verified,
            }

            RESULT_CACHE[result_key] = (time.time(), result)
            return result

    # ---------------- CATEGORY LOGIC ----------------

    def _identify_targets(self, query: str, link_map: Dict[str, str]):
        targets = []
        q = query.lower()

        for key, synonyms in CATEGORY_MAP.items():
            if key in q:
                for syn in synonyms:
                    match = process.extractOne(
                        syn, link_map.keys(), scorer=fuzz.token_set_ratio
                    )
                    if match and match[1] > 60:
                        targets.append((match[0], link_map[match[0]], match[1]))

        matches = process.extract(
            query, link_map.keys(), scorer=fuzz.token_set_ratio, limit=5
        )
        for name, score, _ in matches:
            if score > 55:
                targets.append((name, link_map[name], score))

        seen = set()
        unique = []
        for n, u, s in targets:
            if u not in seen:
                unique.append((n, u, s))
                seen.add(u)

        unique.sort(key=lambda x: x[2], reverse=True)
        return unique[:3]

    # ---------------- RECURSIVE DIVE ----------------

    async def _recursive_dive(self, session, url, keywords, depth, visited):
        if depth > MAX_DEPTH or url in visited:
            return []

        visited.add(url)
        soup = await self._get(session, url)
        if not soup:
            return []

        parts = []
        for r in soup.select("table tr"):
            cols = r.find_all("td")
            if len(cols) < 2:
                continue
            a = cols[0].find("a")
            if not a:
                continue

            num = a.get_text(strip=True)
            name = cols[1].get_text(" ", strip=True)

            if num and name:
                parts.append({"number": num, "name": name})

        if parts:
            return parts

        candidates = []
        for a in soup.select("div.caption a, td.illustration a"):
            text = a.get_text(" ", strip=True).lower()
            href = a.get("href")
            if not text or not href:
                continue
            if any(b in text for b in LINK_BLACKLIST):
                continue

            score = fuzz.partial_ratio(" ".join(keywords), text)
            if any(k in text for k in keywords):
                score += 50
            if score > 50:
                candidates.append((score, urljoin(BASE_URL, href)))

        candidates.sort(reverse=True)

        for _, next_url in candidates[:3]:
            res = await self._recursive_dive(
                session, next_url, keywords, depth + 1, visited
            )
            if res:
                return res

        return []

    # ---------------- FINAL FILTER ----------------

    def _verify_relevance(self, parts, query):
        verified = []
        q = query.lower()
        keys = q.split()

        for p in parts:
            name = p["name"].lower()
            num = p["number"].lower()

            if (
                q in num
                or all(k in name for k in keys)
                or fuzz.partial_ratio(q, name) > 65
            ):
                verified.append(p)

        return verified


# ---------------- SINGLETON ----------------

_scraper_instance: Optional[AsyncPartSouqScraper] = None

def get_scraper() -> AsyncPartSouqScraper:
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = AsyncPartSouqScraper()
    return _scraper_instance
