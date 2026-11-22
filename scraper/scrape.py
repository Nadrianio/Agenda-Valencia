#!/usr/bin/env python3
"""Actualiza events.json leyendo las agendas de varias salas de València.
Solo usa la biblioteca estándar de Python (sin instalar nada)."""
import json, re, sys, time, html, unicodedata, datetime as dt, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "events.json"
EXTRA = ROOT / "manual" / "extra.json"
UA = "Mozilla/5.0 (compatible; AgendaValenciaBot/1.0)"
TODAY = dt.date.today()

MONTHS = {"enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,"julio":7,
          "agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12}
ABBR = {"ENE":1,"FEB":2,"MAR":3,"ABR":4,"MAY":5,"JUN":6,"JUL":7,"AGO":8,"SEP":9,"OCT":10,"NOV":11,"DIC":12}

# Para añadir una sala: copia una línea y cambia id, url, venue y cat.
# kind: "loco" (lista de texto "21 de noviembre a las 21:00 h – Grupo – Desde 15 €"),
#       "16t" (formato de 16toneladas.com), "ldjson" (páginas con datos schema.org/Event).
SOURCES = [
    {"id": "loco", "kind": "loco", "venue": "Loco Club", "cat": "Música",
     "url": "https://www.visitvalencia.com/agenda-valencia/conciertos-en-loco-club-la-sala-mas-eclectica-de-valencia"},
    {"id": "16t", "kind": "16t", "venue": "16 Toneladas", "cat": "Música",
     "url": "https://www.16toneladas.com/"},
    # La Ganzúa agrupa conciertos de muchas salas. Solo se guardan las salas de VENUES_GANZUA.
    {"id": "ganzua", "kind": "laganzua", "venue": "", "cat": "Música",
     "url": "https://www.laganzua.net/conciertos/valencia",
     "urls": ["https://www.laganzua.net/conciertos/salas-conciertos/sala-jerusalem",
              "https://www.laganzua.net/conciertos/valencia"]
             + ["https://www.laganzua.net/conciertos/valencia-pagina-%d" % n for n in range(2, 9)]},
    # XCEED: fiestas y clubes. Solo se guardan eventos de Valencia (la web puede cambiar de formato).
    {"id": "xceed", "kind": "xceed", "venue": "", "cat": "Música",
     "url": "https://xceed.me/en/valencia/events", "accept": "text/markdown, text/html;q=0.9",
     "urls": ["https://xceed.me/en", "https://xceed.me/en/valencia/events"]},
    # Cartelera de cines (SensaCine). La página estática solo trae las sesiones del día en que se lee.
    {"id": "babel", "kind": "sensacine", "venue": "Cines Babel", "cat": "Cartelera",
     "url": "https://www.sensacine.com/cines/cine/E0119/"},
    {"id": "lys", "kind": "sensacine", "venue": "Cines Lys", "cat": "Cartelera",
     "url": "https://www.sensacine.com/cines/cine/E0187/"},
    {"id": "rialto", "kind": "ldjson", "venue": "Teatro Rialto", "cat": "Teatro",
     "url": "https://ivc.gva.es/es/ivc/programacion-ivc/teatro-rialto-de-valencia"},
]

def fetch(url, accept=None):
    hdr = {"User-Agent": UA, "Accept-Language": "es"}
    if accept: hdr["Accept"] = accept
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def lines_of(raw):
    raw = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", raw)
    raw = re.sub(r"(?is)<!--.*?-->", " ", raw)
    # Las etiquetas en línea (a, span, strong...) no deben partir una frase en dos líneas.
    raw = re.sub(r"(?is)</?(?:a|span|b|strong|em|i|u|small|abbr|time|font|mark|sup|sub|label)(?:\s[^>]*)?>", " ", raw)
    raw = re.sub(r"<[^>]+>", "\n", raw)
    return [re.sub(r"\s+", " ", l).strip() for l in html.unescape(raw).split("\n") if l.strip()]

def iso(month, day):
    d = dt.date(TODAY.year, month, day)
    if d < TODAY - dt.timedelta(days=90):
        d = dt.date(TODAY.year + 1, month, day)
    return d.isoformat()

def ev(src, d, h, t, p="", u=None):
    return {"d": d, "h": h or "", "t": t.strip(), "c": src["cat"], "v": src["venue"],
            "p": p or "", "u": u or src.get("_url") or src["url"], "s": src["id"]}

def parse_loco(raw, src):
    out = []
    pat = re.compile(r"^(\d{1,2}) de ([a-záéíóú]+) a las (\d{1,2}:\d{2}) h\s*[–-]\s*(.+)$", re.I)
    for l in lines_of(raw):
        m = pat.match(l)
        if not m or m.group(2).lower() not in MONTHS:
            continue
        rest = m.group(4)
        pm = re.search(r"\s[–-]\s*(Desde\s[\d.,]+\s*€)\s*$", rest)
        price = pm.group(1) if pm else ""
        title = rest[:pm.start()] if pm else rest
        out.append(ev(src, iso(MONTHS[m.group(2).lower()], int(m.group(1))), m.group(3).zfill(5), title, price))
    return out

def parse_16t(raw, src):
    out, L = [], lines_of(raw)
    pat = re.compile(r"^([A-ZÁ]{3})\s*[·•.]\s*(\d{1,2})\s*[·•.]\s*[A-ZÁ]{3}\s*[·•.]\s*(\d{1,2}:\d{2})\s*h?", re.I)
    for i, l in enumerate(L):
        m = pat.match(l)
        if not m or m.group(1).upper() not in ABBR or i == 0:
            continue
        title = L[i - 1]
        if pat.match(title) or len(title) > 120:
            continue
        out.append(ev(src, iso(ABBR[m.group(1).upper()], int(m.group(2))), m.group(3).zfill(5), title.title() if title.isupper() else title))
    return out


def norm(x):
    return unicodedata.normalize("NFD", x).encode("ascii", "ignore").decode().lower()

# Salas que se guardan de La Ganzúa (basta con que el nombre contenga estas palabras).
# Para añadir otra sala, añade su nombre aquí.
VENUES_GANZUA = ["jerusalem", "hifi", "killing time", "hielo", "mat32", "moon", "rock city",
                 "matisse", "radio city", "wah wah", "black note"]

def parse_laganzua(raw, src):
    out, L = [], lines_of(raw)
    pat = re.compile(r"^Fecha\s+(?:[a-záéíóú]+\s+)?(\d{1,2}) de ([a-záéíóú]+) de (\d{4})", re.I)
    for i, l in enumerate(L):
        m = pat.match(l)
        if not m or m.group(2).lower() not in MONTHS:
            continue
        try: d = dt.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError: continue
        j = i - 1
        while j >= 0 and L[j].startswith("|"): j -= 1
        if j < 0: continue
        title = re.sub(r"\s+en\s+(Valencia|València)$", "", L[j]).strip()
        venue, price = None, ""
        for k in range(i + 1, min(i + 9, len(L))):
            if pat.match(L[k]): break
            if L[k].startswith("Ciudad") and venue is None:
                rest = L[k][6:].strip()
                nxt = L[k + 1] if k + 1 < len(L) else ""
                cands = [c for c in (rest, nxt) if norm(c) not in ("valencia", "")]
                if "valencia" in (norm(rest), norm(nxt)) and cands:
                    venue = cands[0]
            pm = re.match(r"^Precio:\s*([\d.,]+)", L[k])
            if pm:
                try:
                    v = float(pm.group(1).replace(",", "."))
                    price = "Gratis" if v == 0 else ("%d €" % v if v == int(v) else ("%.2f €" % v).replace(".", ","))
                except ValueError: pass
        if not venue or not any(w in norm(venue) for w in VENUES_GANZUA):
            continue
        e = ev(src, d, "", title, price)
        e["v"] = venue
        out.append(e)
    return out

VERSIONS = {"espanola": "Español", "doblada": "Doblada", "v.o": "V.O.", "v.o.": "V.O.", "v.o.s.e.": "V.O.", "vose": "V.O."}

def version_label(txt):
    t = norm(txt).replace("en version ", "").replace("en ", "").strip()
    return VERSIONS.get(t, txt.replace("En ", "").strip())

def parse_sensacine(raw, src):
    """Cartelera de un cine: una película = un evento por día, con sus sesiones en el campo x."""
    L = lines_of(raw)
    rel = re.compile(r"^\d{1,2} de [a-záéíóú]+ de \d{4} \|")
    ses = re.compile(r"^(\d{1,2}) de ([a-záéíóú]+) de (\d{4}) - (.+)$", re.I)
    tim = re.compile(r"^(\d{1,2}:\d{2})\b")
    films, cur, key = [], None, None
    for i, l in enumerate(L):
        if rel.match(l) and i > 0:
            cur = {"t": L[i - 1].strip(), "s": {}}; films.append(cur); key = None; continue
        m = ses.match(l)
        if m and cur is not None and m.group(2).lower() in MONTHS:
            d = dt.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
            key = (d, version_label(m.group(4)))
            cur["s"].setdefault(key, [])
            continue
        t = tim.match(l)
        if t and cur is not None and key and t.group(1).zfill(5) not in cur["s"][key]:
            cur["s"][key].append(t.group(1).zfill(5))
    out = []
    for f in films:
        by_day = {}
        for (d, v), times in f["s"].items():
            if times: by_day.setdefault(d, []).append((v, sorted(times)))
        for d, groups in by_day.items():
            allt = sorted(t for _, ts in groups for t in ts)
            x = " · ".join("%s %s" % (v, " · ".join(ts)) for v, ts in sorted(groups))
            e = ev(src, d, allt[0], f["t"])
            e["x"] = x
            out.append(e)
    return out

EN_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
             "august", "september", "october", "november", "december"], 1)}

