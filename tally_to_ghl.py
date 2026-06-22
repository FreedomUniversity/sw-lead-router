#!/usr/bin/env python3
"""Bridge Tally -> GHL (upsert): legge le submission Preview, crea/aggiorna il contatto in GHL,
assegna round-robin ai 5 advisor, tag + nota + task. Idempotente via tag 'preview-richiesta'."""
import os, json, urllib.request, datetime
GHL_TOKEN = os.environ.get("GHL_TOKEN") or open(os.path.expanduser("~/.config/ghl-token")).read().strip()
TALLY_TOKEN = os.environ.get("TALLY_TOKEN") or open(os.path.expanduser("~/.config/tally-token")).read().strip()
LOC="HzkPpPNCqGDplfXVJAer"; FORM="zxgW1M"; GATE_MS=1782083269955
ADV=[("zxoL3ZMecZpbtnvmiog5","Advisor 1"),("z0phvZrHszEiFz2ncUSi","Advisor 2"),
     ("ZLjQS4KP9lqRPRjqVKNl","Advisor 3"),("Fn5K8TNhVk7kmQn2ByZb","Advisor 4"),("DBp0ZYtxaGT476FFm6H1","Advisor 5")]
UA="Mozilla/5.0 (Macintosh) ScuderiaBridge/2.0"
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
    try: data=req("https://api.tally.so/forms/%s/submissions?limit=50"%FORM, TALLY_TOKEN)
    except Exception as e: print("ERR tally", e); return
    qmap={q.get("id"):(q.get("title") or "").lower() for q in data.get("questions",[])}
    n=0
    for sub in data.get("submissions",[]):
        sid=sub.get("id"); created=sub.get("submittedAt") or sub.get("createdAt") or ""
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
        att=g("attivit"); citta=g("citt"); tipo=g("tipo"); sito=g("sito")
        if not (email or phone): continue
        parts=(name or att or "Lead").split(" ",1); fn=parts[0]; ln=parts[1] if len(parts)>1 else ""
        aid,an=ADV[hsh(sid)%len(ADV)]
        existing=None
        try:
            sr=ghl("POST","/contacts/search",{"locationId":LOC,"query":email or phone,"pageLimit":5})
            for c in sr.get("contacts",[]):
                if (email and (c.get("email","") or "").lower()==email.lower()) or (phone and (c.get("phone","") or "").replace(" ","")==phone.replace(" ","")):
                    existing=c; break
        except Exception: pass
        if existing:
            tags=[str(t).lower() for t in (existing.get("tags") or [])]
            if "preview-richiesta" in tags: continue  # gia' processato -> no spam
            cid=existing.get("id")
            if existing.get("assignedTo"):
                aid=existing.get("assignedTo"); an=next((nm for i,nm in ADV if i==aid), "Advisor")
            else:
                try: ghl("PUT","/contacts/"+cid,{"assignedTo":aid})
                except Exception: pass
            try: ghl("POST","/contacts/"+cid+"/tags",{"tags":["scuderia-web","meta-ads","preview-richiesta"]})
            except Exception: pass
        else:
            payload={"locationId":LOC,"firstName":fn,"lastName":ln,"source":"Tally Preview - Meta Ads","assignedTo":aid,"tags":["scuderia-web","meta-ads","preview-richiesta"]}
            if email: payload["email"]=email
            if phone: payload["phone"]=phone
            try: cid=(ghl("POST","/contacts/",payload).get("contact") or {}).get("id")
            except Exception as e: print("err create",sid,e); continue
            if not cid: continue
        n+=1
        # campi strutturati + opportunita' in pipeline 03_BROAD
        try:
            upd={}
            if att: upd["companyName"]=att
            if citta: upd["customFields"]=[{"id":"MixbsmkeQaCcDkLKNwLC","value":citta}]
            if upd: ghl("PUT","/contacts/"+cid,upd)
        except Exception: pass
        try:
            ghl("POST","/opportunities/",{"pipelineId":"7Zudd2lv0jtbqFHrfjiL","locationId":LOC,
                "name":(att or fn)+" - Preview sito","pipelineStageId":"c99cb342-f7de-4258-b2db-490ad37921ce",
                "status":"open","contactId":cid,"assignedTo":aid,"monetaryValue":997})
        except Exception: pass
        note=("\U0001F7E1 Nuovo lead Meta Ads - Scuderia Web (Preview sito)\n"
              "Attivita': %s\nCitta': %s\nTipo: %s\nHa gia' un sito: %s\nTel/WhatsApp: %s\nEmail: %s\n"
              "Assegnato a: %s (round-robin)\nRichiesta: Preview gratuita - contattare entro poche ore su WhatsApp."%(att or "-",citta or "-",tipo or "-",sito or "-",phone or "-",email or "-",an))
        try: ghl("POST","/contacts/"+cid+"/notes",{"body":note,"userId":aid})
        except Exception: pass
        try:
            due=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            ghl("POST","/contacts/"+cid+"/tasks",{"title":"\U0001F4DE Contatta lead preview: "+(att or fn),"body":"Lead Meta Preview - WhatsApp entro 2h. Tel: "+(phone or "-"),"dueDate":due,"assignedTo":aid,"completed":False})
        except Exception: pass
        print("PROCESSATO", fn, "|", att, "->", an, "| cid", cid)
    print("done, lead processati:", n)
if __name__=="__main__": main()
