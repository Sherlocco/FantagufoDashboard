# -*- coding: utf-8 -*-
"""
🦉 Fanta Gufo Mondiale 2026 — Dashboard Utenti
"""
import streamlit as st
import json
import os
import pandas as pd
from collections import defaultdict

st.set_page_config(page_title="🦉 Fanta Gufo 2026 — Dashboard", page_icon="🦉", layout="wide")

DATA_FILE = "fanta_gufo_data.json"
RESULTS_FILE = "results.json"
PARTICIPANTS = ["Andrea","Fabio","Gabriele","Giampaolo","Lorenzo","Manuel","Marco","Nino","Pasquale","Roberto","Simone","Umberto","Walter"]
GROUPS = ["A","B","C","D","E","F","G","H","I","J","K","L"]

@st.cache_data
def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)

def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def load_corrections():
    if os.path.exists("corrections.json"):
        with open("corrections.json", "r", encoding="utf-8") as f: return json.load(f)
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
# MOTORE PUNTEGGI
# ═══════════════════════════════════════════════════════════
def calculate_scores(data, results, corrections):
    match_dict = get_match_dict(data)
    scores = {}
    for pname in PARTICIPANTS:
        if pname not in data["partecipanti"]: continue
        pdata = data["partecipanti"][pname]
        totale = 0.0; gironi = defaultdict(float); dettaglio = []; sc_used = {}
        for mid_str, match in match_dict.items():
            res = results.get(mid_str)
            if not res or not res.get("completata"): continue
            grp = match["girone"]
            pred_data = pdata["pronostici"].get(mid_str, {})
            pronostico = pred_data.get("pronostico")
            combo = get_combo(data, corrections, pname, mid_str)
            hs=res["casa"]; aws=res["trasferta"]; actual=result_sign(hs,aws); tg=hs+aws
            scorers=[s.strip().lower() for s in res.get("marcatori","").split(",") if s.strip()]
            hth=res.get("casa_1t",0); hta=res.get("trasferta_1t",0)
            aht=f"{hth}-{hta}"; aft=f"{hs}-{aws}"; bs=hs>0 and aws>0
            pts=0.0; details=[]; cc=0
            pc=(pronostico==actual) if pronostico else False
            if pc: pts+=1; details.append(("Pronostico",1))
            dc=combo.get("doppia_chance")
            if dc and not pc:
                dok=False
                if dc=="1": dok=actual in ("1","X")
                if dc=="X": dok=actual in ("1","2")
                if dc=="2": dok=actual in ("X","2")
                if dok: pts+=0.5; details.append(("Doppia Chance",0.5)); cc+=1
            if combo.get("over") and tg>=4: pts+=1; details.append(("Over",1)); cc+=1
            if combo.get("under") and tg<=2: pts+=1; details.append(("Under",1)); cc+=1
            if combo.get("gol") and bs: pts+=0.5; details.append(("Gol",0.5)); cc+=1
            if combo.get("no_gol") and not bs: pts+=0.5; details.append(("No Gol",0.5)); cc+=1
            if combo.get("risultato_parziale") and combo["risultato_parziale"]==aht: pts+=1; details.append(("Ris. Parziale",1)); cc+=1
            if combo.get("risultato_finale") and combo["risultato_finale"]==aft: pts+=2; details.append(("Ris. Finale",2)); cc+=1
            if combo.get("golden_goal"):
                gg=combo["golden_goal"].lower()
                if any(gg in s or s in gg for s in scorers):
                    pts+=1; details.append(("Golden Goal",1)); cc+=1
                    u=True
                    for o in PARTICIPANTS:
                        if o==pname: continue
                        oc=get_combo(data,corrections,o,mid_str); ogg=(oc.get("golden_goal") or "").lower()
                        if ogg and (ogg in gg or gg in ogg): u=False; break
                    if u: pts+=1; details.append(("Golden Goal Unico",1))
            if combo.get("best_bet") and pc:
                u=True
                for o in PARTICIPANTS:
                    if o==pname: continue
                    op=data["partecipanti"].get(o,{}).get("pronostici",{}).get(mid_str,{}).get("pronostico")
                    if op==actual: u=False; break
                if u: pts+=3; details.append(("Best Bet",3)); cc+=1
            if combo.get("against"):
                t=combo["against"]
                if t in data["partecipanti"]:
                    tp=data["partecipanti"][t]["pronostici"].get(mid_str,{}).get("pronostico")
                    tc=(tp==actual) if tp else False
                    if not tc: pts+=1; details.append(("Against ✓",1)); cc+=1
                    else: pts-=0.5; details.append(("Against ✗",-0.5))
            if cc>=3 and not sc_used.get(grp):
                pts+=2; details.append(("Super Combo",2)); sc_used[grp]=True
            totale+=pts; gironi[grp]+=pts
            if pts!=0: dettaglio.append({"partita":mid_str,"match":f"{match['casa']} - {match['trasferta']}","girone":grp,"punti":pts,"dettaglio":details})
        scores[pname]={"totale":round(totale,1),"gironi":dict(gironi),"dettaglio":dettaglio}
    return scores

