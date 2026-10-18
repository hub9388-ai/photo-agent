from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from photo_runtime import resolve_env_value
from photo_trace import trace_event
from photo_utils import normalize_string_list

try:
    import requests as _requests_lib
except ImportError:
    _requests_lib = None  # type: ignore


REFERENCE_SEARCH_PROVIDER = "Web Search (DuckDuckGo / Bing RSS)"
PLACES_PROVIDER = "高德地图 POI"
WEATHER_PROVIDER = "高德天气"
WEATHER_FORECAST_MAX_DAYS = 3
DEFAULT_PLACE_LIMIT = 5

AMAP_PLACE_TEXT_URL = "https://restapi.amap.com/v3/place/text"
AMAP_GEO_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"


def http_get_json(url: str, timeout: int = 15, headers: dict | None = None) -> dict:
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    merged_headers = {**default_headers, **(headers or {})}

    if _requests_lib is not None:
        session = _requests_lib.Session()
        session.trust_env = False
        response = session.get(url, headers=merged_headers, timeout=timeout)
        response.raise_for_status()
        return response.json()

    request = Request(url, headers=merged_headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_iso_date(text: str) -> date | None:
    value = str(text).strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def decode_search_redirect(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    target = query.get("uddg", [""])[0]
    return unquote(target) if target else url


def compact_text(text: str, limit: int = 180) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(limit - 3, 0)] + "..."


def search_reference_links(query: str, limit: int = 3) -> list[dict]:
    text = str(query).strip()
    if not text:
        return []

    trace_event(
        "provider.reference_search.start",
        provider=REFERENCE_SEARCH_PROVIDER,
        query=text,
        limit=limit,
    )

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(text)}"
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )

    try:
        with urlopen(request, timeout=8) as response:
            html_text = response.read(1_000_000).decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        trace_event(
            "provider.reference_search.failed",
            provider=REFERENCE_SEARCH_PROVIDER,
            query=text,
            error=str(exc),
        )
        return search_bing_reference_links(text, limit=limit)

    matches = list(re.finditer(
        r'<a\b(?=[^>]*\bclass="[^"]*\bresult__a\b[^"]*")[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    ))

    results: list[dict] = []
    seen: set[str] = set()
    for index, match in enumerate(matches):
        raw_url, raw_title = match.groups()
        clean_url = decode_search_redirect(unescape(raw_url))
        clean_title = re.sub(r"<.*?>", "", unescape(raw_title)).strip()
        if urlparse(clean_url).scheme not in {"http", "https"} or not clean_title or clean_url in seen:
            continue
        seen.add(clean_url)
        following = html_text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(html_text)]
        snippet = re.search(r'<(?:a|div)[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|div)>', following, re.I | re.S)
        excerpt = compact_text(unescape(re.sub(r"<[^>]+>", " ", snippet.group(1))), 500) if snippet else ""
        results.append({"title": compact_text(clean_title), "url": clean_url, "snippet": excerpt})
        if len(results) >= limit:
            break

    if not results:
        results = search_bing_reference_links(text, limit=limit)

    trace_event(
        "provider.reference_search.result",
        provider=REFERENCE_SEARCH_PROVIDER,
        query=text,
        result_count=len(results),
    )
    return results


def search_bing_reference_links(query: str, limit: int = 3) -> list[dict]:
    """Public RSS endpoint; fixed host, bounded response, no result-page fetching."""
    request = Request(
        f"https://www.bing.com/search?format=rss&q={quote_plus(query)}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            root = ET.fromstring(response.read(1_000_000))
    except (HTTPError, URLError, TimeoutError, OSError, ET.ParseError, ValueError):
        trace_event("provider.reference_search.fallback_failed", provider="Bing RSS")
        return []
    results = []
    seen = set()
    for item in root.findall("./channel/item"):
        url = (item.findtext("link") or "").strip()
        title = compact_text(item.findtext("title") or "")
        if urlparse(url).scheme not in {"http", "https"} or not title or url in seen:
            continue
        seen.add(url)
        results.append({"title": title, "url": url, "snippet": compact_text(
            re.sub(r"<[^>]+>", " ", unescape(item.findtext("description") or "")), 500)})
        if len(results) >= limit:
            break
    return results


def amap_text(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def parse_amap_location(location_text: str) -> tuple[float | None, float | None]:
    parts = str(location_text or "").split(",")
    if len(parts) != 2:
        return None, None
    try:
        lng = float(parts[0])
        lat = float(parts[1])
    except ValueError:
        return None, None
    return lng, lat


def infer_place_search_queries(brief: dict) -> list[str]:
    queries: list[str] = []
    city = str(brief.get("city", "")).strip()
    target_location = str(brief.get("target_location", "")).strip()
    subject = str(brief.get("subject", "")).strip() or "摄影"
    styles = " ".join(brief.get("style_keywords", [])[:2])

    if city and target_location:
        queries.append(f"{city} {target_location}")
    if city and styles and subject:
        queries.append(f"{city} {styles} {subject} 拍摄地")
    if city and subject:
        queries.append(f"{city} {subject} 拍摄")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in queries:
        key = re.sub(r"\s+", "", item.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:3]


def amap_get_adcode(city: str, api_key: str) -> str:
    payload = http_get_json(
        f"{AMAP_GEO_URL}?{urlencode({'key': api_key, 'address': city, 'output': 'json'})}"
    )
    if str(payload.get("status", "")) != "1":
        return ""
    geocodes = payload.get("geocodes", [])
    if not geocodes:
        return ""
    return str(geocodes[0].get("adcode", "")).strip()


def search_places(brief: dict, limit: int = DEFAULT_PLACE_LIMIT) -> dict:
    api_key = resolve_env_value("AMAP_KEY")
    if not api_key:
        return {
            "status": "unavailable",
            "provider": PLACES_PROVIDER,
            "note": "未配置 AMAP_KEY，地点候选改为规则建议。",
            "results": [],
            "queries": [],
        }

    queries = brief.get("place_search_queries") or infer_place_search_queries(brief)
    if not queries:
        return {
            "status": "empty",
            "provider": PLACES_PROVIDER,
            "note": "缺少可用于高德 POI 搜索的城市或地点关键词。",
            "results": [],
            "queries": [],
        }

    city = str(brief.get("city", "")).strip()
    trace_event(
        "provider.places.start",
        provider=PLACES_PROVIDER,
        city=city,
        queries=queries,
        limit=limit,
    )

    results: list[dict] = []
    seen_place_ids: set[str] = set()
    provider_notes: list[str] = []

    for query_text in queries:
        params = {
            "key": api_key,
            "keywords": query_text,
            "city": city,
            "citylimit": "false",
            "offset": max(limit, 10),
            "page": 1,
            "extensions": "all",
            "output": "json",
        }
        url = f"{AMAP_PLACE_TEXT_URL}?{urlencode(params)}"
        try:
            payload = http_get_json(url)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            provider_notes.append(f'查询"{query_text}"失败：{exc}')
            trace_event(
                "provider.places.query_failed",
                provider=PLACES_PROVIDER,
                query=query_text,
                error=str(exc),
            )
            continue
        except json.JSONDecodeError:
            provider_notes.append(f'查询"{query_text}"返回了不可解析结果。')
            trace_event(
                "provider.places.query_failed",
                provider=PLACES_PROVIDER,
                query=query_text,
                error="json_decode_error",
            )
            continue

        status = str(payload.get("status", "")).strip()
        info = str(payload.get("info", "")).strip()
        if status != "1":
            provider_notes.append(f'查询"{query_text}"返回状态：{info or status or "UNKNOWN"}')
            trace_event(
                "provider.places.query_failed",
                provider=PLACES_PROVIDER,
                query=query_text,
                error=info or status or "UNKNOWN",
            )
            continue

        for item in payload.get("pois", []):
            place_id = str(item.get("id", "")).strip()
            if not place_id:
                place_id = f"{item.get('name', '')}|{item.get('address', '')}|{item.get('location', '')}"
            if not place_id or place_id in seen_place_ids:
                continue

            seen_place_ids.add(place_id)
            photos = item.get("photos") or []
            photo_url = ""
            if photos and isinstance(photos[0], dict):
                photo_url = str(photos[0].get("url", "")).strip()
            lng, lat = parse_amap_location(str(item.get("location", "")).strip())

            address_parts = [
                amap_text(item.get("pname")),
                amap_text(item.get("cityname")),
                amap_text(item.get("adname")),
                amap_text(item.get("address")),
            ]
            address = " ".join(part for part in address_parts if part)

            results.append(
                {
                    "place_id": place_id,
                    "name": str(item.get("name", "")).strip(),
                    "address": address,
                    "rating": item.get("biz_ext", {}).get("rating") if isinstance(item.get("biz_ext"), dict) else "",
                    "types": normalize_string_list(str(item.get("type", "")).split(";"), limit=5),
                    "lat": lat,
                    "lng": lng,
                    "photo_url": photo_url,
                }
            )
            if len(results) >= limit:
                break

        if len(results) >= limit:
            break

    if results:
        note = f"已通过 {PLACES_PROVIDER} 查询到 {len(results)} 个地点候选。"
        if provider_notes:
            note = f"{note} 另有部分查询失败：{'；'.join(provider_notes[:2])}"
        payload = {
            "status": "ok",
            "provider": PLACES_PROVIDER,
            "note": note,
            "results": results,
            "queries": queries,
        }
        trace_event(
            "provider.places.result",
            provider=PLACES_PROVIDER,
            status="ok",
            result_count=len(results),
            note=compact_text(note),
        )
        return payload

    note = "未找到合适地点候选。" + (f" 细节：{'；'.join(provider_notes[:2])}" if provider_notes else "")
    trace_event(
        "provider.places.result",
        provider=PLACES_PROVIDER,
        status="empty",
        result_count=0,
        note=compact_text(note),
    )
    return {
        "status": "empty",
        "provider": PLACES_PROVIDER,
        "note": note,
        "results": [],
        "queries": queries,
    }


def get_weather_forecast(brief: dict, places_payload: dict) -> dict:
    api_key = resolve_env_value("AMAP_KEY")
    if not api_key:
        return {
            "status": "unavailable",
            "provider": WEATHER_PROVIDER,
            "note": "未配置 AMAP_KEY，无法查询天气。",
            "target_date": brief.get("shoot_date", ""),
            "days": [],
        }

    city = str(brief.get("city", "")).strip()
    if not city:
        return {
            "status": "empty",
            "provider": WEATHER_PROVIDER,
            "note": "缺少城市信息，无法查询天气。",
            "target_date": brief.get("shoot_date", ""),
            "days": [],
        }

    target_date = str(brief.get("shoot_date", "")).strip()
    trace_event(
        "provider.weather.start",
        provider=WEATHER_PROVIDER,
        city=city,
        target_date=target_date,
    )

    target = parse_iso_date(target_date)
    if target is not None:
        delta_days = (target - datetime.now().date()).days
        if delta_days > WEATHER_FORECAST_MAX_DAYS:
            note = (
                f"目标日期 {target_date} 超出高德天气 3 天预报范围，"
                "天气建议将退化为规则判断，请临近拍摄前再刷新。"
            )
            trace_event(
                "provider.weather.result",
                provider=WEATHER_PROVIDER,
                status="advisory",
                city=city,
                target_date=target_date,
                note=compact_text(note),
            )
            return {
                "status": "advisory",
                "provider": WEATHER_PROVIDER,
                "note": note,
                "target_date": target_date,
                "days": [],
            }

    try:
        adcode = amap_get_adcode(city, api_key)
        if not adcode:
            note = f'高德地理编码未找到 "{city}" 对应的行政区划码。'
            trace_event(
                "provider.weather.result",
                provider=WEATHER_PROVIDER,
                status="empty",
                city=city,
                target_date=target_date,
                note=compact_text(note),
            )
            return {
                "status": "empty",
                "provider": WEATHER_PROVIDER,
                "note": note,
                "target_date": target_date,
                "days": [],
            }

        payload = http_get_json(
            f"{AMAP_WEATHER_URL}?{urlencode({'key': api_key, 'city': adcode, 'extensions': 'all', 'output': 'json'})}"
        )
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        trace_event(
            "provider.weather.result",
            provider=WEATHER_PROVIDER,
            status="error",
            city=city,
            target_date=target_date,
            error=str(exc),
        )
        return {
            "status": "error",
            "provider": WEATHER_PROVIDER,
            "note": f"高德天气查询失败：{exc}",
            "target_date": target_date,
            "days": [],
        }
    except json.JSONDecodeError:
        trace_event(
            "provider.weather.result",
            provider=WEATHER_PROVIDER,
            status="error",
            city=city,
            target_date=target_date,
            error="json_decode_error",
        )
        return {
            "status": "error",
            "provider": WEATHER_PROVIDER,
            "note": "高德天气接口返回了不可解析结果。",
            "target_date": target_date,
            "days": [],
        }

    if str(payload.get("status", "")) != "1":
        note = f"高德天气接口返回错误：{payload.get('info', 'UNKNOWN')}"
        trace_event(
            "provider.weather.result",
            provider=WEATHER_PROVIDER,
            status="error",
            city=city,
            target_date=target_date,
            note=compact_text(note),
        )
        return {
            "status": "error",
            "provider": WEATHER_PROVIDER,
            "note": note,
            "target_date": target_date,
            "days": [],
        }

    forecasts = payload.get("forecasts", [])
    if not forecasts:
        note = "高德天气未返回预报数据。"
        trace_event(
            "provider.weather.result",
            provider=WEATHER_PROVIDER,
            status="empty",
            city=city,
            target_date=target_date,
            note=note,
        )
        return {
            "status": "empty",
            "provider": WEATHER_PROVIDER,
            "note": note,
            "target_date": target_date,
            "days": [],
        }

    raw_days = forecasts[0].get("casts", [])
    all_days = []
    for day in raw_days:
        day_str = str(day.get("date", "")).strip()
        text_day = str(day.get("dayweather", "")).strip()
        text_night = str(day.get("nightweather", "")).strip()
        condition = text_day or text_night
        all_days.append(
            {
                "date": day_str,
                "condition": condition,
                "text_day": text_day,
                "text_night": text_night,
                "temp_max_c": str(day.get("daytemp", "")).strip(),
                "temp_min_c": str(day.get("nighttemp", "")).strip(),
                "wind_dir_day": str(day.get("daywind", "")).strip(),
                "wind_scale_day": str(day.get("daypower", "")).strip(),
                "sunrise": "",
                "sunset": "",
            }
        )

    if target_date:
        matched = [day for day in all_days if day["date"] == target_date]
        normalized_days = matched[:3] if matched else all_days[:3]
    else:
        normalized_days = all_days[:3]

    note = f"已通过高德天气查询到 {city} 的预报。"
    trace_event(
        "provider.weather.result",
        provider=WEATHER_PROVIDER,
        status="ok" if normalized_days else "empty",
        city=city,
        target_date=target_date,
        result_count=len(normalized_days),
        note=note,
    )
    return {
        "status": "ok" if normalized_days else "empty",
        "provider": WEATHER_PROVIDER,
        "note": note,
        "target_date": target_date,
        "days": normalized_days,
    }


def collect_provider_context(brief: dict, *, place_limit: int = DEFAULT_PLACE_LIMIT) -> dict:
    places = search_places(brief, limit=place_limit) if brief.get("needs_places", True) else {
        "status": "skipped",
        "provider": PLACES_PROVIDER,
        "note": "本轮未请求地点搜索。",
        "results": [],
        "queries": [],
    }

    weather = get_weather_forecast(brief, places) if brief.get("needs_weather", True) else {
        "status": "skipped",
        "provider": WEATHER_PROVIDER,
        "note": "本轮未请求天气搜索。",
        "target_date": brief.get("shoot_date", ""),
        "days": [],
    }

    # Keep web evidence separate from verified map POIs and weather forecasts.
    # Only explicitly permitted brief fields leave this process, never media/keys.
    web_queries = []
    location = " ".join(str(brief.get(key) or "").strip()[:80] for key in ("city", "target_location")).strip()
    if location and brief.get("needs_places", True) and not places.get("results"):
        web_queries.append(("places", f"{location} {str(brief.get('subject') or '摄影')[:80]} 游览路线 拍摄地点 交通"))
    if location and brief.get("needs_weather", True) and not weather.get("days"):
        web_queries.append(("weather", f"{location} {str(brief.get('shoot_date') or '')[:20]} 天气预报"))
    web_results = []
    for purpose, query in web_queries:
        for result in search_reference_links(query[:240], limit=3):
            web_results.append({**result, "purpose": purpose})
    web_search = {
        "status": "ok" if web_results else "empty" if web_queries else "skipped",
        "results": web_results,
        "queries": [query for _, query in web_queries],
    }
    trace_event("provider.planning_web_fallback.result", status=web_search["status"],
                purposes=[purpose for purpose, _ in web_queries], result_count=len(web_results))

    availability_notes = [
        compact_text(places.get("note", "")),
        compact_text(weather.get("note", "")),
    ]
    availability_notes = [item for item in availability_notes if item]

    payload = {
        "brief": brief,
        "places": places,
        "weather": weather,
        "web_search": web_search,
        "availability_notes": availability_notes,
    }
    trace_event(
        "provider.context.collected",
        places_status=places.get("status", ""),
        weather_status=weather.get("status", ""),
        place_count=len(places.get("results", [])),
        weather_days=len(weather.get("days", [])),
    )
    return payload

