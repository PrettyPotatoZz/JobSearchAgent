"""Fetch dated postings from public structured careers feeds (Workday, Recruitee) and parse
LinkedIn/Indeed alert e-mails dropped in data/inbox/. Standard library only.

Everything fetched is untrusted data: it is only filtered and stored as JSON, never executed.
"""
from __future__ import annotations

import email
import email.policy
import json
import re
import shutil
import ssl
import time
import urllib.request
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path


def _ssl_context() -> ssl.SSLContext:
    # python.org builds on macOS ship without root certificates; use the system bundle (verification stays on).
    ctx = ssl.create_default_context()
    if Path("/etc/ssl/cert.pem").exists():
        ctx.load_verify_locations("/etc/ssl/cert.pem")
    return ctx


_CTX = _ssl_context()


def _http(url: str, ua: str, payload: dict | None = None, timeout: int = 20):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": ua, "Accept": "application/json",
        **({"Content-Type": "application/json"} if data else {})})
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return json.load(r)


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def city_of(location: str, cities: list[dict]) -> str | None:
    loc = _norm(location)
    for c in cities:
        for a in c["aliases"] + [c["name"]]:
            if re.search(rf"\b{re.escape(_norm(a))}\b", loc):
                return c["name"]
    return None


def workday_posted(text: str, today: date) -> date | None:
    t = (text or "").lower()
    if "today" in t:
        return today
    if "yesterday" in t:
        return today - timedelta(days=1)
    m = re.search(r"(\d+)\+?\s*days?", t)
    if m and "+" not in t:
        return today - timedelta(days=int(m.group(1)))
    return None  # "30+ Days Ago" or unknown -> not usable


def fetch_workday(feed, kw, cat, cfg, prefs, today, out, log):
    base = f"https://{feed['host']}/wday/cxs/{feed['tenant']}/{feed['site']}/jobs"
    for page in range(cfg["max_pages_per_query"]):
        try:
            d = _http(base, cfg["user_agent"], {"appliedFacets": {}, "limit": 20, "offset": page * 20, "searchText": kw})
        except Exception as e:  # noqa: BLE001
            log.append({"source": feed["company"], "query": kw, "status": "error", "note": str(e)[:200]})
            return
        posts = d.get("jobPostings") or []
        for p in posts:
            posted = workday_posted(p.get("postedOn", ""), today)
            if not posted or (today - posted).days > prefs["max_age_days"]:
                continue
            loc = p.get("locationsText") or ""
            city = city_of(loc, prefs["cities"])
            if not city and "location" not in loc.lower():  # "2 Locations" -> keep, check later
                continue
            out.append({"title": p.get("title"), "company": feed["company"], "index": feed["index"],
                        "location_text": loc, "city_guess": city, "category_hint": cat,
                        "url": f"https://{feed['host']}/en-US/{feed['site']}{p.get('externalPath', '')}",
                        "job_id": (p.get("bulletFields") or [None])[0],
                        "posted_date": posted.isoformat(), "posted_evidence": p.get("postedOn"),
                        "source": f"Empresa ({feed['index']}) · Workday",
                        "_detail": f"https://{feed['host']}/wday/cxs/{feed['tenant']}/{feed['site']}{p.get('externalPath', '')}"})
        time.sleep(cfg["delay_seconds"])
        if len(posts) < 20:
            break