# ═══════════════════════════════════════════════════════════
# GRIGLIA PRONOSTICI
# ═══════════════════════════════════════════════════════════
def build_pronostici_grid(data, results):
    rows = []
    for grp in GROUPS:
        for match in sorted([m for m in data["partite"] if m["girone"]==grp], key=lambda m:m["id"]):
            mid=str(match["id"]); res=results.get(mid)
            ris=f"{res['casa']}-{res['trasferta']}" if res and res.get("completata") else ""
            row={"#":match["id"],"Gir.":grp,"Partita":f"{match['casa']} - {match['trasferta']}","Ris.":ris}
            for p in PARTICIPANTS:
                row[p]=data["partecipanti"].get(p,{}).get("pronostici",{}).get(mid,{}).get("pronostico","") or ""
            rows.append(row)
    return pd.DataFrame(rows)

def style_pronostici(df, results):
    def bg(val,ri,col):
        if col not in PARTICIPANTS or val=="": return ""
        mid=str(df.iloc[ri]["#"]); res=results.get(mid)
        if res and res.get("completata"):
            a=result_sign(res["casa"],res["trasferta"])
            return "background-color:#c6efce;color:#006100;font-weight:bold" if val==a else "background-color:#ffc7ce;color:#9c0006"
        return {"1":"background-color:#dbeafe;color:#1e40af","X":"background-color:#fef9c3;color:#854d0e","2":"background-color:#fce7f3;color:#9d174d"}.get(val,"")
    s=df.style.hide(axis="index")
    for c in PARTICIPANTS: s=s.apply(lambda x,c=c:[bg(v,i,c) for i,v in enumerate(x)],subset=[c])
    s=s.apply(lambda x:["font-weight:bold;background-color:#e2e8f0" if v else "" for v in x],subset=["Ris."])
    s=s.set_properties(**{"text-align":"center"},subset=PARTICIPANTS+["Ris.","#","Gir."])
    s=s.set_properties(**{"text-align":"left"},subset=["Partita"]).set_properties(**{"font-size":"13px"})
    return s

# ═══════════════════════════════════════════════════════════
# COMBO
# ═══════════════════════════════════════════════════════════
def evaluate_combo(combo, pronostico, res, data, corrections, pname, mid_str):
    if not res or not res.get("completata"): return None, 0
    hs=res["casa"];aws=res["trasferta"];actual=result_sign(hs,aws);tg=hs+aws
    scorers=[s.strip().lower() for s in res.get("marcatori","").split(",") if s.strip()]
    hth=res.get("casa_1t",0);hta=res.get("trasferta_1t",0)
    aht=f"{hth}-{hta}";aft=f"{hs}-{aws}";bs=hs>0 and aws>0
    pc=(pronostico==actual) if pronostico else False
    items=[];ccnt=0
    items.append((pronostico or "?",pc))
    if not combo: return items,0
    dc=combo.get("doppia_chance")
    if dc:
        if pc: items.append((f"D{dc}",None))
        else:
            dok=False
            if dc=="1":dok=actual in("1","X")
            if dc=="X":dok=actual in("1","2")
            if dc=="2":dok=actual in("X","2")
            items.append((f"D{dc}",dok))
            if dok:ccnt+=1
    if combo.get("best_bet"):
        if pc:
            u=True
            for o in PARTICIPANTS:
                if o==pname:continue
                if data["partecipanti"].get(o,{}).get("pronostici",{}).get(mid_str,{}).get("pronostico")==actual:u=False;break
            items.append(("BB",u))
            if u:ccnt+=1
        else:items.append(("BB",False))
    if combo.get("over"):ok=tg>=4;items.append(("OV",ok));ccnt+=ok
    if combo.get("under"):ok=tg<=2;items.append(("U",ok));ccnt+=ok
    if combo.get("gol"):ok=bs;items.append(("G",ok));ccnt+=ok
    if combo.get("no_gol"):ok=not bs;items.append(("NG",ok));ccnt+=ok
    if combo.get("against"):
        t=combo["against"];sh=t[:3]
        if t in data["partecipanti"]:
            tp=data["partecipanti"][t]["pronostici"].get(mid_str,{}).get("pronostico")
            ok=not((tp==actual) if tp else False);items.append((f"A+{sh}",ok));ccnt+=ok
        else:items.append((f"A+{sh}",None))
    if combo.get("golden_goal"):
        gg=combo["golden_goal"];gl=gg.lower()
        ok=any(gl in s or s in gl for s in scorers) if scorers else False
        items.append((f"⭐{gg}",ok));ccnt+=ok
    if combo.get("risultato_parziale"):
        rp=combo["risultato_parziale"];ok=rp==aht;items.append((f"P:{rp}",ok));ccnt+=ok
    if combo.get("risultato_finale"):
        rf=combo["risultato_finale"];ok=rf==aft;items.append((f"F:{rf}",ok));ccnt+=ok
    return items,ccnt

