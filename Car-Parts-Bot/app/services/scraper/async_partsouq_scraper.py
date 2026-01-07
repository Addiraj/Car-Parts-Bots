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



# import asyncio
# import aiohttp
# import urllib.parse
# import time
# from typing import Dict, List, Optional
# from bs4 import BeautifulSoup
# from rapidfuzz import process, fuzz
# from urllib.parse import urljoin
# import os
# from dotenv import load_dotenv

# load_dotenv()

# # ---------------- CONFIG ----------------

# BASE_URL = "https://partsouq.com"
# MAX_DEPTH = 3

# SCRAPE_DO_API = "http://api.scrape.do"

# SCRAPE_DO_TOKENS = [
#     t.strip()
#     for t in os.getenv("SCRAPE_DO_TOKENS", "").split(",")
#     if t.strip()
# ]
# if not SCRAPE_DO_TOKENS:
#     raise RuntimeError("SCRAPE_DO_TOKENS not found in .env file")


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
# RESULT_CACHE_TTL = 60 * 60

# PAGE_CACHE: Dict[str, tuple] = {}
# PAGE_CACHE_TTL = 10 * 60


# def _expired(ts: float, ttl: int) -> bool:
#     return (time.time() - ts) > ttl


# # ---------------- TOKEN SWITCH LOGIC ----------------

# class TokenState:
#     def __init__(self, token: str, idx: int):
#         self.token = token
#         self.idx = idx
#         self.exhausted = False
#         self.last_used = 0

#     def short(self):
#         return self.token[:6] + "..."


# TOKEN_POOL = [
#     TokenState(t, i)
#     for i, t in enumerate(SCRAPE_DO_TOKENS, start=1)
# ]


# def get_next_token() -> TokenState:
#     active = [t for t in TOKEN_POOL if not t.exhausted]
#     if not active:
#         raise RuntimeError("ALL SCRAPE.DO TOKENS EXHAUSTED")

#     token = min(active, key=lambda t: t.last_used)
#     token.last_used = time.time()
#     print(f"[TOKEN] Using token #{token.idx} ({token.short()})")
#     return token


# def is_quota_error(status: int, body: str) -> bool:
#     if status in (401, 402, 403, 429):
#         body = body.lower()
#         return any(x in body for x in ["quota", "credit", "limit", "exceeded"])
#     return False


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
#         attempts = 0

#         while attempts < len(TOKEN_POOL):
#             token_state = get_next_token()
#             attempts += 1

#             scrape_url = (
#                 f"{SCRAPE_DO_API}"
#                 f"?token={token_state.token}"
#                 f"&url={encoded}"
#                 f"&render=true"
#             )

#             try:
#                 async with session.get(scrape_url, headers=HEADERS) as resp:
#                     html = await resp.text()

#                     if is_quota_error(resp.status, html):
#                         token_state.exhausted = True
#                         print(
#                             f"[TOKEN] Token #{token_state.idx} "
#                             f"({token_state.short()}) exhausted → switching"
#                         )
#                         continue

#                     if resp.status != 200:
#                         return None

#                     soup = BeautifulSoup(html, "html.parser")
#                     PAGE_CACHE[cache_key] = (time.time(), soup)
#                     return soup

#             except Exception:
#                 return None

#         raise RuntimeError("All tokens exhausted or blocked")

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



#OIL FILTER SCRAPER (SYNC VERSION)
import requests
import time
import os
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dotenv import load_dotenv

load_dotenv()

# ================= CONFIG =================

BASE_URL = "https://partsouq.com"
SCRAPER_API_BASE = "http://api.scraperapi.com"

SCRAPER_API_KEYS = [
    k.strip()
    for k in os.getenv("SCRAPE_DO_TOKENS", "").split(",")
    if k.strip()
]

if not SCRAPER_API_KEYS:
    raise RuntimeError("SCRAPER_API_KEYS missing")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TARGET_DIAGRAMS = ["oil filter", "filter element", "oil supply"]

# ================= TOKEN ROTATION =================