def parse_xceed(raw, src):
    """Eventos de Valencia en xceed.me. Entiende la lista con enlaces tipo
    [Título](https://xceed.me/en/valencia/event/...) — November 28, 2026 at [Sala](...) y, como plan B, HTML."""
    out = []
    dpat = r"([A-Za-z]+) (\d{1,2}), (\d{4})"
    cands = []
    for m in re.finditer(r"\[([^\]]+)\]\((https://xceed\.me/[a-z]{2}/valencia/event/[^)\s]+)\)\s*[—-]\s*" + dpat + r"(?:\s+at\s+\[([^\]]+)\]\([^)]*\))?", raw):
        cands.append((m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)))
    if not cands:  # plan B: HTML con enlaces a /valencia/event/
        for m in re.finditer(r'(?is)<a[^>]+href="((?:https://xceed\.me)?/[a-z]{2}/valencia/event/[^"]+)"[^>]*>(.*?)</a>', raw):
            L = lines_of(m.group(2))
            di = next((i for i, l in enumerate(L) if re.search(dpat, l)), None)
            if di is None or not L: continue
            dm = re.search(dpat, L[di])
            url = m.group(1) if m.group(1).startswith("http") else "https://xceed.me" + m.group(1)
            venue = L[di + 1] if di + 1 < len(L) else ""
            cands.append((L[0], url, dm.group(1), dm.group(2), dm.group(3), venue))
    for title, url, mon, day, year, venue in cands:
        mo = EN_MONTHS.get(mon.lower())
        if not mo: continue
        try: d = dt.date(int(year), mo, int(day)).isoformat()
        except ValueError: continue
        e = ev(src, d, "", title, "", url)
        e["v"] = (venue or "Valencia").strip()
        out.append(e)
    return out

