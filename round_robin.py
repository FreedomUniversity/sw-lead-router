#!/usr/bin/env python3
"""Scuderia Web — Round-robin lead Meta Preview -> advisor GHL.
Stateless + deterministico (hash) -> sicuro eseguire da piu' host (Mac + GitHub Actions) senza conflitti.
Token GHL da env GHL_TOKEN, fallback ~/.config/ghl-token."""
import os, json, urllib.request, datetime

def get_token():
    t = os.environ.get("GHL_TOKEN")
    if t: return t.strip()
    return open(os.path.expanduser("~/.config/ghl-token")).read().strip()

TOKEN = get_token()
LOC = "HzkPpPNCqGDplfXVJAer"
PIPELINE = "f3Kkvi2gu9z0JcUqsbMY"            # 03_ADV (pipeline dedicata ai lead Meta ADS, isolata dallo scraping in 03_BROAD)
STAGE = "d67efacb-0a2e-4b1e-b71b-a44b206f4aff"  # 03_ADV / In attesa
GATE_MS = 1782079191767  # solo lead creati dopo il go-live: protegge gli 8800+ contatti esistenti
ADV = [("zxoL3ZMecZpbtnvmiog5","Advisor 1"),("z0phvZrHszEiFz2ncUSi","Advisor 2"),
       ("ZLjQS4KP9lqRPRjqVKNl","Advisor 3"),("Fn5K8TNhVk7kmQn2ByZb","Advisor 4"),
       ("DBp0ZYtxaGT476FFm6H1","Advisor 5")]
SRC = ["facebook","instagram","meta","preview","lead ad","leadconnector","ig "]
H = {"Authorization":"Bearer "+TOKEN,"Version":"2021-07-28","Content-Type":"application/json",
     "Accept":"application/json","User-Agent":"Mozilla/5.0 ScuderiaRR/2.0"}

def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("https://services.leadconnectorhq.com"+path, data=data, headers=H, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def h(s):
    x = 0
    for ch in s: x = (x*31 + ord(ch)) & 0xffffffff
    return x

def main():
    try:
        res = api("POST","/contacts/search",{"locationId":LOC,"pageLimit":100})
    except Exception as e:
        print("ERR search", e); return
    n = 0
    for c in res.get("contacts", []):
        cid = c.get("id")
        if not cid or c.get("assignedTo"): continue
        da = c.get("dateAdded") or ""
        try:
            da_ms = int(datetime.datetime.fromisoformat(da.replace("Z","+00:00")).timestamp()*1000) if da else 0
        except Exception:
            da_ms = 0
        if da_ms and da_ms < GATE_MS: continue
        try:
            d = api("GET","/contacts/"+cid).get("contact", {})
        except Exception:
            continue
        if d.get("assignedTo"): continue
        src = (d.get("source") or "").lower(); tg = " ".join(d.get("tags") or []).lower()
        if not any(m in src or m in tg for m in SRC): continue
        aid, an = ADV[h(cid) % len(ADV)]
        try:
            api("PUT","/contacts/"+cid,{"assignedTo":aid})
        except Exception as e:
            print("ERR assign", cid, e); continue
        n += 1
        try: api("POST","/contacts/"+cid+"/tags",{"tags":["scuderia-web","meta-ads","preview-richiesta"]})
        except Exception: pass
        # crea la card opportunita' nel board 03_ADV (pipeline dedicata Meta ADS) -> visibile e assegnata
        try:
            nome = ((d.get("firstName","") or "")+" "+(d.get("lastName","") or "")).strip() or (d.get("companyName") or "Lead Meta")
            api("POST","/opportunities/",{"locationId":LOC,"pipelineId":PIPELINE,"pipelineStageId":STAGE,
                "name":nome,"status":"open","contactId":cid,"assignedTo":aid,"monetaryValue":997})
        except Exception as e:
            print("WARN opp", cid, e)
        note = ("\U0001F7E1 Nuovo lead Meta Ads - Scuderia Web (Preview sito)\n"
                "Nome: %s %s\nTel/WhatsApp: %s\nEmail: %s\nFonte: %s\nAssegnato a: %s (round-robin)\n"
                "Richiesta: Preview gratuita - contattare entro poche ore su WhatsApp." %
                (d.get("firstName",""), d.get("lastName",""), d.get("phone","-"), d.get("email","-"), d.get("source","-"), an))
        try: api("POST","/contacts/"+cid+"/notes",{"body":note,"userId":aid})
        except Exception: pass
        try:
            import datetime as _dt
            due = (_dt.datetime.now(_dt.timezone.utc)+_dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            api("POST","/contacts/"+cid+"/tasks",{"title":"\U0001F4DE Contatta lead preview: "+(d.get("firstName","") or "nuovo lead"),
                "body":"Lead Meta Preview Scuderia - contatta su WhatsApp entro 2h. Tel: "+(d.get("phone","-")),
                "dueDate":due,"assignedTo":aid,"completed":False})
        except Exception: pass
        print("ASSEGNATO", d.get("firstName",""), cid, "->", an)
    print("done, assegnati:", n)

if __name__ == "__main__":
    main()