class Token:
    def __init__(self, key: str, idx: int):
        self.key = key
        self.idx = idx
        self.last_used = 0

    def short(self):
        return self.key[:6] + "..."


TOKENS = [Token(k, i) for i, k in enumerate(SCRAPER_API_KEYS, 1)]


def get_token() -> Token:
    t = min(TOKENS, key=lambda x: x.last_used)
    t.last_used = time.time()
    print(f"[TOKEN] Using #{t.idx} ({t.short()})")
    return t


# ================= SCRAPER =================

class PartSouqScraper:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get(self, target_url: str) -> Optional[BeautifulSoup]:
        token = get_token()

        params = {
            "api_key": token.key,
            "url": target_url,
        }
        # print(f"[+] Fetching: {target_url} with token #{token.idx}")
        # print(f"[*] Fetching: {target_url}")

        try:
            resp = self.session.get(
                SCRAPER_API_BASE,
                params=params,
                timeout=60,
                allow_redirects=True,
            )
            print("[*] Response URL:", resp.url)
            print("STATUS:", resp.status_code)

            if resp.status_code != 200 or not resp.text.strip():
                return None

            return BeautifulSoup(resp.text, "html.parser")

        except Exception as e:
            print(f"[!] Network error: {e}")
            return None

    # ================= PUBLIC API =================
    # METHOD NAME KEPT SAME (but now sync)
    def search_part(self, vin: str, part_name: str) -> Dict:

        # ─────────────────────────────
        # 1️⃣ SEARCH VIN
        # ─────────────────────────────
        search_url = f"{BASE_URL}/search?q={vin}"
        soup = self._get(search_url)
        # print(search_url)
        if not soup:
            return {"error": "VIN search failed"}

        # ─────────────────────────────
        # 2️⃣ FIND LUBRICATION SECTION
        # ─────────────────────────────
        lubrication_link = None

        for a in soup.select("div.caption a, td a"):
            text = a.get_text(" ", strip=True).lower()
            href = a.get("href")
            # print(f"Checking link text: {text}")
            # print(f"href: {href}")
            if href and ("lubrication" in text or "oil supply" in text):
                lubrication_link = urljoin(BASE_URL, href)
                print(f"[+] Found Section: {text.title()}")
                break

        if not lubrication_link:
            return {"error": "Lubrication section not found"}

        # normalize
        lubrication_link = lubrication_link.replace("/en/", "/")

        # ─────────────────────────────
        # 3️⃣ LOAD LUBRICATION PAGE
        # ─────────────────────────────
        soup_lub = self._get(lubrication_link)

        if not soup_lub:
            return {"error": "Failed to load lubrication page"}

        # ─────────────────────────────
        # 4️⃣ FIND OIL FILTER DIAGRAM
        # ─────────────────────────────
        diagram_link = None

        for a in soup_lub.select("div.caption a, td a"):
            text = a.get_text(" ", strip=True).lower()
            href = a.get("href")

            if not href:
                continue

            if any(t in text for t in TARGET_DIAGRAMS):
                if "microfilter" in text:
                    continue
                diagram_link = urljoin(BASE_URL, href)
                print(f"[+] Found Diagram: {text.title()}")
                break

        if not diagram_link:
            return {"error": "Oil filter diagram not found"}

        diagram_link = diagram_link.replace("/en/", "/")

        # ─────────────────────────────
        # 5️⃣ LOAD PARTS DIAGRAM
        # ─────────────────────────────
        soup_parts = self._get(diagram_link)

        if not soup_parts:
            return {"error": "Failed to load parts diagram"}

        # ─────────────────────────────
        # 6️⃣ EXTRACT PARTS
        # ─────────────────────────────
        parts: List[Dict] = []

        for row in soup_parts.select("table tr"):
            cols = row.select("td")
            if len(cols) < 2:
                continue

            a = cols[0].select_one("a")
            if not a:
                continue

            number = a.get_text(strip=True)
            name = cols[1].get_text(" ", strip=True)

            if "filter" in name.lower() or "element" in name.lower():
                parts.append({
                    "number": number,
                    "name": name
                })

        return {
            "vin": vin,
            "query": part_name,
            "parts": parts
        }