def walk(x):
    if isinstance(x, list):
        for i in x: yield from walk(i)
    elif isinstance(x, dict):
        yield x
        for v in x.values():
            if isinstance(v, (list, dict)): yield from walk(v)

def guess_cat(name, typ, default):
    s = (name + " " + typ).lower()
    if any(k in s for k in ("film", "cine", "screening", "proyecc")): return "Cine"
    if any(k in s for k in ("exposic", "visualarts", "galer")): return "Arte"
    if any(k in s for k in ("teatro", "theater", "danza", "obra")): return "Teatro"
    if any(k in s for k in ("music", "concierto", "dj", "live")): return "Música"
    return default

def parse_ldjson(raw, src):
    out = []
    for blk in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', raw):
        try: data = json.loads(blk)
        except ValueError: continue
        for o in walk(data):
            typ = o.get("@type", "")
            typ = " ".join(typ) if isinstance(typ, list) else str(typ)
            if "Event" not in typ or not o.get("name") or not o.get("startDate"):
                continue
            sd = str(o["startDate"])
            try: d = dt.date.fromisoformat(sd[:10]).isoformat()
            except ValueError: continue
            h = sd[11:16] if "T" in sd and sd[11:16] != "00:00" else ""
            loc = o.get("location")
            venue = loc.get("name") if isinstance(loc, dict) else None
            price = ""
            off = o.get("offers")
            off = off[0] if isinstance(off, list) and off else off
            if isinstance(off, dict):
                pr = off.get("price", off.get("lowPrice"))
                if pr is not None:
                    try: price = "Gratis" if float(pr) == 0 else "Desde %s €" % str(pr).replace(".", ",")
                    except ValueError: pass
            e = ev(src, d, h, str(o["name"]), price, o.get("url") if str(o.get("url", "")).startswith("https://") else None)
            e["c"] = guess_cat(e["t"], typ, src["cat"])
            if venue: e["v"] = venue
            out.append(e)
    return out