def format_evaluated_cell(items):
    if items is None:return ""
    return " ".join(f"✅{s}" if o is True else f"❌{s}" if o is False else f"➖{s}" if o is None else s for s,o in items)

def build_combo_results_grid(data, results, corrections):
    rows=[];ce={};ri=0;sc_used={p:{} for p in PARTICIPANTS}
    for grp in GROUPS:
        for match in sorted([m for m in data["partite"] if m["girone"]==grp],key=lambda m:m["id"]):
            mid=str(match["id"]);res=results.get(mid)
            if not res or not res.get("completata"):continue
            row={"#":match["id"],"Gir.":grp,"Partita":f"{match['casa']} - {match['trasferta']}","Ris.":f"{res['casa']}-{res['trasferta']}"}
            for p in PARTICIPANTS:
                pd_=data["partecipanti"].get(p,{}).get("pronostici",{}).get(mid,{})
                pr=pd_.get("pronostico");co=get_combo(data,corrections,p,mid)
                items,ccnt=evaluate_combo(co,pr,res,data,corrections,p,mid)
                if items is None:
                    a=result_sign(res["casa"],res["trasferta"]);items=[(pr or "?",(pr==a) if pr else False)]
                if ccnt>=3 and not sc_used[p].get(grp):items.append(("SC",True));sc_used[p][grp]=True
                ce[(ri,p)]=items;row[p]=format_evaluated_cell(items)
            rows.append(row);ri+=1
    return pd.DataFrame(rows),ce

def style_combo_results(df, ce):
    def bg(ri,c):
        if c not in PARTICIPANTS:return ""
        items=ce.get((ri,c))
        if items is None:return ""
        ok=sum(1 for _,o in items if o is True);bad=sum(1 for _,o in items if o is False);t=ok+bad
        if t==0:return ""
        if bad==0:return "background-color:#c6efce;color:#006100"
        if ok==0:return "background-color:#ffc7ce;color:#9c0006"
        return "background-color:#fff3cd;color:#856404"
    s=df.style.hide(axis="index")
    for c in PARTICIPANTS:s=s.apply(lambda x,c=c:[bg(i,c) for i in range(len(x))],subset=[c])
    s=s.apply(lambda x:["font-weight:bold;background-color:#e2e8f0" if v else "" for v in x],subset=["Ris."])
    s=s.set_properties(**{"text-align":"center"},subset=["#","Gir.","Ris."])
    s=s.set_properties(**{"text-align":"left","font-size":"12px"},subset=PARTICIPANTS)
    s=s.set_properties(**{"text-align":"left","font-size":"13px"},subset=["Partita"])
    return s

def format_combo_cell(combo):
    if not combo:return ""
    p=[]
    if combo.get("doppia_chance"):p.append(f"D{combo['doppia_chance']}")
    if combo.get("best_bet"):p.append("BB")
    if combo.get("over"):p.append("OV")
    if combo.get("under"):p.append("U")
    if combo.get("gol"):p.append("G")
    if combo.get("no_gol"):p.append("NG")
    if combo.get("against"):p.append(f"A+{combo['against'][:3]}")
    if combo.get("golden_goal"):p.append(f"⭐{combo['golden_goal']}")
    if combo.get("risultato_parziale"):p.append(f"P:{combo['risultato_parziale']}")
    if combo.get("risultato_finale"):p.append(f"F:{combo['risultato_finale']}")
    return " ".join(p)

def build_combo_grid(data, corrections):
    rows=[]
    for grp in GROUPS:
        for match in sorted([m for m in data["partite"] if m["girone"]==grp],key=lambda m:m["id"]):
            mid=str(match["id"]);row={"#":match["id"],"Gir.":grp,"Partita":f"{match['casa']} - {match['trasferta']}"}
            any_=False
            for p in PARTICIPANTS:
                co=get_combo(data,corrections,p,mid);c=format_combo_cell(co);row[p]=c
                if c:any_=True
            if any_:rows.append(row)
    return pd.DataFrame(rows)

