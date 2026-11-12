"""Junta los partidos guardados de la API de Clubes de EA y prepara stats.json para la web.

Uso: python3 build_stats.py data/ docs/stats.json
- data/club.json     -> resumen del club (allTimeLeaderboard/search)
- data/matches.json  -> historial de partidos (y cualquier otra lista de partidos en data/)
- data/members.json  -> stats de temporada por jugador (members/stats), opcional

Cada partido sale con la línea completa de cada jugador humano; la web calcula
resúmenes, sesiones, premios, análisis táctico y tendencias a partir de eso.
"""
import json, sys, glob, os, datetime

data_dir, out_path = sys.argv[1], sys.argv[2]
club = json.load(open(os.path.join(data_dir, "club.json")))
CID = str(club["clubId"])

TYPE_LABEL = {"1": "Liga", "5": "Playoff", "9": "Amistoso"}
POS_ES = {"goalkeeper": "POR", "defender": "DEF", "midfielder": "MED", "forward": "DEL"}


def num(x, cast=int):
    try:
        return cast(x)
    except (TypeError, ValueError):
        return cast(0)


matches = {}
for f in sorted(glob.glob(os.path.join(data_dir, "*.json"))):
    if os.path.basename(f) in ("club.json", "members.json"):
        continue
    raw = json.load(open(f))
    if isinstance(raw, list):
        for m in raw:
            if CID in m.get("clubs", {}):
                matches[m["matchId"]] = m

rows = []
for m in sorted(matches.values(), key=lambda m: m["timestamp"], reverse=True):
    me = m["clubs"][CID]
    opp_id = next(c for c in m["clubs"] if c != CID)
    opp = m["clubs"][opp_id]
    gf, ga = num(me["goals"]), num(opp["goals"])
    # En amistosos EA no llena wins/losses, así que se decide por el marcador
    if me.get("winnerByDnf") == "1":
        res = "G"
    elif opp.get("winnerByDnf") == "1":
        res = "P"
    else:
        res = "G" if gf > ga else "P" if gf < ga else "E"
    dnf = me.get("winnerByDnf") == "1" or opp.get("winnerByDnf") == "1"
    lineup = []
    for pid, p in m.get("players", {}).get(CID, {}).items():
        lineup.append({
            "name": p["playername"],
            "pos": POS_ES.get(p.get("pos"), p.get("pos") or "?"),
            "rating": num(p.get("rating"), float),
            "sec": num(p.get("secondsPlayed")),
            "g": num(p.get("goals")), "a": num(p.get("assists")),
            "sh": num(p.get("shots")),
            "pm": num(p.get("passesmade")), "pa": num(p.get("passattempts")),
            "tm": num(p.get("tacklesmade")), "ta": num(p.get("tackleattempts")),
            "sv": num(p.get("saves")), "gc": num(p.get("goalsconceded")),
            "red": num(p.get("redcards")),
            "mom": 1 if p.get("mom") == "1" else 0,
        })
    lineup.sort(key=lambda x: -x["rating"])
    rows.append({
        "id": m["matchId"], "ts": m["timestamp"],
        "type": m.get("_type") or TYPE_LABEL.get(me.get("matchType"), "Otro"),
        "opp": (opp.get("details") or {}).get("name", "Rival").strip(),
        "gf": gf, "ga": ga, "res": res, "dnf": dnf,
        "lineup": lineup,
    })

members = None
mp = os.path.join(data_dir, "members.json")
if os.path.exists(mp):
    members = json.load(open(mp))

out = {
    "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "club": club,
    "matches": rows,
    "members": members,
}
with open(out_path, "w") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"{len(rows)} partidos -> {out_path}")