# ================= SINGLETON =================

_scraper: Optional[PartSouqScraper] = None


def get_scraper() -> PartSouqScraper:
    global _scraper
    if _scraper is None:
        _scraper = PartSouqScraper()
    return _scraper

# import requests
# import time
# import os
# from typing import Dict, Optional, List, Tuple
# from bs4 import BeautifulSoup
# from urllib.parse import urljoin
# from dotenv import load_dotenv
# import re

# load_dotenv()

# # ================= CONFIG =================

# BASE_URL = "https://partsouq.com"
# SCRAPER_API_BASE = "http://api.scraperapi.com"

# SCRAPER_API_KEYS = [
#     k.strip()
#     for k in os.getenv("SCRAPE_DO_TOKENS", "").split(",")
#     if k.strip()
# ]

# if not SCRAPER_API_KEYS:
#     raise RuntimeError("SCRAPER_API_KEYS missing")

# HEADERS = {
#     "User-Agent": (
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#         "AppleWebKit/537.36 (KHTML, like Gecko) "
#         "Chrome/91.0.4472.124 Safari/537.36"
#     ),
#     "Accept-Language": "en-US,en;q=0.9",
# }

# # ================= PART CONFIG =================

# PART_CONFIG = {
#     "oil filter": {
#         "section": ["lubrication", "oil supply", "maintenance"],
#         "diagram": ["oil filter", "filter element", "oil supply"],
#         "part_name": ["filter", "element"]
#     },
#     "brake pad": {
#         "section": ["brake service", "brakes", "maintenance"],
#         "diagram": ["front brake", "rear brake", "brake pad", "caliper"],
#         "part_name": ["pad", "lining", "repair kit"]
#     },
#     "brake disc": {
#         "section": ["brake service", "brakes"],
#         "diagram": ["front brake", "rear brake"],
#         "part_name": ["disc", "rotor"]
#     },
#     "spark plug": {
#         "section": ["ignition", "engine electrical"],
#         "diagram": ["ignition", "spark plug"],
#         "part_name": ["spark", "plug"]
#     },
#     "belt": {
#         "section": ["belt drive", "engine"],
#         "diagram": ["belt", "drive"],
#         "part_name": ["belt", "ribbed"]
#     }
# }

# # ================= TOKEN ROTATION =================

# class Token:
#     def __init__(self, key: str, idx: int):
#         self.key = key
#         self.idx = idx
#         self.last_used = 0

#     def short(self):
#         return self.key[:6] + "..."


# TOKENS = [Token(k, i) for i, k in enumerate(SCRAPER_API_KEYS, 1)]


# def get_token() -> Token:
#     t = min(TOKENS, key=lambda x: x.last_used)
#     t.last_used = time.time()
#     print(f"[TOKEN] Using #{t.idx} ({t.short()})")
#     return t


# # ================= SCRAPER =================

# class PartSouqScraper:

#     def __init__(self):
#         self.session = requests.Session()
#         self.session.headers.update(HEADERS)

#     # ---------- internal fetch ----------
#     def _get(self, target_url: str) -> Optional[BeautifulSoup]:
#         token = get_token()

#         params = {
#             "api_key": token.key,
#             "url": target_url,
#         }

#         print(f"[*] Fetching: {target_url}")

#         try:
#             resp = self.session.get(
#                 SCRAPER_API_BASE,
#                 params=params,
#                 timeout=60,
#                 allow_redirects=True,
#             )

#             print("STATUS:", resp.status_code)

#             if resp.status_code != 200 or not resp.text.strip():
#                 return None

#             return BeautifulSoup(resp.text, "html.parser")

#         except Exception as e:
#             print(f"[!] Network error: {e}")
#             return None

#     # ---------- resolve config ----------
#     def _resolve_part_config(self, query: str) -> Tuple[Optional[str], Optional[Dict]]:
#         query = query.lower()
#         for key, cfg in PART_CONFIG.items():
#             if key in query:
#                 return key, cfg
#         return None, None