def build_speciali_grid(data):
    rows=[]
    for l,k in [("Prima Eliminata","prima_eliminata"),("Arbitro Finale","arbitro_finale"),("Partita + Goal","partita_piu_goal"),("Capocannoniere","capocannoniere")]:
        row={"Scommessa":l}
        for p in PARTICIPANTS:row[p]=data["partecipanti"].get(p,{}).get("speciali",{}).get(k,"-") or "-"
        rows.append(row)
    return pd.DataFrame(rows)

# ═══════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════
def build_report(data, results, corrections, pname):
    match_dict=get_match_dict(data);pdata=data["partecipanti"].get(pname,{})
    OL=["1/X/2","DC","BB","Over","Under","Gol","No Gol","Against","Golden Goal","Ris.Parz.","Ris.Fin.","SC"]
    counts={l:{"Pron.":0,"✅":0,"❌":0,"Residue":0} for l in OL};sc_used={}
    for mid_str,match in match_dict.items():
        grp=match["girone"];pd_=pdata.get("pronostici",{}).get(mid_str,{});pr=pd_.get("pronostico")
        combo=get_combo(data,corrections,pname,mid_str);res=results.get(mid_str);done=res and res.get("completata")
        if done:
            hs=res["casa"];aws=res["trasferta"];actual=result_sign(hs,aws);tg=hs+aws
            scorers=[s.strip().lower() for s in res.get("marcatori","").split(",") if s.strip()]
            hth=res.get("casa_1t",0);hta=res.get("trasferta_1t",0);aht=f"{hth}-{hta}";aft=f"{hs}-{aws}";bs_=hs>0 and aws>0
            pc=(pr==actual) if pr else False
        else:pc=None
        ccc=0
        if pr:
            counts["1/X/2"]["Pron."]+=1
            if done:
                if pc: counts["1/X/2"]["✅"]+=1
                else: counts["1/X/2"]["❌"]+=1
            else:counts["1/X/2"]["Residue"]+=1
        dc=combo.get("doppia_chance")
        if dc:
            counts["DC"]["Pron."]+=1
            if done:
                if pc:
                    pass  # non valutata: non conta come corretta né sbagliata
                else:
                    dok=False
                    if dc=="1":dok=actual in("1","X")
                    if dc=="X":dok=actual in("1","2")
                    if dc=="2":dok=actual in("X","2")
                    if dok:counts["DC"]["✅"]+=1;ccc+=1
                    else:counts["DC"]["❌"]+=1
            else:
                counts["DC"]["Residue"]+=1
        if combo.get("best_bet"):
            counts["BB"]["Pron."]+=1
            if done:
                if pc:
                    u=True
                    for o in PARTICIPANTS:
                        if o==pname:continue
                        if data["partecipanti"].get(o,{}).get("pronostici",{}).get(mid_str,{}).get("pronostico")==actual:u=False;break
                    counts["BB"]["✅" if u else "❌"]+=1;ccc+=u
                else:counts["BB"]["❌"]+=1
            else:counts["BB"]["Residue"]+=1
        for opt,key,chk in [("Over","over",lambda:tg>=4),("Under","under",lambda:tg<=2),("Gol","gol",lambda:bs_),("No Gol","no_gol",lambda:not bs_)]:
            if combo.get(key):
                counts[opt]["Pron."]+=1
                if done:ok=chk();counts[opt]["✅" if ok else "❌"]+=1;ccc+=ok
                else:counts[opt]["Residue"]+=1
        if combo.get("against"):
            counts["Against"]["Pron."]+=1
            if done:
                t=combo["against"]
                if t in data["partecipanti"]:
                    tp=data["partecipanti"][t]["pronostici"].get(mid_str,{}).get("pronostico");tc=(tp==actual) if tp else False
                    ok=not tc;counts["Against"]["✅" if ok else "❌"]+=1;ccc+=ok
                else:counts["Against"]["❌"]+=1
            else:counts["Against"]["Residue"]+=1
        if combo.get("golden_goal"):
            counts["Golden Goal"]["Pron."]+=1
            if done:
                gg=combo["golden_goal"].lower();ok=any(gg in s or s in gg for s in scorers)
                counts["Golden Goal"]["✅" if ok else "❌"]+=1;ccc+=ok
            else:counts["Golden Goal"]["Residue"]+=1
        if combo.get("risultato_parziale"):
            counts["Ris.Parz."]["Pron."]+=1
            if done:ok=combo["risultato_parziale"]==aht;counts["Ris.Parz."]["✅" if ok else "❌"]+=1;ccc+=ok
            else:counts["Ris.Parz."]["Residue"]+=1
        if combo.get("risultato_finale"):
            counts["Ris.Fin."]["Pron."]+=1
            if done:ok=combo["risultato_finale"]==aft;counts["Ris.Fin."]["✅" if ok else "❌"]+=1;ccc+=ok
            else:counts["Ris.Fin."]["Residue"]+=1
        n_opts=sum(1 for k in ["doppia_chance","best_bet","over","under","gol","no_gol","against","golden_goal","risultato_parziale","risultato_finale"] if combo.get(k))
        if n_opts>=3:
            counts["SC"]["Pron."]+=1
            if done:
                if ccc>=3 and not sc_used.get(grp):counts["SC"]["✅"]+=1;sc_used[grp]=True
                else:counts["SC"]["❌"]+=1
            else:counts["SC"]["Residue"]+=1
    return OL,counts

