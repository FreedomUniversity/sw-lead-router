# SW Lead Router
Round-robin automatico dei lead Meta "Preview sito" sui 5 advisor GHL di Scuderia Web.
Stateless, deterministico (hash), idempotente. Gira ogni 5 min via GitHub Actions (cloud H24).
Nessuna credenziale nel codice: il token GHL e' un GitHub Secret.
