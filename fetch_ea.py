"""Trae los datos del club desde la API de Clubes de EA y los guarda en data/.

- data/club.json     -> resumen del club (se reemplaza en cada corrida)
- data/members.json  -> stats de temporada por jugador (se reemplaza)
- data/matches.json  -> historial de partidos (se ACUMULA, sin duplicados)
"""
import json, os, sys, time, urllib.request, urllib.parse

CLUB_ID = os.environ.get("CLUB_ID", "1497050")
PLATFORM = os.environ.get("PLATFORM", "common-gen5")
BASE = "https://proclubs.ea.com/api/fc"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.ea.com/",
    "Origin": "https://www.ea.com",
}


try:
    # EA rechaza clientes que no parecen un navegador; curl_cffi imita la conexión de Chrome.
    from curl_cffi import requests as cffi
except ImportError:
    cffi = None


def fetch(url):
    if cffi:
        r = cffi.get(url, headers={k: v for k, v in HEADERS.items() if k != "User-Agent"},
                     impersonate="chrome", timeout=20)
        r.raise_for_status()
        return r.json()
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path, **params):
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(3):
        try:
            return fetch(url)
        except Exception as e:  # 403, timeouts, etc.
            last = e
            print(f"  intento {attempt + 1} falló: {path}: {e}")
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"No se pudo leer {path}: {last}")


def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else default


def save(name, obj):
    with open(os.path.join(DATA, name), "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def main():
    os.makedirs(DATA, exist_ok=True)
    ok = 0

    # 1) Partidos: se juntan con los que ya teníamos
    stored = {m["matchId"]: m for m in load("matches.json", [])}
    before = len(stored)
    for mt, label in (("leagueMatch", "Liga"), ("playoffMatch", "Playoff"), ("friendlyMatch", "Amistoso")):
        try:
            got = get("clubs/matches", matchType=mt, platform=PLATFORM, clubIds=CLUB_ID)
            ok += 1
            for m in got or []:
                m["_type"] = label  # de qué lista vino el partido
                stored[m["matchId"]] = m
            print(f"{mt}: {len(got or [])} partidos recibidos")
        except RuntimeError as e:
            print(e)
    matches = sorted(stored.values(), key=lambda m: m["timestamp"], reverse=True)
    save("matches.json", matches)
    print(f"Historial: {before} -> {len(matches)} partidos")

    # 2) Stats de temporada por jugador
    try:
        save("members.json", get("members/stats", platform=PLATFORM, clubId=CLUB_ID))
        ok += 1
    except RuntimeError as e:
        print(e)

    # 3) Resumen del club (récord, división...)
    try:
        club = load("club.json", {"clubName": ""})
        res = get("allTimeLeaderboard/search", platform=PLATFORM, clubName=club.get("clubName") or "Fusion Esports")
        hit = next((c for c in res or [] if str(c.get("clubId")) == CLUB_ID), None)
        if hit:
            info = hit.get("clubInfo", {})
            flat = {k: v for k, v in hit.items() if k != "clubInfo"}
            flat["clubName"] = hit.get("clubName") or info.get("name")
            flat["stadName"] = (info.get("customKit") or {}).get("stadName", club.get("stadName", ""))
            flat["platform"] = PLATFORM
            save("club.json", flat)
            ok += 1
    except RuntimeError as e:
        print(e)

    if ok == 0:
        print("EA no respondió a ninguna petición.")
        sys.exit(1)


if __name__ == "__main__":
    main()