def build_report_dataframe(data, results, corrections):
    OL=["1/X/2","DC","BB","Over","Under","Gol","No Gol","Against","Golden Goal","Ris.Parz.","Ris.Fin.","SC"]
    SC=["Pron.","✅","❌","Residue"]
    cols=pd.MultiIndex.from_tuples([(o,s) for o in OL for s in SC])
    rows=[]
    for p in PARTICIPANTS:
        _,c=build_report(data,results,corrections,p)
        rows.append([c[o][s] for o in OL for s in SC])
    return pd.DataFrame(rows,index=PARTICIPANTS,columns=cols)

# ═══════════════════════════════════════════════════════════
# IPOTESI OS
# ═══════════════════════════════════════════════════════════
def build_os_analysis(data, results, corrections):
    match_dict=get_match_dict(data)
    grid_rows=[];grid_styles={};ri=0
    sc_base={p:{} for p in PARTICIPANTS}
    for grp in GROUPS:
        for match in sorted([m for m in data["partite"] if m["girone"]==grp],key=lambda m:m["id"]):
            mid=str(match["id"]);res=results.get(mid)
            if not res or not res.get("completata"):continue
            for p in PARTICIPANTS:
                pd_=data["partecipanti"].get(p,{}).get("pronostici",{}).get(mid,{})
                _,cc=evaluate_combo(get_combo(data,corrections,p,mid),pd_.get("pronostico"),res,data,corrections,p,mid)
                if cc>=3 and not sc_base[p].get(grp):sc_base[p][grp]=mid
    gi_best={p:{} for p in PARTICIPANTS};ri=0
    for grp in GROUPS:
        for match in sorted([m for m in data["partite"] if m["girone"]==grp],key=lambda m:m["id"]):
            mid=str(match["id"]);res=results.get(mid)
            if not res or not res.get("completata"):continue
            row={"#":match["id"],"Gir.":grp,"Partita":f"{match['casa']} - {match['trasferta']}","Ris.":f"{res['casa']}-{res['trasferta']}"}
            for p in PARTICIPANTS:
                pd_=data["partecipanti"].get(p,{}).get("pronostici",{}).get(mid,{})
                pr=pd_.get("pronostico");co=get_combo(data,corrections,p,mid)
                actual=result_sign(res["casa"],res["trasferta"]);pc=(pr==actual) if pr else False
                _,cc=evaluate_combo(co,pr,res,data,corrections,p,mid)
                if not pc:
                    row[p]=f"{cc}✅ → —";grid_styles[(ri,p)]="gray";val=0
                else:
                    ccw=cc+1;sc_in=grp in sc_base[p]
                    if ccw>=3 and not sc_in:
                        row[p]=f"{cc}✅ → 🔥+3";grid_styles[(ri,p)]="fire";val=3
                    else:
                        row[p]=f"{cc}✅ → +1";grid_styles[(ri,p)]="green";val=1
                if val>gi_best[p].get(grp,0):gi_best[p][grp]=val
            grid_rows.append(row);ri+=1
    sum_rows=[]
    for p in PARTICIPANTS:
        b=gi_best[p];n3=sum(1 for v in b.values() if v==3);n1=sum(1 for v in b.values() if v==1)
        sum_rows.append({"Partecipante":p,"Gironi con OS utile":n1+n3,"Gironi +1":n1,"🔥 Gironi +3 (OS+SC)":n3,"Max punti extra":sum(b.values())})
    return pd.DataFrame(grid_rows),grid_styles,pd.DataFrame(sum_rows)

def style_os_grid(df, gs):
    def bg(ri,c):
        if c not in PARTICIPANTS:return ""
        s=gs.get((ri,c))
        if s=="fire":return "background-color:#fed7aa;color:#9a3412;font-weight:bold"
        if s=="green":return "background-color:#d1fae5;color:#065f46"
        if s=="gray":return "background-color:#f1f5f9;color:#94a3b8"
        return ""
    s=df.style.hide(axis="index")
    for c in PARTICIPANTS:s=s.apply(lambda x,c=c:[bg(i,c) for i in range(len(x))],subset=[c])
    s=s.apply(lambda x:["font-weight:bold;background-color:#e2e8f0" if v else "" for v in x],subset=["Ris."])
    s=s.set_properties(**{"text-align":"center"},subset=["#","Gir.","Ris."]).set_properties(**{"text-align":"center","font-size":"12px"},subset=PARTICIPANTS)
    s=s.set_properties(**{"text-align":"left","font-size":"13px"},subset=["Partita"])
    return s

