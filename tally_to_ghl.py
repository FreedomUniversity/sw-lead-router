#!/usr/bin/env python3
"""Bridge Tally -> GHL: legge le submission del form Preview, crea il contatto in GHL,
assegna round-robin ai 5 advisor, aggiunge tag + nota + task. Stateless, dedup via email/telefono."""
import os, json, urllib.request, urllib.parse, datetime
GHL_TOKEN = os.environ.get("GHL_TOKEN") or open(os.path.expanduser("~/.config/ghl-token")).read().strip()
TALLY_TOKEN = os.environ.get("TALLY_TOKEN") or open(os.path.expanduser("~/.config/tally-token")).read().strip()
LOC="HzkPpPNCqGDplfXVJAer"; FORM="zxgW1M"; GATE_MS=1782083269955
ADV=[("zxoL3ZMecZpbtnvmiog5","Advisor 1"),("z0phvZrHszEiFz2ncUSi","Advisor 2"),
     ("ZLjQS4KP9lqRPRjqVKNl","Advisor 3"),("Fn5K8TNhVk7kmQn2ByZb","Advisor 4"),("DBp0ZYtxaGT476FFm6H1","Advisor 5")]
UA="Mozilla/5.0 (Macintosh) ScuderiaBridge/1.0"

def req(url, token, method="GET", body=None):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(url, data=data, method=method, headers={"Authorization":"Bearer "+token,
      "Content-Type":"application/json","Accept":"application/json","User-Agent":UA,"Version":"2021-07-28"})
    with urllib.request.urlopen(r, timeout=30) as resp: return json.loads(resp.read().decode())

def ghl(method,path,body=None): return req("https://services.leadconnectorhq.com"+path, GHL_TOKEN, method, body)
def hsh(s):
    x=0
    for ch in s: x=(x*31+ord(ch))&0xffffffff
    return x

def main():
    try:
        data=req("https://api.tally.so/forms/%s/submissions?limit=50"%FORM, TALLY_TOKEN)
    except Exception as e:
        print("ERR tally", e); return
    qmap={q.get("id"):(q.get("title") or "").lower() for q in data.get("questions",[])}
    n=0
    for sub in data.get("submissions",[]):
        sid=sub.get("id");
        created=sub.get("submittedAt") or sub.get("createdAt") or ""
        try: cms=int(datetime.datetime.fromisoformat(created.replace("Z","+00:00")).timestamp()*1000) if created else 0
        except: cms=0
        if cms and cms<GATE_MS: continue
        resp={}
        for r in sub.get("responses",[]):
            t=qmap.get(r.get("questionId"),"")
            v=r.get("answer"); v=r.get("value") if v is None else v
            if isinstance(v,list): v=", ".join(str(z) for z in v)
            resp[t]=v
        def g(*kw):
            for t,v in resp.items():
                if v and any(k in t for k in kw): return str(v)
            return ""
        name=g("nome e cognome") or g("nome"); phone=g("whatsapp","telefono","numero"); email=g("email")
        att=g("attività","attivita"); citta=g("città","citta"); tipo=g("tipo"); sito=g("sito")
        if not (email or phone): continue
        # dedup
        try:
            s=ghl("POST","/contacts/search",{"locationId":LOC,"query":email or phone,"pageLimit":5})
            if any((c.get("email","") or "").lower()==email.lower() and email for c in s.get("contacts",[])) or                any((c.get("phone","") or "").replace(" ","")==phone.replace(" ","") and phone for c in s.get("contacts",[])):
                continue
        except Exception: pass
        parts=(name or att or "Lead").split(" ",1); fn=parts[0]; ln=parts[1] if len(parts)>1 else ""
        aid,an=ADV[hsh(sid)%len(ADV)]
        payload={"locationId":LOC,"firstName":fn,"lastName":ln,"source":"Tally Preview - Meta Ads",
                 "assignedTo":aid,"tags":["scuderia-web","meta-ads","preview-richiesta"]}
        if email: payload["email"]=email
        if phone: payload["phone"]=phone
        try:
            c=ghl("POST","/contacts/",payload); cid=(c.get("contact") or {}).get("id")
        except Exception as e:
            print("skip (dup?)", sid, e); continue
        if not cid: continue
        n+=1
        note=("\U0001F7E1 Nuovo lead Meta Ads - Scuderia Web (Preview sito)\n"
              "Attivita': %s\nCitta': %s\nTipo: %s\nHa gia' un sito: %s\n"
              "Tel/WhatsApp: %s\nEmail: %s\nAssegnato a: %s (round-robin)\n"
              "Richiesta: Preview gratuita - contattare entro poche ore su WhatsApp."%(att or "-",citta or "-",tipo or "-",sito or "-",phone or "-",email or "-",an))
        try: ghl("POST","/contacts/"+cid+"/notes",{"body":note,"userId":aid})
        except Exception: pass
        try:
            due=(datetime.datetime.utcnow()+datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            ghl("POST","/contacts/"+cid+"/tasks",{"title":"\U0001F4DE Contatta lead preview: "+(att or fn),
                "body":"Lead Meta Preview - WhatsApp entro 2h. Tel: "+(phone or "-"),"dueDate":due,"assignedTo":aid,"completed":False})
        except Exception: pass
        print("CREATO+ASSEGNATO", fn, att, "->", an)
    print("done, nuovi lead:", n)

if __name__=="__main__": main()
