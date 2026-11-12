"""Junta los partidos guardados de la API de Clubes de EA y calcula las stats del dashboard.

Uso: python3 build_stats.py data/ stats.json
- data/club.json        -> resumen del club (allTimeLeaderboard/search)
- data/*.json (resto)   -> listas de partidos (clubs/matches), se juntan sin duplicar
- data/members.json     -> opcional, stats de temporada por jugador (members/stats)
"""
import json, sys, glob, os, datetime
from collections import Counter, defaultdict

data_dir, out_path = sys.argv[1], sys.argv[2]
club = json.load(open(os.path.join(data_dir, "club.json")))
CID = str(club["clubId"])

TYPE_LABEL = {"1": "Liga", "5": "Playoff", "9": "Amistoso"}
POS_ES = {"goalkeeper": "POR", "defender": "DEF", "midfielder": "MED", "forward": "DEL"}

matches = {}
for f in sorted(glob.glob(os.path.join(data_dir, "*.json"))):
    name = os.path.basename(f)
    if name in ("club.json", "members.json"):
        continue
    raw = json.load(open(f))
    if not isinstance(raw, list):
        continue
    for m in raw:
        if CID in m.get("clubs", {}):
            matches[m["matchId"]] = m

def num(x, cast=int):
    try:
        return cast(x)
    except (TypeError, ValueError):
        return cast(0)

rows = []
lines = []  # una fila por jugador y partido

for m in sorted(matches.values(), key=lambda m: m["timestamp"], reverse=True):
    me = m["clubs"][CID]
    opp_id = next(c for c in m["clubs"] if c != CID)
    opp = m["clubs"][opp_id]
    gf, ga = num(me["goals"]), num(opp["goals"])
    res = "G" if me.get("wins") == "1" else "P" if me.get("losses") == "1" else "E"
    dnf = me.get("winnerByDnf") == "1" or opp.get("winnerByDnf") == "1"
    mtype = m.get("_type") or TYPE_LABEL.get(me.get("matchType"), "Otro")
    scorers, assisters, motm, lineup = [], [], None, []
    for pid, p in m.get("players", {}).get(CID, {}).items():
        n = p["playername"]
        g, a = num(p["goals"]), num(p["assists"])
        pos = POS_ES.get(p.get("pos"), p.get("pos"))
        if g: scorers.append({"name": n, "n": g})
        if a: assisters.append({"name": n, "n": a})
        if p.get("mom") == "1": motm = n
        lineup.append({"name": n, "pos": pos, "rating": num(p["rating"], float), "g": g, "a": a})
        lines.append({"type": mtype, "name": n, "pos": pos, "res": res, "rating": num(p["rating"], float),
                      "sec": num(p["secondsPlayed"]), "g": g, "a": a, "shots": num(p["shots"]),
                      "pm": num(p["passesmade"]), "pa": num(p["passattempts"]),
                      "tm": num(p["tacklesmade"]), "ta": num(p["tackleattempts"]),
                      "mom": 1 if p.get("mom") == "1" else 0})
    lineup.sort(key=lambda x: -x["rating"])
    rows.append({
        "id": m["matchId"], "ts": m["timestamp"], "type": mtype,
        "opp": opp["details"]["name"].strip() if opp.get("details") else "Rival",
        "gf": gf, "ga": ga, "res": res, "dnf": dnf, "motm": motm,
        "scorers": sorted(scorers, key=lambda x: -x["n"]),
        "assists": sorted(assisters, key=lambda x: -x["n"]),
        "lineup": lineup,
    })


def players_from(ls):
    by = defaultdict(list)
    for l in ls:
        by[l["name"]].append(l)
    out = []
    for n, L in by.items():
        sec = sum(l["sec"] for l in L); mins = sec / 60
        p90 = (lambda v: round(v * 90 / mins, 2) if mins >= 1 else 0)
        tot = lambda k: sum(l[k] for l in L)
        out.append({
            "name": n, "pos": Counter(l["pos"] for l in L).most_common(1)[0][0],
            "pj": len(L), "min": round(mins),
            "rating": round(sum(l["rating"] for l in L) / len(L), 2),
            "g": tot("g"), "a": tot("a"), "ga90": p90(tot("g") + tot("a")),
            "shots": tot("shots"),
            "passPct": round(100 * tot("pm") / tot("pa")) if tot("pa") else None,
            "pass90": p90(tot("pm")),
            "tacklePct": round(100 * tot("tm") / tot("ta")) if tot("ta") else None,
            "tackles90": p90(tot("tm")),
            "mom": tot("mom"), "wins": sum(1 for l in L if l["res"] == "G"),
        })
    out.sort(key=lambda p: (-p["rating"], -p["min"]))
    return out


def summary_from(rs):
    s = Counter()
    for r in rs:
        s["pj"] += 1; s[r["res"]] += 1
        s["gf"] += r["gf"]; s["ga"] += r["ga"]
        s["cs"] += 1 if r["ga"] == 0 else 0
    return dict(s)


filters = {"Todos": None, "Liga": "Liga", "Playoff": "Playoff", "Amistoso": "Amistoso"}
by_type = {}
for key, typ in filters.items():
    rs = [r for r in rows if typ is None or r["type"] == typ]
    ls = [l for l in lines if typ is None or l["type"] == typ]
    by_type[key] = {"summary": summary_from(rs), "players": players_from(ls)}

members = None
mp = os.path.join(data_dir, "members.json")
if os.path.exists(mp):
    members = json.load(open(mp))

out = {
    "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "club": club,
    "matches": rows,
    "byType": by_type,
    "members": members,
}
json.dump(out, open(out_path, "w"), ensure_ascii=False, indent=1)
print(f"{len(rows)} partidos, {len(lines)} líneas de jugador -> {out_path}")
