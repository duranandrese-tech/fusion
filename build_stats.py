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
players = defaultdict(lambda: Counter())
player_pos = defaultdict(Counter)
player_ratings = defaultdict(list)

for m in sorted(matches.values(), key=lambda m: m["timestamp"], reverse=True):
    me = m["clubs"][CID]
    opp_id = next(c for c in m["clubs"] if c != CID)
    opp = m["clubs"][opp_id]
    gf, ga = num(me["goals"]), num(opp["goals"])
    if me.get("wins") == "1":
        res = "G"
    elif me.get("losses") == "1":
        res = "P"
    else:
        res = "E"
    dnf = me.get("winnerByDnf") == "1" or opp.get("winnerByDnf") == "1"
    plist = m.get("players", {}).get(CID, {})
    scorers, assisters, motm, lineup = [], [], None, []
    for pid, p in plist.items():
        n = p["playername"]
        g, a = num(p["goals"]), num(p["assists"])
        if g: scorers.append({"name": n, "n": g})
        if a: assisters.append({"name": n, "n": a})
        if p.get("mom") == "1": motm = n
        lineup.append({"name": n, "pos": POS_ES.get(p.get("pos"), p.get("pos")), "rating": num(p["rating"], float),
                       "g": g, "a": a})
        s = players[n]
        s["pj"] += 1
        s["sec"] += num(p["secondsPlayed"])
        s["g"] += g; s["a"] += a
        s["shots"] += num(p["shots"])
        s["pm"] += num(p["passesmade"]); s["pa"] += num(p["passattempts"])
        s["tm"] += num(p["tacklesmade"]); s["ta"] += num(p["tackleattempts"])
        s["mom"] += 1 if p.get("mom") == "1" else 0
        s["red"] += num(p["redcards"])
        s["w"] += 1 if res == "G" else 0
        player_pos[n][POS_ES.get(p.get("pos"), p.get("pos"))] += 1
        player_ratings[n].append(num(p["rating"], float))
    lineup.sort(key=lambda x: -x["rating"])
    rows.append({
        "id": m["matchId"],
        "ts": m["timestamp"],
        "type": TYPE_LABEL.get(me.get("matchType"), "Otro"),
        "opp": opp["details"]["name"].strip() if opp.get("details") else "Rival",
        "gf": gf, "ga": ga, "res": res, "dnf": dnf,
        "motm": motm,
        "scorers": sorted(scorers, key=lambda x: -x["n"]),
        "assists": sorted(assisters, key=lambda x: -x["n"]),
        "lineup": lineup,
    })

plist = []
for n, s in players.items():
    mins = s["sec"] / 60
    p90 = (lambda v: round(v * 90 / mins, 2) if mins >= 1 else 0)
    plist.append({
        "name": n,
        "pos": player_pos[n].most_common(1)[0][0],
        "pj": s["pj"], "min": round(mins),
        "rating": round(sum(player_ratings[n]) / len(player_ratings[n]), 2),
        "g": s["g"], "a": s["a"], "ga90": p90(s["g"] + s["a"]),
        "shots": s["shots"],
        "passPct": round(100 * s["pm"] / s["pa"]) if s["pa"] else None,
        "pass90": p90(s["pm"]),
        "tacklePct": round(100 * s["tm"] / s["ta"]) if s["ta"] else None,
        "tackles90": p90(s["tm"]),
        "mom": s["mom"], "wins": s["w"],
    })
plist.sort(key=lambda p: (-p["rating"], -p["min"]))

summary = Counter()
for r in rows:
    summary["pj"] += 1
    summary[r["res"]] += 1
    summary["gf"] += r["gf"]; summary["ga"] += r["ga"]
    summary["cs"] += 1 if r["ga"] == 0 else 0

members = None
mp = os.path.join(data_dir, "members.json")
if os.path.exists(mp):
    members = json.load(open(mp))

out = {
    "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "club": club,
    "summary": dict(summary),
    "matches": rows,
    "players": plist,
    "members": members,
}
json.dump(out, open(out_path, "w"), ensure_ascii=False, indent=1)
print(f"{len(rows)} partidos, {len(plist)} jugadores -> {out_path}")