# ═══════════════════════════════════════════════════════════
# IPOTESI TRUMP BOMB
# ═══════════════════════════════════════════════════════════
def build_trump_analysis(data, results, corrections):
    """Analisi what-if Trump Bomb: per ogni giocatore, quanto perderebbe per girone."""
    scores = calculate_scores(data, results, corrections)

    # Grid: rows = participants, columns = gironi
    grid_rows = []
    player_gironi = {}  # pname -> {grp: pts}

    for pname in PARTICIPANTS:
        if pname not in scores:
            continue
        s = scores[pname]
        gironi_pts = {}
        row = {"Partecipante": pname}
        for g in GROUPS:
            pts = round(s["gironi"].get(g, 0), 1)
            gironi_pts[g] = pts
            row[g] = pts
        row["TOTALE"] = s["totale"]
        player_gironi[pname] = gironi_pts
        grid_rows.append(row)

    grid_df = pd.DataFrame(grid_rows)

    # Summary
    sum_rows = []
    for pname in PARTICIPANTS:
        if pname not in player_gironi:
            continue
        gp = player_gironi[pname]
        non_zero = {g: p for g, p in gp.items() if p > 0}
        if non_zero:
            worst_g = max(non_zero, key=non_zero.get)
            worst_pts = non_zero[worst_g]
            best_g = min(non_zero, key=non_zero.get)
            best_pts = non_zero[best_g]
        else:
            worst_g = "-"; worst_pts = 0; best_g = "-"; best_pts = 0

        sum_rows.append({
            "Partecipante": pname,
            "Girone peggiore": worst_g,
            "Punti girone": worst_pts,
            "Se dimezzato": f"-{worst_pts/2:.1f}",
            "Se azzerato": f"-{worst_pts:.1f}",
            "Girone migliore": best_g,
            "Punti girone ": best_pts,
            "Se dimezzato ": f"-{best_pts/2:.1f}",
            "Se azzerato ": f"-{best_pts:.1f}",
        })

    sum_df = pd.DataFrame(sum_rows)
    return grid_df, player_gironi, sum_df


