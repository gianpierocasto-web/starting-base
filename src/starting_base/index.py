"""Ricerca sull'indice awesome-reverse-engineered e verdetto di base pronta.

Il punteggio è quello di re_index.py nel repository alexgaoth/awesome-reverse-engineered:
nome e slug pesano di più, poi topics, descrizione e categoria. I sinonimi pesano 0.7.
Stelle, archivio e inattività oltre 3 anni modificano il punteggio come nello script ufficiale.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("starting_base")

RAW_INDEX = (
    "https://raw.githubusercontent.com/alexgaoth/awesome-reverse-engineered/main/data/entries.json"
)
CACHE = Path.home() / ".cache" / "awesome-reverse-engineered" / "entries.json"
MAX_AGE_SECONDS = 86400
INDEX_SOURCE = "https://github.com/alexgaoth/awesome-reverse-engineered"

SYNONYMS: dict[str, list[str]] = {
    "twitter": ["x"],
    "x": ["twitter"],
    "ble": ["bluetooth"],
    "bluetooth": ["ble"],
    "car": ["vehicle", "automotive"],
    "vehicle": ["car"],
    "decomp": ["decompilation"],
    "decompile": ["decompilation"],
    "chatgpt": ["openai"],
    "openai": ["chatgpt"],
    "gemini": ["bard"],
    "instagram": ["meta"],
    "facebook": ["meta"],
    "imessage": ["apple"],
    "n64": ["nintendo 64"],
    "gamecube": ["gc"],
    "ps1": ["playstation 1", "psx"],
    "ps2": ["playstation 2"],
    "local": ["local control", "cloud-free"],
    "locale": ["local", "local control", "cloud-free"],
    "vacuum": ["robot"],
}

STOPWORDS = {
    "a",
    "al",
    "alla",
    "alle",
    "agli",
    "ai",
    "allo",
    "an",
    "and",
    "already",
    "anche",
    "avere",
    "base",
    "can",
    "ce",
    "che",
    "ci",
    "come",
    "con",
    "controllare",
    "controllo",
    "cui",
    "da",
    "dei",
    "del",
    "della",
    "delle",
    "dello",
    "degli",
    "di",
    "e",
    "ed",
    "esiste",
    "esistono",
    "fare",
    "for",
    "fra",
    "gia",
    "già",
    "gli",
    "ha",
    "hai",
    "ho",
    "i",
    "il",
    "in",
    "is",
    "la",
    "le",
    "lo",
    "ma",
    "me",
    "mi",
    "mia",
    "mio",
    "my",
    "ne",
    "nel",
    "nella",
    "nelle",
    "nello",
    "negli",
    "nei",
    "non",
    "o",
    "od",
    "of",
    "or",
    "partenza",
    "per",
    "perche",
    "perché",
    "piu",
    "più",
    "please",
    "posso",
    "pronta",
    "pronto",
    "progetto",
    "progetti",
    "puo",
    "può",
    "puoi",
    "qualche",
    "quale",
    "quali",
    "qualcosa",
    "queste",
    "questi",
    "questa",
    "questo",
    "repo",
    "repository",
    "se",
    "serve",
    "si",
    "sia",
    "something",
    "sono",
    "su",
    "sua",
    "sue",
    "sul",
    "sulla",
    "sulle",
    "sullo",
    "sugli",
    "sui",
    "suo",
    "sviluppare",
    "the",
    "there",
    "ti",
    "to",
    "tra",
    "trova",
    "trovare",
    "un",
    "una",
    "uno",
    "usare",
    "uso",
    "vi",
    "voglio",
    "vorrei",
    "with",
    "without",
    "you",
}

CATEGORY_ROLE = {
    "AI Tools & LLM Clients": (
        "Client o archivio legato a un prodotto AI chiuso: si riusa per parlare con quel servizio "
        "o per leggere materiale già estratto, non per ricostruire il protocollo da zero."
    ),
    "Game Decompilations & Reimplementations": (
        "Decompilazione o reimplementazione di un gioco: è codice da leggere e da cui partire, "
        "non una libreria generica."
    ),
    "Devices, IoT & Hardware": (
        "Controllo di un dispositivo già ricostruito: parti dal protocollo o dal client locale "
        "invece che dal firmware chiuso."
    ),
    "Unofficial Web/App API Clients": (
        "Client di un'API non ufficiale: le chiamate al servizio chiuso sono già ricostruite."
    ),
    "Messaging & Social Apps": (
        "Client o libreria per un'app di messaggistica o un social chiuso."
    ),
    "Third-party Clients": "Client alternativo di un servizio già esistente.",
    "Chinese & Asian Platforms": "Client o integrazione per una piattaforma cinese o asiatica.",
    "Apple Ecosystem": (
        "Integrazione con un servizio o un dispositivo Apple, quando l'SDK ufficiale non basta."
    ),
    "Drivers & Low-level Hardware": "Driver o controllo a basso livello di hardware chiuso.",
    "Automotive": "Integrazione con un'auto o con un componente automotive.",
    "Industrial & Building Automation": (
        "Libreria per un protocollo industriale o di building automation."
    ),
    "Firmware & Embedded": "Firmware o strumento embedded già scritto per quell'hardware.",
    "Network & Wire Protocols": "Implementazione di un protocollo di rete o di un protocollo su cavo.",
    "File Formats": "Parser o strumento per un formato di file.",
    "Online Service Revivals": "Server o client che rimette in funzione un servizio chiuso.",
    "Desktop Software Reimplementations": "Reimplementazione di un software desktop.",
    "Alternative Frontends": "Interfaccia alternativa a un servizio esistente.",
    "Mobile Apps": "App mobile non ufficiale, o modifica di un'app esistente.",
    "RE Tooling": (
        "Strumento di reverse engineering. Aiuta ad analizzare un binario, non è il client "
        "del prodotto che vuoi costruire."
    ),
    "Collections & Awesome Lists": (
        "Raccolta di link. Non è codice da eseguire come base del progetto."
    ),
}

_HEADING = re.compile(r"^#{1,3}\s+(.+?)\s*#*\s*$")
_INTERESTING = re.compile(
    r"install|usage|utilizzo|how to|feature|getting started|quick ?start|protocol|example|esempi|\bapi\b|\bsdk\b",
    re.IGNORECASE,
)

_lock = threading.Lock()
_entries: list[dict[str, Any]] | None = None
_loaded_mtime: float | None = None
_token: str | None = None
_readmes: dict[str, str | None] = {}


def assess(
    query: str,
    language: str | None = None,
    category: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    terms = extract_terms(query)
    if not terms:
        return {
            "verdetto": "nessuna base",
            "motivo": (
                "Nella richiesta non resta nessun nome di prodotto, protocollo o formato. "
                "Indica quello, per esempio il produttore o il formato file."
            ),
            "termini": [],
            "risultati": [],
            "indice": index_meta(),
        }

    lang = (language or "").strip() or None
    cat = (category or "").strip() or None
    hits = search(terms, language=lang, category=cat, limit=clamp_limit(limit))
    results = [card_for(hit, terms) for hit in hits]
    fill_readmes(results)
    return {
        "verdetto": overall_verdict(results),
        "motivo": overall_reason(results, terms, lang, cat),
        "termini": terms,
        "risultati": results,
        "indice": index_meta(),
    }


def explain(repo: str) -> dict[str, Any]:
    entries = load_entries()
    entry = find_entry(entries, repo)
    if entry is None:
        url = repo if repo.startswith("http") else f"https://github.com/{repo.strip('/')}"
        result = {
            "nome": repo,
            "repo": repo,
            "url": url,
            "idoneita": "nessuna base",
            "descrizione": "",
            "aiuto_concreto": {
                "cosa_copre": "",
                "ruolo": "Questo repository non è nell'indice awesome-reverse-engineered.",
                "dal_readme": [],
                "limiti": [
                    "Scheda assente dall'indice: non è una base verificata da quella lista."
                ],
            },
        }
        fill_readmes([result])
        return {
            "verdetto": "nessuna base",
            "motivo": f"{repo} non è nell'indice.",
            "risultati": [result],
            "indice": index_meta(),
        }

    ready = is_ready(entry, full_match=True)
    result = entry_card(entry, matched=[], missing=[], ready=ready)
    fill_readmes([result])
    verdict = "base pronta" if ready else "base parziale"
    return {
        "verdetto": verdict,
        "motivo": (
            "Scheda senza una query di confronto. "
            "La base è pronta solo se il repository è attivo, non archiviato e ha una licenza indicata."
        ),
        "risultati": [result],
        "indice": index_meta(),
    }


def list_categories() -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    for entry in load_entries():
        category = str(entry.get("category") or "Senza categoria")
        subcategory = str(entry.get("subcategory") or "")
        counts.setdefault(category, {})
        counts[category][subcategory] = counts[category].get(subcategory, 0) + 1
    categories = []
    for category in sorted(counts):
        subs = [
            {"nome": name, "progetti": total}
            for name, total in sorted(counts[category].items(), key=lambda item: (-item[1], item[0]))
        ]
        categories.append(
            {
                "categoria": category,
                "progetti": sum(counts[category].values()),
                "ruolo": role_for(category),
                "sottocategorie": subs,
            }
        )
    return {"categorie": categories, "indice": index_meta()}


def extract_terms(query: str) -> list[str]:
    terms: list[str] = []
    for token in re.split(r"[\s,;:/|]+", query.lower()):
        cleaned = token.strip(".,;:!?\"'()[]{}")
        if not cleaned or cleaned in STOPWORDS:
            continue
        if len(cleaned) == 1 and cleaned != "x":
            continue
        if cleaned not in terms:
            terms.append(cleaned)
    return terms


def readme_highlights(text: str) -> list[dict[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    title: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        match = _HEADING.match(line.strip())
        if match:
            if title is not None:
                sections.append((title, body))
            title = match.group(1).strip()
            body = []
        elif title is not None:
            body.append(line)
    if title is not None:
        sections.append((title, body))

    picked: list[dict[str, str]] = []
    for section_title, section_body in sections:
        if not _INTERESTING.search(section_title):
            continue
        excerpt = section_excerpt(section_body)
        if not excerpt:
            continue
        picked.append({"sezione": section_title, "testo": excerpt})
        if len(picked) == 3:
            break
    return picked


def section_excerpt(body: list[str]) -> str:
    paragraph: list[str] = []
    fence: list[str] = []
    in_fence = False
    paragraph_closed = False
    for line in body:
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_fence:
                break
            in_fence = True
            continue
        if in_fence:
            if stripped and not is_noise(stripped):
                fence.append(stripped)
            continue
        if not stripped or is_noise(stripped):
            if paragraph:
                paragraph_closed = True
            continue
        if paragraph_closed:
            continue
        if sum(len(part) + 1 for part in paragraph) < 280:
            paragraph.append(stripped)
    text = " ".join(paragraph)
    if fence:
        text = f"{text} {' '.join(fence)}".strip()
    return " ".join(text.split())[:400]


def is_noise(line: str) -> bool:
    if line.startswith(("![", "[![", "<", "|", "---", "***")):
        return True
    plain = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
    plain = re.sub(r"\[[^\]]*\]\([^)]*\)", "", plain)
    plain = re.sub(r"<[^>]+>", "", plain)
    return not re.search(r"[A-Za-z0-9]", plain)


def search(
    terms: list[str],
    language: str | None,
    category: str | None,
    limit: int,
) -> list[tuple[dict[str, Any], list[str], list[str]]]:
    ranked: list[tuple[tuple[int, float], dict[str, Any], list[str]]] = []
    for entry in load_entries():
        if not entry.get("url") or not entry.get("name"):
            continue
        if category and category.lower() not in category_text(entry):
            continue
        if language and str(entry.get("lang") or "").lower() != language.lower():
            continue
        scored = score(entry, terms)
        if scored is None:
            continue
        matched_count, total, matched_terms = scored
        ranked.append(((matched_count, total), entry, matched_terms))
    ranked.sort(key=lambda item: (-item[0][0], -item[0][1]))
    hits: list[tuple[dict[str, Any], list[str], list[str]]] = []
    for _, entry, matched_terms in ranked[:limit]:
        missing = [term for term in terms if term not in matched_terms]
        hits.append((entry, matched_terms, missing))
    return hits


def score(entry: dict[str, Any], terms: list[str]) -> tuple[int, float, list[str]] | None:
    weighted_fields = fields(entry)
    matched_terms: list[str] = []
    total = 0.0
    for term in terms:
        best = 0.0
        for alternative in [term, *SYNONYMS.get(term, [])]:
            for weight, text in weighted_fields:
                if term_hit(alternative, text):
                    best = max(best, weight if alternative == term else weight * 0.7)
        if best:
            matched_terms.append(term)
            total += best
    if not matched_terms:
        return None
    total += 0.8 * math.log10((entry.get("stars") or 0) + 1)
    if entry.get("archived"):
        total -= 1.0
    pushed = str(entry.get("pushed") or "9999")
    cutoff = time.strftime("%Y", time.gmtime(time.time() - 3 * 365 * 86400))
    if pushed < cutoff:
        total -= 0.5
    return (len(matched_terms), total, matched_terms)


def fields(entry: dict[str, Any]) -> list[tuple[float, str]]:
    url = str(entry.get("url") or "")
    slug = url.rstrip("/").split("/")[-1]
    topics = entry.get("topics") or []
    if isinstance(topics, str):
        topics = [topics]
    topic_text = " ".join(str(topic) for topic in topics).lower().replace("-", " ")
    return [
        (3.0, str(entry.get("name") or "").lower()),
        (3.0, slug.lower().replace("-", " ").replace("_", " ")),
        (2.0, topic_text),
        (1.5, str(entry.get("desc") or "").lower()),
        (1.0, str(entry.get("subcategory") or "").lower()),
        (1.0, str(entry.get("category") or "").lower()),
        (1.0, str(entry.get("platform") or "").lower()),
    ]


def term_hit(term: str, text: str) -> bool:
    if len(term) <= 3:
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
    return term in text


def card_for(
    hit: tuple[dict[str, Any], list[str], list[str]],
    terms: list[str],
) -> dict[str, Any]:
    entry, matched, missing = hit
    full = not missing and len(matched) == len(terms)
    return entry_card(entry, matched, missing, is_ready(entry, full))


def entry_card(
    entry: dict[str, Any],
    matched: list[str],
    missing: list[str],
    ready: bool,
) -> dict[str, Any]:
    url = str(entry["url"])
    description = str(entry.get("desc") or "").strip()
    category = str(entry.get("category") or "")
    return {
        "nome": entry.get("name"),
        "repo": github_repo(url),
        "url": url,
        "stelle": entry.get("stars"),
        "lingua": entry.get("lang") or None,
        "licenza": entry.get("license") or None,
        "stato": health_label(entry),
        "ultimo_push": entry.get("pushed") or None,
        "categoria": category,
        "sottocategoria": entry.get("subcategory") or None,
        "descrizione": description,
        "termini_coperti": matched,
        "termini_mancanti": missing,
        "idoneita": "base pronta" if ready else "base parziale",
        "aiuto_concreto": {
            "cosa_copre": description,
            "ruolo": role_for(category),
            "dal_readme": [],
            "limiti": limits_for(entry, missing),
        },
    }


def fill_readmes(results: list[dict[str, Any]]) -> None:
    if not results:
        return
    urls = [str(result["url"]) for result in results]
    with ThreadPoolExecutor(max_workers=min(5, len(urls))) as pool:
        texts = list(pool.map(cached_readme, urls))
    for result, text in zip(results, texts, strict=True):
        help_block = result["aiuto_concreto"]
        if not text:
            help_block["limiti"].append(
                "README non recuperato: l'aiuto usa solo la scheda dell'indice."
            )
            continue
        highlights = readme_highlights(text)
        if highlights:
            help_block["dal_readme"] = highlights
            continue
        start = readme_start(text)
        if start:
            help_block["inizio_readme"] = start
            help_block["limiti"].append(
                "Il README non ha sezioni Installation, Usage o Features: è riportato solo l'inizio."
            )


def limits_for(entry: dict[str, Any], missing: list[str]) -> list[str]:
    limits: list[str] = []
    if missing:
        limits.append("Non copre questi termini della richiesta: " + ", ".join(missing) + ".")
    if entry.get("archived"):
        limits.append("Repo archiviata dall'autore: serve come riferimento, non come base da mantenere.")
    else:
        state = health_label(entry)
        if state == "ferma":
            limits.append("Ultimo push oltre 3 anni fa: un'API non ufficiale può essere già rotta.")
        elif state == "in rallentamento":
            limits.append("Ultimo push tra 1 e 3 anni fa.")
        elif state == "sconosciuta":
            limits.append("Data dell'ultimo push assente dall'indice.")
    if not str(entry.get("license") or "").strip():
        limits.append(
            "Licenza non indicata nell'indice: va trattata come tutti i diritti riservati."
        )
    return limits


def is_ready(entry: dict[str, Any], full_match: bool) -> bool:
    if not full_match or entry.get("archived"):
        return False
    if not str(entry.get("license") or "").strip():
        return False
    age = months_since(entry.get("pushed"))
    return age is not None and age <= 12


def health_label(entry: dict[str, Any]) -> str:
    if entry.get("archived"):
        return "archiviata"
    age = months_since(entry.get("pushed"))
    if age is None:
        return "sconosciuta"
    if age <= 12:
        return "attiva"
    if age <= 36:
        return "in rallentamento"
    return "ferma"


def months_since(pushed: Any) -> float | None:
    if not pushed:
        return None
    text = str(pushed)[:10]
    parsed: datetime | None = None
    for size, pattern in ((10, "%Y-%m-%d"), (7, "%Y-%m"), (4, "%Y")):
        if len(text) < size:
            continue
        try:
            parsed = datetime.strptime(text[:size], pattern).replace(tzinfo=timezone.utc)
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    return (datetime.now(timezone.utc) - parsed).days / 30.44


def overall_verdict(results: list[dict[str, Any]]) -> str:
    if any(result["idoneita"] == "base pronta" for result in results):
        return "base pronta"
    if results:
        return "base parziale"
    return "nessuna base"


def overall_reason(
    results: list[dict[str, Any]],
    terms: list[str],
    language: str | None,
    category: str | None,
) -> str:
    filters = []
    if language:
        filters.append(f"lingua {language}")
    if category:
        filters.append(f"categoria {category}")
    suffix = f" Filtri: {', '.join(filters)}." if filters else ""
    ready = [result["nome"] for result in results if result["idoneita"] == "base pronta"]
    if ready:
        names = ", ".join(str(name) for name in ready)
        return (
            "Almeno un progetto copre tutti i termini, è attivo, non è archiviato "
            f"e ha una licenza indicata: {names}.{suffix}"
        )
    if results:
        return (
            "Ci sono progetti collegati, ma nessuno è insieme completo sui termini, "
            f"attivo e con licenza indicata. Termini usati: {', '.join(terms)}.{suffix}"
        )
    scope = (
        " L'indice elenca solo progetti di interoperabilità già catalogati e lascia fuori "
        "exploit, jailbreak, bypass e rimozione DRM."
    )
    return (
        "Nessun progetto dell'indice copre questi termini. Allarga la ricerca al nome del "
        f"prodotto, del produttore o del protocollo.{suffix}{scope}"
    )


def role_for(category: str) -> str:
    if category in CATEGORY_ROLE:
        return CATEGORY_ROLE[category]
    if not category:
        return "Categoria assente dall'indice: usa la descrizione e il README."
    return (
        f"Progetto catalogato come {category}: la descrizione dice a cosa serve "
        "e il README dice come si installa."
    )


def category_text(entry: dict[str, Any]) -> str:
    return f"{entry.get('category') or ''} {entry.get('subcategory') or ''}".lower()


def github_repo(url: str) -> str:
    match = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", url)
    if not match:
        return url
    return f"{match.group(1)}/{match.group(2)}"


def find_entry(entries: list[dict[str, Any]], ref: str) -> dict[str, Any] | None:
    normalized = ref.strip().rstrip("/").lower()
    normalized = re.sub(r"^https?://(www\.)?", "", normalized)
    if "/" in normalized and not normalized.startswith(("github.com", "gitlab.com", "codeberg.org")):
        normalized = "github.com/" + normalized
    for entry in entries:
        url = re.sub(r"^https?://(www\.)?", "", str(entry.get("url") or "").rstrip("/").lower())
        if url == normalized:
            return entry
    return None


def readme_start(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or is_noise(stripped):
            continue
        kept.append(stripped)
        if len(kept) == 4:
            break
    return " ".join(kept)[:400]


def cached_readme(url: str) -> str | None:
    with _lock:
        if url in _readmes:
            return _readmes[url]
    text = github_readme(url)
    with _lock:
        _readmes[url] = text
    return text


def github_readme(url: str) -> str | None:
    match = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", url)
    if not match:
        return None
    request = urllib.request.Request(
        f"https://api.github.com/repos/{match.group(1)}/{match.group(2)}/readme",
        headers={
            "Accept": "application/vnd.github.raw",
            "User-Agent": "starting-base",
        },
    )
    token = github_token()
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(120_000)
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    text = raw.decode("utf-8", "replace")
    if text.lstrip().startswith("{") and '"message"' in text[:180]:
        return None
    return text


def github_token() -> str:
    global _token
    with _lock:
        if _token is not None:
            return _token
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        if not token:
            try:
                result = subprocess.run(
                    ["gh", "auth", "token"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired):
                result = None
            if result is not None and result.returncode == 0:
                token = result.stdout.strip()
        _token = token
        return _token


def load_entries() -> list[dict[str, Any]]:
    global _entries, _loaded_mtime
    path = ensure_cache()
    mtime = path.stat().st_mtime
    with _lock:
        if _entries is not None and _loaded_mtime == mtime:
            return _entries
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("entries", [])
        if not isinstance(data, list):
            raise FileNotFoundError("L'indice non è un elenco di progetti.")
        _entries = data
        _loaded_mtime = mtime
        return _entries


def ensure_cache() -> Path:
    override = os.environ.get("RE_INDEX_DATA")
    if override:
        path = Path(override)
        if not path.is_file():
            raise FileNotFoundError(f"RE_INDEX_DATA non è un file: {path}")
        return path
    fresh = CACHE.is_file() and (time.time() - CACHE.stat().st_mtime) < MAX_AGE_SECONDS
    if fresh:
        return CACHE
    try:
        with urllib.request.urlopen(RAW_INDEX, timeout=60) as response:
            payload = response.read()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        temporary = CACHE.with_suffix(".json.tmp")
        temporary.write_bytes(payload)
        temporary.replace(CACHE)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        if CACHE.is_file():
            logger.warning("indice non aggiornato: %s", exc)
            return CACHE
        raise FileNotFoundError(
            f"Indice non scaricabile e nessuna cache locale ({exc})."
        ) from exc
    return CACHE


def index_meta() -> dict[str, Any]:
    path = ensure_cache()
    updated = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    return {
        "aggiornato": updated,
        "progetti": len(load_entries()),
        "fonte": INDEX_SOURCE,
    }


def clamp_limit(limit: int) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return 5
    return min(5, max(1, value))