#     # ================= PUBLIC API =================
#     def search_part(self, vin: str, part_name: str) -> Dict:

#         # ─────────────────────────────
#         # 0️⃣ Resolve part config
#         # ─────────────────────────────
#         part_key, cfg = self._resolve_part_config(part_name)

#         if not cfg:
#             return {"error": f"Unsupported part type: {part_name}"}

#         section_keywords = cfg["section"]
#         diagram_keywords = cfg["diagram"]
#         part_keywords = cfg["part_name"]
#         core_keywords = part_keywords          # e.g. ["filter", "element"]
#         fallback_keywords = diagram_keywords   # e.g. ["oil filter", "oil supply"]

#         # ─────────────────────────────
#         # 1️⃣ SEARCH VIN
#         # ─────────────────────────────
#         soup = self._get(f"{BASE_URL}/search?q={vin}")

#         if not soup:
#             return {"error": "VIN search failed"}

#         # ─────────────────────────────
#         # 2️⃣ FIND SECTION
#         # ─────────────────────────────
#         section_link = None

#         for a in soup.select("div.caption a, td a"):
#             text = a.get_text(" ", strip=True).lower()
#             href = a.get("href")

#             if href and any(k in text for k in section_keywords):
#                 section_link = urljoin(BASE_URL, href)
#                 print(f"[+] Found Section: {text.title()}")
#                 break

#         if not section_link:
#             return {"error": f"Section not found for {part_key}"}

#         section_link = section_link.replace("/en/", "/")

#         # ─────────────────────────────
#         # 3️⃣ LOAD SECTION PAGE
#         # ─────────────────────────────
#         soup_section = self._get(section_link)

#         if not soup_section:
#             return {"error": f"Failed to load section page for {part_key}"}

#         # ─────────────────────────────
#         # 4️⃣ FIND DIAGRAM
#         # ─────────────────────────────
#         diagram_link = None

#         diagram_anchors = soup_section.select("div.caption a, td a")

#         if not diagram_anchors:
#             return {"error": f"No diagrams found in section {part_key}"}

#         # ✅ Always pick the FIRST diagram in the section
#         first = diagram_anchors[0]
#         text = first.get_text(" ", strip=True)
#         href = first.get("href")

#         if not href:
#             return {"error": f"First diagram has no link in section {part_key}"}

#         diagram_link = urljoin(BASE_URL, href)
#         diagram_link = diagram_link.replace("/en/", "/")

#         print(f"[+] Using primary diagram: {text}")

#         # ─────────────────────────────
#         # 5️⃣ LOAD DIAGRAM PAGE
#         # ─────────────────────────────
#         soup_parts = self._get(diagram_link)

#         if not soup_parts:
#             return {"error": f"Failed to load parts diagram for {part_key}"}

#         # ─────────────────────────────
#         # 6️⃣ EXTRACT PARTS
#         # ─────────────────────────────
#         parts: List[Dict] = []


#         OEM_RE = re.compile(r"^\d{7,11}$")

#         for row in soup_parts.select("table tr"):
#             cols = row.select("td")
#             if len(cols) < 2:
#                 continue

#             a = cols[0].select_one("a")
#             if not a:
#                 continue

#             number = a.get_text(strip=True)

#             # 🔒 HARD FILTER: only real OEM numbers
#             if not OEM_RE.match(number):
#                 continue

#             name = cols[1].get_text(" ", strip=True)

#             if any(k in name.lower() for k in part_keywords):
#                 parts.append({
#                     "number": number,
#                     "name": name
#                 })


#         if not parts:
#             return {"error": f"No matching parts found for {part_key}"}

#         return {
#             "vin": vin,
#             "query": part_name,
#             "category": part_key,
#             "parts": parts
#         }


# # ================= SINGLETON =================

# _scraper: Optional[PartSouqScraper] = None


# def get_scraper() -> PartSouqScraper:
#     global _scraper
#     if _scraper is None:
#         _scraper = PartSouqScraper()
#     return _scraper