def style_trump_grid(df, player_gironi):
    """Colora: rosso = girone con più punti, verde = girone con meno punti >0."""
    def bg(val, pname, col):
        if col not in GROUPS:
            return ""
        gp = player_gironi.get(pname, {})
        non_zero = {g: p for g, p in gp.items() if p > 0}
        if not non_zero or col not in non_zero:
            if val == 0:
                return "background-color:#f1f5f9;color:#94a3b8"
            return ""
        max_pts = max(non_zero.values())
        min_pts = min(non_zero.values())
        if max_pts == min_pts:
            return ""  # tutti uguali
        if val == max_pts:
            return "background-color:#ffc7ce;color:#9c0006;font-weight:bold"
        if val == min_pts:
            return "background-color:#c6efce;color:#006100"
        return ""

    styled = df.style.hide(axis="index")
    # Apply per-row styling
    for idx in range(len(df)):
        pname = df.iloc[idx]["Partecipante"]
        for g in GROUPS:
            styled = styled.map(
                lambda v, p=pname, c=g: bg(v, p, c),
                subset=pd.IndexSlice[idx, g]
            )
    styled = styled.set_properties(**{"text-align": "center"}, subset=GROUPS + ["TOTALE"])
    styled = styled.set_properties(**{"font-weight": "bold"}, subset=["Partecipante", "TOTALE"])
    styled = styled.set_properties(**{"font-size": "14px"})
    styled = styled.format({g: "{:.1f}" for g in GROUPS} | {"TOTALE": "{:.1f}"})
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
    data=load_data();results=load_results();corrections=load_corrections()
    completed=sum(1 for r in results.values() if r.get("completata"))

    tab1,tab2,tab3,tab4,tab5,tab6=st.tabs(["🏆 Classifica","📋 Pronostici","🎯 Combo","📊 Report","🔮 Ipotesi OS","💣 Trump Bomb"])

    with tab1:
        st.header("🏆 Classifica Generale")
        if completed==0:st.info("⏳ Il torneo non è ancora iniziato.")
        else:
            scores=calculate_scores(data,results,corrections);rows=[]
            for i,p in enumerate(sorted(scores.keys(),key=lambda p:scores[p]["totale"],reverse=True)):
                s=scores[p];m=["🥇","🥈","🥉"][i] if i<3 else f"{i+1}°"
                row={"Pos":m,"Partecipante":p,"Punti":s["totale"]}
                for g in GROUPS:row[g]=round(s["gironi"].get(g,0),1)
                rows.append(row)
            st.dataframe(pd.DataFrame(rows).style.hide(axis="index").set_properties(**{"text-align":"center"}).set_properties(**{"font-weight":"bold"},subset=["Punti","Pos"]).format({"Punti":"{:.1f}"}|{g:"{:.1f}" for g in GROUPS}),use_container_width=True,height=520)
            st.caption(f"📊 Partite completate: {completed}/72")

    with tab2:
        st.header("📋 Griglia Pronostici")
        sg=st.selectbox("Filtra per girone:",["Tutti"]+GROUPS,key="pg")
        pdf=build_pronostici_grid(data,results)
        if sg!="Tutti":pdf=pdf[pdf["Gir."]==sg].reset_index(drop=True)
        st.dataframe(style_pronostici(pdf,results),use_container_width=True,height=700)
        st.markdown("""<div style="display:flex;gap:20px;font-size:12px;margin-top:10px"><span style="background:#c6efce;padding:2px 8px;border-radius:4px">✅ Corretto</span><span style="background:#ffc7ce;padding:2px 8px;border-radius:4px">❌ Sbagliato</span><span style="background:#dbeafe;padding:2px 8px;border-radius:4px">1 Casa</span><span style="background:#fef9c3;padding:2px 8px;border-radius:4px">X Pareggio</span><span style="background:#fce7f3;padding:2px 8px;border-radius:4px">2 Trasferta</span></div>""",unsafe_allow_html=True)
        st.markdown("---");st.subheader("🎯 Scommesse Speciali")
        st.dataframe(build_speciali_grid(data).style.hide(axis="index").set_properties(**{"text-align":"center"},subset=PARTICIPANTS).set_properties(**{"font-weight":"bold"},subset=["Scommessa"]).set_properties(**{"font-size":"12px"}),use_container_width=True)

    with tab3:
        st.header("🎯 Combo")
        cv=st.radio("Visualizzazione:",["📊 Risultati Combo (con ✅/❌)","📋 Tutte le Combo (sigle)"],horizontal=True,key="cv")
        sg2=st.selectbox("Filtra per girone:",["Tutti"]+GROUPS,key="cg")
        if cv.startswith("📊"):
            if completed==0:st.info("⏳ Nessuna partita completata.")
            else:
                cdf,ce=build_combo_results_grid(data,results,corrections)
                if sg2!="Tutti":
                    mask=cdf["Gir."]==sg2;oi=[i for i,m in enumerate(mask) if m];cdf=cdf[mask].reset_index(drop=True)
                    ne={}
                    for ni,old in enumerate(oi):
                        for p in PARTICIPANTS:
                            if(old,p)in ce:ne[(ni,p)]=ce[(old,p)]
                    ce=ne
                if len(cdf)==0:st.info("Nessuna partita completata per questo girone.")
                else:st.dataframe(style_combo_results(cdf,ce),use_container_width=True,height=700)
        else:
            cdf=build_combo_grid(data,corrections)
            if sg2!="Tutti":cdf=cdf[cdf["Gir."]==sg2].reset_index(drop=True)
            st.dataframe(cdf.style.hide(axis="index").set_properties(**{"text-align":"center"},subset=["#","Gir."]).set_properties(**{"text-align":"left","font-size":"12px"},subset=["Partita"]+PARTICIPANTS),use_container_width=True,height=700)

    with tab4:
        st.header("📊 Report Opzioni per Partecipante")
        if completed==0:st.info("⏳ Nessuna partita completata.")
        else:
            sp=st.selectbox("Partecipante:",["Tutti"]+PARTICIPANTS,key="rp")
            OL=["1/X/2","DC","BB","Over","Under","Gol","No Gol","Against","Golden Goal","Ris.Parz.","Ris.Fin.","SC"]
            if sp=="Tutti":
                rdf=build_report_dataframe(data,results,corrections)
                st.dataframe(rdf.style.set_properties(**{"text-align":"center","font-size":"13px"}).map(lambda v:"color:#006100;font-weight:bold" if isinstance(v,(int,float)) and v>0 else "",subset=[(o,"✅") for o in OL]).map(lambda v:"color:#9c0006" if isinstance(v,(int,float)) and v>0 else "",subset=[(o,"❌") for o in OL]),use_container_width=True,height=550)
            else:
                _,c=build_report(data,results,corrections,sp);SC=["Pron.","✅","❌","Residue"]
                cols=pd.MultiIndex.from_tuples([(o,s) for o in OL for s in SC])
                df=pd.DataFrame([[c[o][s] for o in OL for s in SC]],index=[sp],columns=cols)
                st.dataframe(df.style.set_properties(**{"text-align":"center","font-size":"14px"}).map(lambda v:"color:#006100;font-weight:bold" if isinstance(v,(int,float)) and v>0 else "",subset=[(o,"✅") for o in OL]).map(lambda v:"color:#9c0006" if isinstance(v,(int,float)) and v>0 else "",subset=[(o,"❌") for o in OL]),use_container_width=True)

    with tab5:
        st.header("🔮 Ipotesi One Shot")
        st.caption("Dove l'OS avrebbe impatto e dove potrebbe triggerare una Super Combo (🔥+3).")
        if completed==0:st.info("⏳ Nessuna partita completata.")
        else:
            gdf,gs,sdf=build_os_analysis(data,results,corrections)
            st.subheader("📋 Riepilogo");st.dataframe(sdf.style.hide(axis="index").set_properties(**{"text-align":"center"}).set_properties(**{"font-weight":"bold"},subset=["Partecipante","Max punti extra"]).map(lambda v:"color:#9a3412;font-weight:bold" if isinstance(v,(int,float)) and v>0 else "",subset=["🔥 Gironi +3 (OS+SC)"]),use_container_width=True)
            st.markdown("---");st.subheader("🔍 Dettaglio")
            sg3=st.selectbox("Filtra per girone:",["Tutti"]+GROUPS,key="osg")
            dd=gdf.copy();ds=gs.copy()
            if sg3!="Tutti":
                mask=dd["Gir."]==sg3;oi=[i for i,m in enumerate(mask) if m];dd=dd[mask].reset_index(drop=True)
                ns={};
                for ni,old in enumerate(oi):
                    for p in PARTICIPANTS:
                        if(old,p)in ds:ns[(ni,p)]=ds[(old,p)]
                ds=ns
            if len(dd)==0:st.info("Nessuna partita.")
            else:st.dataframe(style_os_grid(dd,ds),use_container_width=True,height=700)
            st.markdown("""<div style="font-size:12px;margin-top:10px"><span style="background:#fed7aa;padding:2px 8px;border-radius:4px">🔥+3 OS attiva SC!</span>&nbsp;<span style="background:#d1fae5;padding:2px 8px;border-radius:4px">+1 OS utile</span>&nbsp;<span style="background:#f1f5f9;padding:2px 8px;border-radius:4px">— Prono sbagliato</span></div>""",unsafe_allow_html=True)

    with tab6:
        st.header("💣 Ipotesi Trump Bomb")
        st.caption(
            "Analisi del rischio Trump Bomb per ogni partecipante. "
            "🔴 = girone con più punti (massimo rischio), 🟢 = girone con meno punti >0 (minimo danno)."
        )
        if completed == 0:
            st.info("⏳ Nessuna partita completata.")
        else:
            grid_df, player_gironi, sum_df = build_trump_analysis(data, results, corrections)

            st.subheader("💣 Punti per girone — Mappa rischio")
            st.dataframe(
                style_trump_grid(grid_df, player_gironi),
                use_container_width=True, height=550,
            )

            st.markdown("---")
            st.subheader("📋 Riepilogo scenari peggiore / migliore")
            st.dataframe(
                sum_df.style.hide(axis="index")
                    .set_properties(**{"text-align": "center"})
                    .set_properties(**{"font-weight": "bold"}, subset=["Partecipante"])
                    .map(lambda v: "color:#9c0006;font-weight:bold" if isinstance(v, str) and v.startswith("-") and float(v) < -2 else "", subset=["Se dimezzato", "Se azzerato"])
                    .map(lambda v: "color:#006100" if isinstance(v, str) and v.startswith("-") and float(v) > -1 else "", subset=["Se dimezzato ", "Se azzerato "]),
                use_container_width=True,
            )

            st.markdown("""
            <div style="font-size:12px; margin-top:10px">
                <b>Legenda griglia:</b>&nbsp;
                <span style="background:#ffc7ce; padding:2px 8px; border-radius:4px">🔴 Girone più rischioso (max punti)</span>&nbsp;
                <span style="background:#c6efce; padding:2px 8px; border-radius:4px">🟢 Girone meno rischioso (min punti >0)</span>&nbsp;
                <span style="background:#f1f5f9; padding:2px 8px; border-radius:4px">⬜ 0 punti</span>
            </div>
            <div style="font-size:11px; margin-top:5px; color:gray">
                <b>Trump Bomb:</b> se ≥3 partecipanti ti nominano sullo stesso girone → punti dimezzati.
                Se >3 → punti azzerati. La bomba colpisce il girone dove hai più punti.
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("<p style='text-align:center;color:gray;font-size:12px'>🦉 Fanta Gufo Mondiale 2026 — Dashboard</p>",unsafe_allow_html=True)

if __name__ == "__main__":
    main()