PARSERS = {"xceed": parse_xceed, "sensacine": parse_sensacine, "laganzua": parse_laganzua, "loco": parse_loco, "16t": parse_16t, "ldjson": parse_ldjson}

def main():
    try: prev = json.loads(OUT.read_text(encoding="utf-8")).get("events", [])
    except Exception: prev = []
    events, failed = [], set()
    for src in SOURCES:
        found = []
        for u in src.get("urls", [src["url"]]):
            try:
                src["_url"] = u
                raw = fetch(u, src.get("accept"))
                got = PARSERS[src["kind"]](raw, src)
                found += got
                if not got:  # diagnóstico: qué ha visto el script en la página
                    L = lines_of(raw)
                    print("  [diagnóstico] %s: %d bytes, %d líneas de texto" % (u, len(raw), len(L)))
                    for l in L[:12]:
                        print("    | " + l[:110])
            except Exception as ex:
                print("%-8s ERROR en %s: %s" % (src["id"], u, ex), file=sys.stderr)
            time.sleep(2)  # una petición cada pocos segundos, por cortesía
        print("%-8s %d eventos" % (src["id"], len(found)))
        if not found: failed.add(src["id"])
        events += found
    # Si una sala falla, se conservan sus eventos anteriores (y los de ejemplo iniciales).
    events += [e for e in prev if e.get("s") in failed or e.get("s") == "seed"]
    try:
        for e in json.loads(EXTRA.read_text(encoding="utf-8")):
            e.setdefault("s", "manual"); events.append(e)
    except Exception: pass
    seen, final = set(), []
    for e in sorted(events, key=lambda e: (e["d"], e.get("h") or "~", e["t"])):
        k = (e["d"], e["t"].lower(), e.get("v", ""))
        if (e.get("d2") or e["d"]) >= TODAY.isoformat() and k not in seen:
            seen.add(k); final.append(e)
    if not final:
        print("Sin eventos: no se sobrescribe events.json", file=sys.stderr); sys.exit(1)
    OUT.write_text(json.dumps({"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                               "events": final}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Total: %d eventos" % len(final))

if __name__ == "__main__":
    main()
