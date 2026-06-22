#!/usr/bin/env python3
"""Bridge Tally(Media Buyer) -> GHL. Crea contatto taggato 'media-buyer-candidato' con nota di screening.
Separato dal funnel clienti: niente pipeline vendita, niente round-robin advisor. Idempotente via tag."""
import os, json, urllib.request, datetime
GHL_TOKEN=os.environ.get("GHL_TOKEN") or open(os.path.expanduser("~/.config/ghl-token")).read().strip()
TALLY_TOKEN=os.environ.get("TALLY_TOKEN") or open(os.path.expanduser("~/.config/tally-token")).read().strip()
LOC="HzkPpPNCqGDplfXVJAer"; FORM="EkAvZA"; GATE_MS=1782107458448
UA="Mozilla/5.0 (Macintosh) ScuderiaMB/1.0"
def req(url, token, method="GET", body=None):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(url, data=data, method=method, headers={"Authorization":"Bearer "+token,
      "Content-Type":"application/json","Accept":"application/json","User-Agent":UA,"Version":"2021-07-28"})
    with urllib.request.urlopen(r, timeout=30) as resp: return json.loads(resp.read().decode())
def ghl(method,path,body=None): return req("https://services.leadconnectorhq.com"+path, GHL_TOKEN, method, body)
def main():
    try: data=req("https://api.tally.so/forms/%s/submissions?limit=50"%FORM, TALLY_TOKEN)
    except Exception as e: print("ERR tally", e); return
    qmap={q.get("id"):(q.get("title") or "").lower() for q in data.get("questions",[])}
    n=0
    for sub in data.get("submissions",[]):
        created=sub.get("submittedAt") or sub.get("createdAt") or ""
        try: cms=int(datetime.datetime.fromisoformat(created.replace("Z","+00:00")).timestamp()*1000) if created else 0
        except: cms=0
        if cms and cms<GATE_MS: continue
        resp={}
        for r in sub.get("responses",[]):
            t=qmap.get(r.get("questionId"),""); v=r.get("answer")
            if isinstance(v,list): v=", ".join(str(z) for z in v)
            resp[t]=v
        def g(*kw):
            for t,v in resp.items():
                if v and any(k in t for k in kw): return str(v)
            return ""
        name=g("nome e cognome") or g("nome"); phone=g("whatsapp","telefono","numero"); email=g("email")
        budget=g("budget"); piatt=g("piattaforme","piattaform"); roas=g("roas"); exp=g("da quanto","anni","esperienza")
        port=g("portfolio","link"); disp=g("disponibilit"); why=g("perché","perche","sceglier")
        if not (email or phone): continue
        # dedup via tag
        try:
            sr=ghl("POST","/contacts/search",{"locationId":LOC,"query":email or phone,"pageLimit":5})
            ex=None
            for c in sr.get("contacts",[]):
                if (email and (c.get("email","") or "").lower()==email.lower()) or (phone and (c.get("phone","") or "").replace(" ","")==phone.replace(" ","")):
                    ex=c; break
            if ex and "media-buyer-candidato" in [str(t).lower() for t in (ex.get("tags") or [])]:
                continue
        except Exception: ex=None
        parts=(name or "Candidato").split(" ",1); fn=parts[0]; ln=parts[1] if len(parts)>1 else ""
        if ex:
            cid=ex.get("id")
            try: ghl("POST","/contacts/"+cid+"/tags",{"tags":["scuderia-web","media-buyer-candidato"]})
            except Exception: pass
        else:
            payload={"locationId":LOC,"firstName":fn,"lastName":ln,"source":"Tally Media Buyer","tags":["scuderia-web","media-buyer-candidato"]}
            if email: payload["email"]=email
            if phone: payload["phone"]=phone
            try: cid=(ghl("POST","/contacts/",payload).get("contact") or {}).get("id")
            except Exception as e: print("err create",e); continue
            if not cid: continue
        n+=1
        note=("\U0001F3AF CANDIDATURA Media Buyer / Full Stack Marketer\n"
              "Nome: %s %s\nTel/WhatsApp: %s\nEmail: %s\n"
              "Budget gestito/mese: %s\nPiattaforme: %s\nMiglior ROAS: %s\nEsperienza: %s\n"
              "Portfolio: %s\nDisponibilita': %s\nPerche' sceglierlo: %s"%(fn,ln,phone or "-",email or "-",
               budget or "-",piatt or "-",roas or "-",exp or "-",port or "-",disp or "-",why or "-"))
        try: ghl("POST","/contacts/"+cid+"/notes",{"body":note,"userId":"zxoL3ZMecZpbtnvmiog5"})
        except Exception: pass
        print("CANDIDATO MB", fn, "| budget", budget, "| ROAS", roas)
    print("done, candidati MB:", n)
if __name__=="__main__": main()
