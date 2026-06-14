# -*- coding: utf-8 -*-
"""
🦉 Fanta Gufo Mondiale 2026 — Dashboard Utenti
"""
import streamlit as st
import json
import os
import pandas as pd
from collections import defaultdict

st.set_page_config(
    page_title="🦉 Fanta Gufo 2026 — Dashboard",
    page_icon="🦉",
    layout="wide",
)

DATA_FILE = "fanta_gufo_data.json"
RESULTS_FILE = "results.json"
PARTICIPANTS = ["Andrea","Fabio","Gabriele","Giampaolo","Lorenzo","Manuel","Marco","Nino","Pasquale","Roberto","Simone","Umberto","Walter"]
GROUPS = ["A","B","C","D","E","F","G","H","I","J","K","L"]

@st.cache_data
def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def load_corrections():
    if os.path.exists("corrections.json"):
        with open("corrections.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_match_dict(data):
    return {str(m["id"]): m for m in data["partite"]}

def result_sign(home, away):
    if home > away: return "1"
    if home == away: return "X"
    return "2"

def get_combo(data, corrections, participant, mid_str):
    base = data["partecipanti"][participant]["pronostici"].get(mid_str, {})
    combo = base.get("combo") or {}
    key = f"{participant}__{mid_str}"
    if key in corrections:
        combo = corrections[key]
        combo["raw"] = combo.get("raw", (base.get("combo") or {}).get("raw", ""))
    return combo


# ═══════════════════════════════════════════════════════════
# MOTORE PUNTEGGI (con Super Combo)
# ═══════════════════════════════════════════════════════════
def calculate_scores(data, results, corrections):
    match_dict = get_match_dict(data)
    scores = {}
    for pname in PARTICIPANTS:
        if pname not in data["partecipanti"]: continue
        pdata = data["partecipanti"][pname]
        totale = 0.0; gironi = defaultdict(float); dettaglio = []
        sc_used = {}
        for mid_str, match in match_dict.items():
            res = results.get(mid_str)
            if not res or not res.get("completata"): continue
            grp = match["girone"]
            pred_data = pdata["pronostici"].get(mid_str, {})
            pronostico = pred_data.get("pronostico")
            combo = get_combo(data, corrections, pname, mid_str)
            hs=res["casa"]; aws=res["trasferta"]
            actual = result_sign(hs, aws); tg = hs + aws
            scorers = [s.strip().lower() for s in res.get("marcatori","").split(",") if s.strip()]
            hth=res.get("casa_1t",0); hta=res.get("trasferta_1t",0)
            aht=f"{hth}-{hta}"; aft=f"{hs}-{aws}"
            bs = hs > 0 and aws > 0
            pts = 0.0; details = []; cc = 0
            pc = (pronostico == actual) if pronostico else False
            if pc: pts += 1; details.append(("Pronostico", 1))
            dc = combo.get("doppia_chance")
            if dc and not pc:
                dok = False
                if dc=="1": dok = actual in ("1","X")
                if dc=="X": dok = actual in ("1","2")
                if dc=="2": dok = actual in ("X","2")
                if dok: pts += 0.5; details.append(("Doppia Chance", 0.5)); cc += 1
            if combo.get("over") and tg >= 4: pts += 1; details.append(("Over", 1)); cc += 1
            if combo.get("under") and tg <= 2: pts += 1; details.append(("Under", 1)); cc += 1
            if combo.get("gol") and bs: pts += 0.5; details.append(("Gol", 0.5)); cc += 1
            if combo.get("no_gol") and not bs: pts += 0.5; details.append(("No Gol", 0.5)); cc += 1
            if combo.get("risultato_parziale") and combo["risultato_parziale"] == aht: pts += 1; details.append(("Ris. Parziale", 1)); cc += 1
            if combo.get("risultato_finale") and combo["risultato_finale"] == aft: pts += 2; details.append(("Ris. Finale", 2)); cc += 1
            if combo.get("golden_goal"):
                gg = combo["golden_goal"].lower()
                if any(gg in s or s in gg for s in scorers):
                    pts += 1; details.append(("Golden Goal", 1)); cc += 1
                    u = True
                    for o in PARTICIPANTS:
                        if o == pname: continue
                        oc = get_combo(data, corrections, o, mid_str)
                        ogg = (oc.get("golden_goal") or "").lower()
                        if ogg and (ogg in gg or gg in ogg): u = False; break
                    if u: pts += 1; details.append(("Golden Goal Unico", 1))
            if combo.get("best_bet") and pc:
                u = True
                for o in PARTICIPANTS:
                    if o == pname: continue
                    op = data["partecipanti"].get(o,{}).get("pronostici",{}).get(mid_str,{}).get("pronostico")
                    if op == actual: u = False; break
                if u: pts += 3; details.append(("Best Bet", 3)); cc += 1
            if combo.get("against"):
                target = combo["against"]
                if target in data["partecipanti"]:
                    tp = data["partecipanti"][target]["pronostici"].get(mid_str,{}).get("pronostico")
                    tc = (tp == actual) if tp else False
                    if not tc: pts += 1; details.append(("Against ✓", 1)); cc += 1
                    else: pts -= 0.5; details.append(("Against ✗", -0.5))
            if cc >= 3 and not sc_used.get(grp):
                pts += 2; details.append(("Super Combo", 2)); sc_used[grp] = True
            totale += pts; gironi[grp] += pts
            if pts != 0:
                dettaglio.append({"partita":mid_str,"match":f"{match['casa']} - {match['trasferta']}","girone":grp,"punti":pts,"dettaglio":details})
        scores[pname] = {"totale":round(totale,1),"gironi":dict(gironi),"dettaglio":dettaglio}
    return scores


# ═══════════════════════════════════════════════════════════
# GRIGLIA PRONOSTICI
# ═══════════════════════════════════════════════════════════
def build_pronostici_grid(data, results):
    rows = []
    for grp in GROUPS:
        gm = sorted([m for m in data["partite"] if m["girone"]==grp], key=lambda m:m["id"])
        for match in gm:
            mid = str(match["id"])
            res = results.get(mid)
            ris_str = f"{res['casa']}-{res['trasferta']}" if res and res.get("completata") else ""
            row = {"#":match["id"],"Gir.":grp,"Partita":f"{match['casa']} - {match['trasferta']}","Ris.":ris_str}
            for pname in PARTICIPANTS:
                pred = data["partecipanti"].get(pname,{}).get("pronostici",{}).get(mid,{}).get("pronostico","")
                row[pname] = pred or ""
            rows.append(row)
    return pd.DataFrame(rows)

def style_pronostici(df, results):
    def cell_bg(val, row_idx, col):
        if col not in PARTICIPANTS or val == "": return ""
        mid = str(df.iloc[row_idx]["#"])
        res = results.get(mid)
        if res and res.get("completata"):
            actual = result_sign(res["casa"], res["trasferta"])
            if val == actual: return "background-color:#c6efce;color:#006100;font-weight:bold"
            else: return "background-color:#ffc7ce;color:#9c0006"
        if val == "1": return "background-color:#dbeafe;color:#1e40af"
        if val == "X": return "background-color:#fef9c3;color:#854d0e"
        if val == "2": return "background-color:#fce7f3;color:#9d174d"
        return ""
    styled = df.style.hide(axis="index")
    for col in PARTICIPANTS:
        styled = styled.apply(lambda s, c=col: [cell_bg(v,i,c) for i,v in enumerate(s)], subset=[col])
    styled = styled.apply(lambda s: ["font-weight:bold;background-color:#e2e8f0" if v else "" for v in s], subset=["Ris."])
    styled = styled.set_properties(**{"text-align":"center"}, subset=PARTICIPANTS+["Ris.","#","Gir."])
    styled = styled.set_properties(**{"text-align":"left"}, subset=["Partita"])
    styled = styled.set_properties(**{"font-size":"13px"})
    return styled


# ═══════════════════════════════════════════════════════════
# COMBO — Valutazione con check/cross + Super Combo
# ═══════════════════════════════════════════════════════════
def evaluate_combo(combo, pronostico, res, data, corrections, pname, mid_str):
    if not res or not res.get("completata"):
        return None, 0
    hs=res["casa"]; aws=res["trasferta"]
    actual = result_sign(hs, aws); tg = hs + aws
    scorers = [s.strip().lower() for s in res.get("marcatori","").split(",") if s.strip()]
    hth=res.get("casa_1t",0); hta=res.get("trasferta_1t",0)
    aht=f"{hth}-{hta}"; aft=f"{hs}-{aws}"
    bs = hs > 0 and aws > 0
    pc = (pronostico == actual) if pronostico else False
    items = []; combo_correct = 0
    items.append((pronostico or "?", pc))
    if not combo:
        return items, 0
    dc = combo.get("doppia_chance")
    if dc:
        if pc:
            items.append((f"D{dc}", None))
        else:
            dok = False
            if dc == "1": dok = actual in ("1","X")
            if dc == "X": dok = actual in ("1","2")
            if dc == "2": dok = actual in ("X","2")
            items.append((f"D{dc}", dok))
            if dok: combo_correct += 1
    if combo.get("best_bet"):
        if pc:
            unique = True
            for o in PARTICIPANTS:
                if o == pname: continue
                op = data["partecipanti"].get(o,{}).get("pronostici",{}).get(mid_str,{}).get("pronostico")
                if op == actual: unique = False; break
            items.append(("BB", unique))
            if unique: combo_correct += 1
        else:
            items.append(("BB", False))
    if combo.get("over"):
        ok = tg >= 4; items.append(("OV", ok))
        if ok: combo_correct += 1
    if combo.get("under"):
        ok = tg <= 2; items.append(("U", ok))
        if ok: combo_correct += 1
    if combo.get("gol"):
        ok = bs; items.append(("G", ok))
        if ok: combo_correct += 1
    if combo.get("no_gol"):
        ok = not bs; items.append(("NG", ok))
        if ok: combo_correct += 1
    if combo.get("against"):
        target = combo["against"]; short = target[:3]
        if target in data["partecipanti"]:
            tp = data["partecipanti"][target]["pronostici"].get(mid_str,{}).get("pronostico")
            tc = (tp == actual) if tp else False
            ok = not tc; items.append((f"A+{short}", ok))
            if ok: combo_correct += 1
        else:
            items.append((f"A+{short}", None))
    if combo.get("golden_goal"):
        gg = combo["golden_goal"]; gg_low = gg.lower()
        ok = any(gg_low in s or s in gg_low for s in scorers) if scorers else False
        items.append((f"⭐{gg}", ok))
        if ok: combo_correct += 1
    if combo.get("risultato_parziale"):
        rp = combo["risultato_parziale"]
        ok = rp == aht; items.append((f"P:{rp}", ok))
        if ok: combo_correct += 1
    if combo.get("risultato_finale"):
        rf = combo["risultato_finale"]
        ok = rf == aft; items.append((f"F:{rf}", ok))
        if ok: combo_correct += 1
    return items, combo_correct


def format_evaluated_cell(items):
    if items is None: return ""
    parts = []
    for sigla, ok in items:
        if ok is True: parts.append(f"✅{sigla}")
        elif ok is False: parts.append(f"❌{sigla}")
        elif ok is None: parts.append(f"➖{sigla}")
        else: parts.append(sigla)
    return " ".join(parts)


def build_combo_results_grid(data, results, corrections):
    rows = []; cell_evals = {}; row_idx = 0
    sc_used = {pname: {} for pname in PARTICIPANTS}
    for grp in GROUPS:
        gm = sorted([m for m in data["partite"] if m["girone"]==grp], key=lambda m:m["id"])
        for match in gm:
            mid = str(match["id"]); res = results.get(mid)
            if not res or not res.get("completata"): continue
            ris_str = f"{res['casa']}-{res['trasferta']}"
            row = {"#":match["id"],"Gir.":grp,"Partita":f"{match['casa']} - {match['trasferta']}","Ris.":ris_str}
            for pname in PARTICIPANTS:
                pred_data = data["partecipanti"].get(pname,{}).get("pronostici",{}).get(mid,{})
                pronostico = pred_data.get("pronostico")
                combo = get_combo(data, corrections, pname, mid)
                items, combo_correct = evaluate_combo(combo, pronostico, res, data, corrections, pname, mid)
                if items is None:
                    actual_sign = result_sign(res["casa"], res["trasferta"])
                    pred_ok = (pronostico == actual_sign) if pronostico else False
                    items = [(pronostico or "?", pred_ok)]
                if combo_correct >= 3 and not sc_used[pname].get(grp):
                    items.append(("SC", True))
                    sc_used[pname][grp] = True
                cell_evals[(row_idx, pname)] = items
                row[pname] = format_evaluated_cell(items)
            rows.append(row); row_idx += 1
    return pd.DataFrame(rows), cell_evals


def style_combo_results(df, cell_evals):
    def get_bg(row_idx, col):
        if col not in PARTICIPANTS: return ""
        items = cell_evals.get((row_idx, col))
        if items is None: return ""
        correct = sum(1 for _,ok in items if ok is True)
        wrong = sum(1 for _,ok in items if ok is False)
        total = correct + wrong
        if total == 0: return ""
        if wrong == 0: return "background-color:#c6efce;color:#006100"
        if correct == 0: return "background-color:#ffc7ce;color:#9c0006"
        return "background-color:#fff3cd;color:#856404"
    styled = df.style.hide(axis="index")
    for col in PARTICIPANTS:
        styled = styled.apply(lambda s, c=col: [get_bg(i,c) for i in range(len(s))], subset=[col])
    styled = styled.apply(lambda s: ["font-weight:bold;background-color:#e2e8f0" if v else "" for v in s], subset=["Ris."])
    styled = styled.set_properties(**{"text-align":"center"}, subset=["#","Gir.","Ris."])
    styled = styled.set_properties(**{"text-align":"left"}, subset=["Partita"]+PARTICIPANTS)
    styled = styled.set_properties(**{"font-size":"12px"}, subset=PARTICIPANTS)
    styled = styled.set_properties(**{"font-size":"13px"}, subset=["#","Gir.","Partita","Ris."])
    return styled


def format_combo_cell(combo):
    if not combo: return ""
    parts = []
    if combo.get("doppia_chance"): parts.append(f"D{combo['doppia_chance']}")
    if combo.get("best_bet"): parts.append("BB")
    if combo.get("over"): parts.append("OV")
    if combo.get("under"): parts.append("U")
    if combo.get("gol"): parts.append("G")
    if combo.get("no_gol"): parts.append("NG")
    if combo.get("against"): parts.append(f"A+{combo['against'][:3]}")
    if combo.get("golden_goal"): parts.append(f"⭐{combo['golden_goal']}")
    if combo.get("risultato_parziale"): parts.append(f"P:{combo['risultato_parziale']}")
    if combo.get("risultato_finale"): parts.append(f"F:{combo['risultato_finale']}")
    return " ".join(parts)

def build_combo_grid(data, corrections):
    rows = []
    for grp in GROUPS:
        gm = sorted([m for m in data["partite"] if m["girone"]==grp], key=lambda m:m["id"])
        for match in gm:
            mid = str(match["id"])
            row = {"#":match["id"],"Gir.":grp,"Partita":f"{match['casa']} - {match['trasferta']}"}
            has_any = False
            for pname in PARTICIPANTS:
                combo = get_combo(data, corrections, pname, mid)
                cell = format_combo_cell(combo)
                row[pname] = cell
                if cell: has_any = True
            if has_any: rows.append(row)
    return pd.DataFrame(rows)


def build_speciali_grid(data):
    fields = [("Prima Eliminata","prima_eliminata"),("Arbitro Finale","arbitro_finale"),
              ("Partita + Goal","partita_piu_goal"),("Capocannoniere","capocannoniere")]
    rows = []
    for label, key in fields:
        row = {"Scommessa": label}
        for pname in PARTICIPANTS:
            sp = data["partecipanti"].get(pname,{}).get("speciali",{})
            row[pname] = sp.get(key, "-") or "-"
        rows.append(row)
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════
def build_report(data, results, corrections, pname):
    match_dict = get_match_dict(data)
    pdata = data["partecipanti"].get(pname, {})
    option_labels = ["1/X/2","DC","BB","Over","Under","Gol","No Gol","Against","Golden Goal","Ris.Parz.","Ris.Fin.","SC"]
    counts = {l: {"Pron.":0,"✅":0,"❌":0,"Residue":0} for l in option_labels}
    sc_used = {}
    for mid_str, match in match_dict.items():
        grp = match["girone"]
        pred_data = pdata.get("pronostici",{}).get(mid_str,{})
        pronostico = pred_data.get("pronostico")
        combo = get_combo(data, corrections, pname, mid_str)
        res = results.get(mid_str)
        completed = res and res.get("completata")
        if completed:
            hs=res["casa"];aws=res["trasferta"];actual=result_sign(hs,aws);tg=hs+aws
            scorers=[s.strip().lower() for s in res.get("marcatori","").split(",") if s.strip()]
            hth=res.get("casa_1t",0);hta=res.get("trasferta_1t",0)
            aht=f"{hth}-{hta}";aft=f"{hs}-{aws}";bs=hs>0 and aws>0
            pc=(pronostico==actual) if pronostico else False
        else:
            pc=None
        ccc=0
        if pronostico:
            counts["1/X/2"]["Pron."]+=1
            if completed:
                if pc:counts["1/X/2"]["✅"]+=1
                else:counts["1/X/2"]["❌"]+=1
            else:counts["1/X/2"]["Residue"]+=1
        dc=combo.get("doppia_chance")
        if dc:
            if completed and pc:
                pass
            else:
                counts["DC"]["Pron."]+=1
                if completed:
                    dok=False
                    if dc=="1":dok=actual in("1","X")
                    if dc=="X":dok=actual in("1","2")
                    if dc=="2":dok=actual in("X","2")
                    if dok:counts["DC"]["✅"]+=1;ccc+=1
                    else:counts["DC"]["❌"]+=1
                else:counts["DC"]["Residue"]+=1
        if combo.get("best_bet"):
            counts["BB"]["Pron."]+=1
            if completed:
                if pc:
                    u=True
                    for o in PARTICIPANTS:
                        if o==pname:continue
                        op=data["partecipanti"].get(o,{}).get("pronostici",{}).get(mid_str,{}).get("pronostico")
                        if op==actual:u=False;break
                    if u:counts["BB"]["✅"]+=1;ccc+=1
                    else:counts["BB"]["❌"]+=1
                else:counts["BB"]["❌"]+=1
            else:counts["BB"]["Residue"]+=1
        if combo.get("over"):
            counts["Over"]["Pron."]+=1
            if completed:
                if tg>=4:counts["Over"]["✅"]+=1;ccc+=1
                else:counts["Over"]["❌"]+=1
            else:counts["Over"]["Residue"]+=1
        if combo.get("under"):
            counts["Under"]["Pron."]+=1
            if completed:
                if tg<=2:counts["Under"]["✅"]+=1;ccc+=1
                else:counts["Under"]["❌"]+=1
            else:counts["Under"]["Residue"]+=1
        if combo.get("gol"):
            counts["Gol"]["Pron."]+=1
            if completed:
                if bs:counts["Gol"]["✅"]+=1;ccc+=1
                else:counts["Gol"]["❌"]+=1
            else:counts["Gol"]["Residue"]+=1
        if combo.get("no_gol"):
            counts["No Gol"]["Pron."]+=1
            if completed:
                if not bs:counts["No Gol"]["✅"]+=1;ccc+=1
                else:counts["No Gol"]["❌"]+=1
            else:counts["No Gol"]["Residue"]+=1
        if combo.get("against"):
            counts["Against"]["Pron."]+=1
            if completed:
                target=combo["against"]
                if target in data["partecipanti"]:
                    tp=data["partecipanti"][target]["pronostici"].get(mid_str,{}).get("pronostico")
                    tc=(tp==actual) if tp else False
                    if not tc:counts["Against"]["✅"]+=1;ccc+=1
                    else:counts["Against"]["❌"]+=1
                else:counts["Against"]["❌"]+=1
            else:counts["Against"]["Residue"]+=1
        if combo.get("golden_goal"):
            counts["Golden Goal"]["Pron."]+=1
            if completed:
                gg=combo["golden_goal"].lower()
                if any(gg in s or s in gg for s in scorers):counts["Golden Goal"]["✅"]+=1;ccc+=1
                else:counts["Golden Goal"]["❌"]+=1
            else:counts["Golden Goal"]["Residue"]+=1
        if combo.get("risultato_parziale"):
            counts["Ris.Parz."]["Pron."]+=1
            if completed:
                if combo["risultato_parziale"]==aht:counts["Ris.Parz."]["✅"]+=1;ccc+=1
                else:counts["Ris.Parz."]["❌"]+=1
            else:counts["Ris.Parz."]["Residue"]+=1
        if combo.get("risultato_finale"):
            counts["Ris.Fin."]["Pron."]+=1
            if completed:
                if combo["risultato_finale"]==aft:counts["Ris.Fin."]["✅"]+=1;ccc+=1
                else:counts["Ris.Fin."]["❌"]+=1
            else:counts["Ris.Fin."]["Residue"]+=1
        n_opts=sum([1 if combo.get(k) else 0 for k in ["doppia_chance","best_bet","over","under","gol","no_gol","against","golden_goal","risultato_parziale","risultato_finale"]])
        if n_opts>=3:
            counts["SC"]["Pron."]+=1
            if completed:
                if ccc>=3 and not sc_used.get(grp):counts["SC"]["✅"]+=1;sc_used[grp]=True
                else:counts["SC"]["❌"]+=1
            else:counts["SC"]["Residue"]+=1
    return option_labels, counts

def build_report_dataframe(data, results, corrections):
    option_labels = ["1/X/2","DC","BB","Over","Under","Gol","No Gol","Against","Golden Goal","Ris.Parz.","Ris.Fin.","SC"]
    status_cols = ["Pron.","✅","❌","Residue"]
    tuples = [(opt,stat) for opt in option_labels for stat in status_cols]
    columns = pd.MultiIndex.from_tuples(tuples)
    rows = []
    for pname in PARTICIPANTS:
        _,counts = build_report(data, results, corrections, pname)
        row_data = []
        for opt in option_labels:
            for stat in status_cols:
                row_data.append(counts[opt][stat])
        rows.append(row_data)
    df = pd.DataFrame(rows, index=PARTICIPANTS, columns=columns)
    df.index.name = "Partecipante"
    return df


# ═══════════════════════════════════════════════════════════
# IPOTESI OS (One Shot) — What-if analysis
# ═══════════════════════════════════════════════════════════
def build_os_analysis(data, results, corrections):
    """Analizza per ogni partita completata e partecipante l'impatto ipotetico dell'OS."""
    match_dict = get_match_dict(data)
    grid_rows = []
    grid_styles = {}  # (row_idx, pname) -> style_key
    row_idx = 0

    # Prima: calcola le SC già assegnate dalle combo normali
    sc_base = {pname: {} for pname in PARTICIPANTS}
    for grp in GROUPS:
        gm = sorted([m for m in data["partite"] if m["girone"]==grp], key=lambda m:m["id"])
        for match in gm:
            mid = str(match["id"]); res = results.get(mid)
            if not res or not res.get("completata"): continue
            for pname in PARTICIPANTS:
                pred_data = data["partecipanti"].get(pname,{}).get("pronostici",{}).get(mid,{})
                pronostico = pred_data.get("pronostico")
                combo = get_combo(data, corrections, pname, mid)
                _, combo_correct = evaluate_combo(combo, pronostico, res, data, corrections, pname, mid)
                if combo_correct >= 3 and not sc_base[pname].get(grp):
                    sc_base[pname][grp] = mid  # SC normale assegnata a questa partita

    # Summary counters
    summary = {pname: {"os_plus1": 0, "os_plus3": 0, "os_inutile": 0} for pname in PARTICIPANTS}

    for grp in GROUPS:
        gm = sorted([m for m in data["partite"] if m["girone"]==grp], key=lambda m:m["id"])
        for match in gm:
            mid = str(match["id"]); res = results.get(mid)
            if not res or not res.get("completata"): continue
            ris_str = f"{res['casa']}-{res['trasferta']}"
            row = {"#":match["id"],"Gir.":grp,"Partita":f"{match['casa']} - {match['trasferta']}","Ris.":ris_str}

            for pname in PARTICIPANTS:
                pred_data = data["partecipanti"].get(pname,{}).get("pronostici",{}).get(mid,{})
                pronostico = pred_data.get("pronostico")
                combo = get_combo(data, corrections, pname, mid)
                actual = result_sign(res["casa"], res["trasferta"])
                pc = (pronostico == actual) if pronostico else False
                _, combo_correct = evaluate_combo(combo, pronostico, res, data, corrections, pname, mid)

                if not pc:
                    # Pronostico sbagliato → OS inutile
                    row[pname] = f"{combo_correct}✅ → —"
                    grid_styles[(row_idx, pname)] = "gray"
                    summary[pname]["os_inutile"] += 1
                else:
                    # Pronostico corretto → OS vale +1, ma può triggerare SC?
                    cc_with_os = combo_correct + 1  # OS aggiunge 1 combo corretta
                    sc_already_in_girone = grp in sc_base[pname]
                    sc_already_this_match = sc_base[pname].get(grp) == mid

                    if cc_with_os >= 3 and not sc_already_in_girone:
                        # OS triggerebbe SC! 🔥
                        row[pname] = f"{combo_correct}✅ → 🔥+3"
                        grid_styles[(row_idx, pname)] = "fire"
                        summary[pname]["os_plus3"] += 1
                    elif sc_already_this_match and combo_correct >= 3:
                        # SC già assegnata su questa partita, OS dà solo +1
                        row[pname] = f"{combo_correct}✅ → +1"
                        grid_styles[(row_idx, pname)] = "green"
                        summary[pname]["os_plus1"] += 1
                    else:
                        # OS dà +1 ma niente SC
                        row[pname] = f"{combo_correct}✅ → +1"
                        grid_styles[(row_idx, pname)] = "green"
                        summary[pname]["os_plus1"] += 1

            grid_rows.append(row)
            row_idx += 1

    grid_df = pd.DataFrame(grid_rows)

    # Summary DF — max 1 OS per girone, privilegia il punteggio migliore
    # girone_best[pname][grp] = miglior impatto OS nel girone (3 o 1)
    girone_best = {pname: {} for pname in PARTICIPANTS}
    r = 0
    for grp in GROUPS:
        gm = sorted([m for m in data["partite"] if m["girone"]==grp], key=lambda m:m["id"])
        for match in gm:
            mid = str(match["id"]); res = results.get(mid)
            if not res or not res.get("completata"): continue
            for pname in PARTICIPANTS:
                style = grid_styles.get((r, pname))
                val = 3 if style == "fire" else (1 if style == "green" else 0)
                if val > girone_best[pname].get(grp, 0):
                    girone_best[pname][grp] = val
            r += 1

    sum_rows = []
    for pname in PARTICIPANTS:
        best = girone_best[pname]
        n_plus3 = sum(1 for v in best.values() if v == 3)
        n_plus1 = sum(1 for v in best.values() if v == 1)
        tot = sum(best.values())
        sum_rows.append({
            "Partecipante": pname,
            "Gironi con OS utile": n_plus1 + n_plus3,
            "Gironi +1": n_plus1,
            "🔥 Gironi +3 (OS+SC)": n_plus3,
            "Max punti extra": tot,
        })
    sum_df = pd.DataFrame(sum_rows)

    return grid_df, grid_styles, sum_df


def style_os_grid(df, grid_styles):
    def get_bg(row_idx, col):
        if col not in PARTICIPANTS: return ""
        style = grid_styles.get((row_idx, col))
        if style == "fire": return "background-color:#fed7aa;color:#9a3412;font-weight:bold"
        if style == "green": return "background-color:#d1fae5;color:#065f46"
        if style == "gray": return "background-color:#f1f5f9;color:#94a3b8"
        return ""
    styled = df.style.hide(axis="index")
    for col in PARTICIPANTS:
        styled = styled.apply(lambda s, c=col: [get_bg(i,c) for i in range(len(s))], subset=[col])
    styled = styled.apply(lambda s: ["font-weight:bold;background-color:#e2e8f0" if v else "" for v in s], subset=["Ris."])
    styled = styled.set_properties(**{"text-align":"center"}, subset=["#","Gir.","Ris."])
    styled = styled.set_properties(**{"text-align":"center","font-size":"12px"}, subset=PARTICIPANTS)
    styled = styled.set_properties(**{"text-align":"left","font-size":"13px"}, subset=["Partita"])
    return styled


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    st.markdown(
        "<h1 style='text-align:center'>🦉 Fanta Gufo Mondiale 2026</h1>"
        "<p style='text-align:center; color:gray'>Dashboard Partecipanti</p>",
        unsafe_allow_html=True
    )
    data = load_data(); results = load_results(); corrections = load_corrections()
    completed = sum(1 for r in results.values() if r.get("completata"))

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Classifica", "📋 Pronostici", "🎯 Combo", "📊 Report", "🔮 Ipotesi OS"])

    # === TAB 1: CLASSIFICA ===
    with tab1:
        st.header("🏆 Classifica Generale")
        if completed == 0:
            st.info("⏳ Il torneo non è ancora iniziato.")
        else:
            scores = calculate_scores(data, results, corrections)
            rows = []
            for i, pname in enumerate(sorted(scores.keys(), key=lambda p: scores[p]["totale"], reverse=True)):
                s = scores[pname]
                medal = ["🥇","🥈","🥉"][i] if i < 3 else f"{i+1}°"
                row = {"Pos":medal,"Partecipante":pname,"Punti":s["totale"]}
                for g in GROUPS: row[g] = round(s["gironi"].get(g,0),1)
                rows.append(row)
            cls_df = pd.DataFrame(rows)
            st.dataframe(
                cls_df.style.hide(axis="index")
                    .set_properties(**{"text-align":"center"})
                    .set_properties(**{"font-weight":"bold"}, subset=["Punti","Pos"])
                    .format({"Punti":"{:.1f}"} | {g:"{:.1f}" for g in GROUPS}),
                use_container_width=True, height=520,
            )
            st.caption(f"📊 Partite completate: {completed}/72")

    # === TAB 2: PRONOSTICI ===
    with tab2:
        st.header("📋 Griglia Pronostici")
        sel_grp = st.selectbox("Filtra per girone:", ["Tutti"]+GROUPS, key="pg")
        pro_df = build_pronostici_grid(data, results)
        if sel_grp != "Tutti":
            pro_df = pro_df[pro_df["Gir."]==sel_grp].reset_index(drop=True)
        st.dataframe(style_pronostici(pro_df, results), use_container_width=True, height=700)
        st.markdown("""
        <div style="display:flex; gap:20px; font-size:12px; margin-top:10px">
            <span style="background:#c6efce; padding:2px 8px; border-radius:4px">✅ Corretto</span>
            <span style="background:#ffc7ce; padding:2px 8px; border-radius:4px">❌ Sbagliato</span>
            <span style="background:#dbeafe; padding:2px 8px; border-radius:4px">1 Casa</span>
            <span style="background:#fef9c3; padding:2px 8px; border-radius:4px">X Pareggio</span>
            <span style="background:#fce7f3; padding:2px 8px; border-radius:4px">2 Trasferta</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        st.subheader("🎯 Scommesse Speciali")
        sp_df = build_speciali_grid(data)
        st.dataframe(
            sp_df.style.hide(axis="index")
                .set_properties(**{"text-align":"center"}, subset=PARTICIPANTS)
                .set_properties(**{"font-weight":"bold"}, subset=["Scommessa"])
                .set_properties(**{"font-size":"12px"}),
            use_container_width=True,
        )

    # === TAB 3: COMBO ===
    with tab3:
        st.header("🎯 Combo")
        combo_view = st.radio(
            "Visualizzazione:",
            ["📊 Risultati Combo (con ✅/❌)", "📋 Tutte le Combo (sigle)"],
            horizontal=True, key="combo_view"
        )
        sel_grp2 = st.selectbox("Filtra per girone:", ["Tutti"]+GROUPS, key="cg")
        if combo_view.startswith("📊"):
            if completed == 0:
                st.info("⏳ Nessuna partita completata.")
            else:
                combo_df, cell_evals = build_combo_results_grid(data, results, corrections)
                if sel_grp2 != "Tutti":
                    mask = combo_df["Gir."] == sel_grp2
                    old_indices = [i for i, m in enumerate(mask) if m]
                    combo_df = combo_df[mask].reset_index(drop=True)
                    new_evals = {}
                    for new_idx, old_idx in enumerate(old_indices):
                        for pname in PARTICIPANTS:
                            if (old_idx, pname) in cell_evals:
                                new_evals[(new_idx, pname)] = cell_evals[(old_idx, pname)]
                    cell_evals = new_evals
                if len(combo_df) == 0:
                    st.info("Nessuna partita completata per questo girone.")
                else:
                    st.dataframe(style_combo_results(combo_df, cell_evals), use_container_width=True, height=700)
                    st.markdown("""
                    <div style="font-size:12px; margin-top:10px">
                        <b>Legenda:</b>&nbsp;
                        <span style="background:#c6efce; padding:2px 8px; border-radius:4px">✅ Tutto corretto</span>&nbsp;
                        <span style="background:#ffc7ce; padding:2px 8px; border-radius:4px">❌ Tutto sbagliato</span>&nbsp;
                        <span style="background:#fff3cd; padding:2px 8px; border-radius:4px">🟡 Misto</span>&nbsp;
                        <span>➖ Non applicabile</span>&nbsp;
                        <span style="font-weight:bold">SC = Super Combo (+2pt)</span>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            combo_df = build_combo_grid(data, corrections)
            if sel_grp2 != "Tutti":
                combo_df = combo_df[combo_df["Gir."]==sel_grp2].reset_index(drop=True)
            styled = combo_df.style.hide(axis="index")
            styled = styled.set_properties(**{"text-align":"center"}, subset=["#","Gir."])
            styled = styled.set_properties(**{"text-align":"left"}, subset=["Partita"]+PARTICIPANTS)
            styled = styled.set_properties(**{"font-size":"12px"})
            st.dataframe(styled, use_container_width=True, height=700)

    # === TAB 4: REPORT ===
    with tab4:
        st.header("📊 Report Opzioni per Partecipante")
        st.caption("Per ogni tipo di pronostico: quante volte è stato usato, indovinato, sbagliato, e quante partite restano.")
        if completed == 0:
            st.info("⏳ Nessuna partita completata.")
        else:
            sel_p = st.selectbox("Partecipante:", ["Tutti"]+PARTICIPANTS, key="rp")
            if sel_p == "Tutti":
                report_df = build_report_dataframe(data, results, corrections)
                st.dataframe(
                    report_df.style
                        .set_properties(**{"text-align":"center","font-size":"13px"})
                        .map(lambda v: "color:#006100;font-weight:bold" if isinstance(v,(int,float)) and v>0 else "", subset=[(opt,"✅") for opt in report_df.columns.get_level_values(0).unique()])
                        .map(lambda v: "color:#9c0006" if isinstance(v,(int,float)) and v>0 else "", subset=[(opt,"❌") for opt in report_df.columns.get_level_values(0).unique()]),
                    use_container_width=True, height=550,
                )
            else:
                _,counts = build_report(data, results, corrections, sel_p)
                option_labels=["1/X/2","DC","BB","Over","Under","Gol","No Gol","Against","Golden Goal","Ris.Parz.","Ris.Fin.","SC"]
                status_cols=["Pron.","✅","❌","Residue"]
                tuples=[(opt,stat) for opt in option_labels for stat in status_cols]
                columns=pd.MultiIndex.from_tuples(tuples)
                row_data=[]
                for opt in option_labels:
                    for stat in status_cols:
                        row_data.append(counts[opt][stat])
                df=pd.DataFrame([row_data],index=[sel_p],columns=columns)
                df.index.name="Partecipante"
                st.dataframe(
                    df.style
                        .set_properties(**{"text-align":"center","font-size":"14px"})
                        .map(lambda v: "color:#006100;font-weight:bold" if isinstance(v,(int,float)) and v>0 else "", subset=[(opt,"✅") for opt in option_labels])
                        .map(lambda v: "color:#9c0006" if isinstance(v,(int,float)) and v>0 else "", subset=[(opt,"❌") for opt in option_labels]),
                    use_container_width=True,
                )
            st.markdown("""
            <div style="font-size:11px; margin-top:10px; color:gray">
                <b>Pron.</b> = Opzione inserita ·
                <b>✅</b> = Indovinata ·
                <b>❌</b> = Sbagliata ·
                <b>Residue</b> = Partita non giocata ·
                <b>DC</b> = non valutata se pronostico base corretto ·
                <b>SC</b> = Super Combo (≥3 combo, max 1/girone)
            </div>
            """, unsafe_allow_html=True)

    # === TAB 5: IPOTESI OS ===
    with tab5:
        st.header("🔮 Ipotesi One Shot")
        st.caption(
            "L'OS è un'opzione segreta. Se il pronostico è corretto, dà +1 punto aggiuntivo. "
            "Questa tab mostra **dove l'OS avrebbe impatto** e, soprattutto, dove potrebbe **triggerare una Super Combo** (🔥+3)."
        )
        if completed == 0:
            st.info("⏳ Nessuna partita completata.")
        else:
            # Summary
            grid_df, grid_styles, sum_df = build_os_analysis(data, results, corrections)
            st.subheader("📋 Riepilogo potenziale OS per partecipante")
            st.dataframe(
                sum_df.style.hide(axis="index")
                    .set_properties(**{"text-align":"center"})
                    .set_properties(**{"font-weight":"bold"}, subset=["Partecipante","Max punti extra"])
                    .map(lambda v: "color:#9a3412;font-weight:bold" if isinstance(v,(int,float)) and v>0 else "", subset=["🔥 Gironi +3 (OS+SC)"])
                    .map(lambda v: "color:#065f46;font-weight:bold" if isinstance(v,(int,float)) and v>0 else "", subset=["Max punti extra"]),
                use_container_width=True,
            )

            st.markdown("---")
            st.subheader("🔍 Dettaglio per partita")
            st.caption("Ogni cella mostra: `N✅ → impatto` dove N = combo corrette attuali. 🔥+3 = OS attiverebbe Super Combo!")

            sel_grp3 = st.selectbox("Filtra per girone:", ["Tutti"]+GROUPS, key="osg")
            display_df = grid_df.copy()
            display_styles = grid_styles.copy()

            if sel_grp3 != "Tutti":
                mask = display_df["Gir."] == sel_grp3
                old_indices = [i for i, m in enumerate(mask) if m]
                display_df = display_df[mask].reset_index(drop=True)
                new_styles = {}
                for new_idx, old_idx in enumerate(old_indices):
                    for pname in PARTICIPANTS:
                        if (old_idx, pname) in display_styles:
                            new_styles[(new_idx, pname)] = display_styles[(old_idx, pname)]
                display_styles = new_styles

            if len(display_df) == 0:
                st.info("Nessuna partita completata per questo girone.")
            else:
                st.dataframe(style_os_grid(display_df, display_styles), use_container_width=True, height=700)

            st.markdown("""
            <div style="font-size:12px; margin-top:10px">
                <b>Legenda:</b>&nbsp;
                <span style="background:#fed7aa; padding:2px 8px; border-radius:4px">🔥+3 OS attiva SC!</span>&nbsp;
                <span style="background:#d1fae5; padding:2px 8px; border-radius:4px">+1 OS utile</span>&nbsp;
                <span style="background:#f1f5f9; padding:2px 8px; border-radius:4px">— Pronostico sbagliato</span>
            </div>
            <div style="font-size:11px; margin-top:5px; color:gray">
                L'OS è segreto: ogni partecipante ha 1 OS per girone. Se il pronostico è corretto, +1pt.
                Se con OS si raggiungono ≥3 combo corrette E SC non è ancora stata usata nel girone → 🔥 Super Combo (+2pt extra) = +3 totali!
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        "<p style='text-align:center; color:gray; font-size:12px'>"
        "🦉 Fanta Gufo Mondiale 2026 — Dashboard</p>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