def fetch_recruitee(feed, cfg, prefs, today, out, log, kw_by_cat):
    try:
        d = _http(f"https://{feed['subdomain']}.recruitee.com/api/offers/", cfg["user_agent"])
    except Exception as e:  # noqa: BLE001
        log.append({"source": feed["company"], "query": "api/offers", "status": "error", "note": str(e)[:200]})
        return
    for o in d.get("offers", []):
        try:
            posted = datetime.strptime(o["published_at"][:10], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        if (today - posted).days > prefs["max_age_days"]:
            continue
        city = city_of(f"{o.get('city')} {o.get('location')}", prefs["cities"])
        if not city and not o.get("remote"):
            continue
        title = o.get("title") or ""
        cat = next((c for c, kws in kw_by_cat.items() if any(_norm(k) in _norm(title) for k in kws)), None)
        sal = o.get("salary") or {}
        out.append({"title": title, "company": feed["company"], "index": feed["index"],
                    "location_text": f"{o.get('city')}, {o.get('country')}", "city_guess": city,
                    "category_hint": cat, "url": o.get("careers_url"), "job_id": str(o.get("id")),
                    "posted_date": posted.isoformat(), "posted_evidence": f"published_at {o.get('published_at')}",
                    "work_mode": "Remoto" if o.get("remote") else ("Híbrido" if o.get("hybrid") else None),
                    "employment_type": o.get("employment_type_code"),
                    "salary": sal if (sal.get("min") or sal.get("max")) else None,
                    "source": f"Empresa ({feed['index']}) · Recruitee",
                    "description": _strip_html((o.get("description") or "") + " " + (o.get("requirements") or ""))})
    time.sleep(cfg["delay_seconds"])


EXCLUDE_TITLE = re.compile(
    r"\b(intern(ship)?|praktikum|praktikant|werkstudent|duales? studium|master ?thesis|bachelor ?thesis|"
    r"abschlussarbeit|trainee|beca|becario|pr[aá]cticas|apprentice|ausbildung|candidate pool|"
    r"seed program|graduate program)\b|\((contract|temporary|befristet)\)", re.I)


def _strip_html(h: str, limit: int = 6000) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", h or ""))
    return re.sub(r"\s+", " ", t).strip()[:limit]


def enrich_workday(postings: list[dict], cfg: dict, prefs: dict, today: date, log: list) -> list[dict]:
    """Fetch the public job detail (description, exact start date, all locations) for Workday postings.
    Drops postings whose locations include none of the target cities."""
    out, dropped_city, errors = [], 0, 0
    for p in postings:
        url = p.pop("_detail", None)
        if not url:
            out.append(p)
            continue
        try:
            info = _http(url, cfg["user_agent"]).get("jobPostingInfo", {})
        except Exception:  # noqa: BLE001
            errors += 1
            out.append(p)  # keep with title-only data; Claude marks it as unverified
            time.sleep(cfg["delay_seconds"])
            continue
        locs = [info.get("location") or ""] + list(info.get("additionalLocations") or [])
        city = next((c for c in (city_of(l, prefs["cities"]) for l in locs) if c), None)
        if not city:
            dropped_city += 1
            time.sleep(cfg["delay_seconds"])
            continue
        p["city_guess"] = city
        p["location_text"] = " · ".join(l for l in locs if l)
        if info.get("startDate"):
            try:
                d = date.fromisoformat(info["startDate"][:10])
                if (today - d).days <= prefs["max_age_days"]:
                    p["posted_date"] = d.isoformat()
                    p["posted_evidence"] = f"startDate {d.isoformat()} ({info.get('postedOn')})"
            except ValueError:
                pass
        p["time_type"] = info.get("timeType")
        p["description"] = _strip_html(info.get("jobDescription") or "")
        out.append(p)
        time.sleep(cfg["delay_seconds"])
    log.append({"source": "Workday (detalle)", "query": "jobPostingInfo", "status": "ok" if not errors else "error",
                "note": f"{len(out)} con detalle; {dropped_city} fuera de las ciudades; {errors} errores"})
    return out


def fetch_feeds(cfg: dict, prefs: dict, today: date) -> dict:
    out, log = [], []
    for feed in cfg["feeds"]:
        if feed["type"] == "workday":
            for cat, kws in cfg["keywords"].items():
                for kw in kws:
                    fetch_workday(feed, kw, cat, cfg, prefs, today, out, log)
        elif feed["type"] == "recruitee":
            fetch_recruitee(feed, cfg, prefs, today, out, log, cfg["keywords"])
        n = sum(1 for x in out if x["company"] == feed["company"])
        log.append({"source": feed["company"], "query": feed["type"], "status": "ok", "note": f"{n} ofertas en ventana y ciudad"})
    seen, uniq = set(), []
    dropped = 0
    for x in out:
        if EXCLUDE_TITLE.search(x.get("title") or ""):
            dropped += 1
            continue
        if x["url"] not in seen:
            seen.add(x["url"])
            uniq.append(x)
    log.append({"source": "Filtro previo", "query": "título", "status": "ok",
                "note": f"{dropped} descartadas por título (prácticas, Werkstudent, trainee, contract…)"})
    return {"postings": uniq, "sources_log": log}


# ------------------------------------------------------------------ inbox (alert e-mails)
JOB_URL = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?(?:linkedin\.com/(?:comm/)?jobs/view/\d+|indeed\.[a-z.]+/(?:rc/clk|viewjob|pagead/clk)[^\s\"'<>]*)",
    re.I)


def _text_of(msg) -> str:
    parts = []
    for part in msg.walk():
        ct = part.get_content_type()
        if ct in ("text/plain", "text/html"):
            try:
                body = part.get_content()
            except Exception:  # noqa: BLE001
                continue
            if ct == "text/html":
                body = re.sub(r"<a [^>]*href=\"([^\"]+)\"[^>]*>", r" \1 ", body)
                body = unescape(re.sub(r"<[^>]+>", " ", body))
            parts.append(body)
    return re.sub(r"[ \t]+", " ", "\n".join(parts))


def read_inbox(inbox: Path, processed: Path) -> dict:
    items, files = [], []
    for f in sorted(inbox.glob("*")):
        if f.is_dir():
            continue
        if f.suffix.lower() == ".eml":
            msg = email.message_from_bytes(f.read_bytes(), policy=email.policy.default)
            try:
                received = parsedate_to_datetime(msg["Date"]).date().isoformat()
            except Exception:  # noqa: BLE001
                received = None
            text = _text_of(msg)
            urls = sorted({u.split("?")[0] if "linkedin" in u.lower() else u for u in JOB_URL.findall(text)})
            items.append({"file": f.name, "from": str(msg["From"]), "subject": str(msg["Subject"]),
                          "received": received, "job_urls": urls, "text": text[:12000]})
            files.append(f)
        elif f.name == "links.txt":
            links = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip().startswith("http")]
            if links:
                items.append({"file": f.name, "from": "manual", "subject": "Enlaces añadidos a mano",
                              "received": date.today().isoformat(), "job_urls": links, "text": ""})
            files.append(f)
    return {"items": items, "_files": files}


def archive_inbox(files: list[Path], processed: Path, run_id: str) -> None:
    dest = processed / run_id
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.move(str(f), dest / f.name)
