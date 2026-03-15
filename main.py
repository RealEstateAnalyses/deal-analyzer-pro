from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pathlib
import requests
from bs4 import BeautifulSoup
import re

app = FastAPI(title="Deal Analyzer Pro API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def mostra_sito():
    html_content = pathlib.Path("index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html_content)

# --- MODELLI DATI ---
class InputDeal(BaseModel):
    prezzo_acquisto: float
    rendita_catastale: float
    mq: int
    stato_immobile: str
    stima_rivendita: float
    agenzia_percentuale: float
    mesi_operazione: int
    spese_condominio_mensili: float
    costo_lavori_custom: float

class InputURL(BaseModel):
    url: str

# --- NUOVO ENDPOINT: LO SCRAPER DEGLI ANNUNCI ---
@app.post("/api/estrai-dati")
def estrai_dati_annuncio(dati: InputURL):
    # Usiamo un "User-Agent" finto per far credere al sito che siamo un normale browser (es. Chrome) e non un robot
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Scarichiamo la pagina web dell'annuncio
        risposta = requests.get(dati.url, headers=headers, timeout=10)
        soup = BeautifulSoup(risposta.text, 'html.parser')
        
        # Estraiamo tutto il testo dalla pagina per cercare i numeri chiave
        testo_pagina = soup.get_text().replace('\n', ' ')
        
        # 1. Cerchiamo il Prezzo (Cerchiamo il simbolo € seguito da numeri)
        # Questo è un approccio semplificato ("Regular Expressions")
        prezzo_trovato = 0
        match_prezzo = re.search(r'€\s?([\d\.]+)', testo_pagina)
        if match_prezzo:
            # Togliamo i puntini (es. 150.000 diventa 150000)
            prezzo_pulito = match_prezzo.group(1).replace('.', '')
            prezzo_trovato = float(prezzo_pulito)
            
        # 2. Cerchiamo i Metri Quadri (Cerchiamo numeri seguiti da 'mq' o 'm2')
        mq_trovati = 0
        match_mq = re.search(r'(\d+)\s?(mq|m2|m²)', testo_pagina, re.IGNORECASE)
        if match_mq:
            mq_trovati = int(match_mq.group(1))
            
        return {
            "successo": True,
            "prezzo_estratto": prezzo_trovato,
            "mq_estratti": mq_trovati,
            "messaggio": "Dati estratti con successo!" if prezzo_trovato > 0 else "Pagina letta, ma format non riconosciuto."
        }
        
    except Exception as e:
        return {"successo": False, "errore": str(e)}

# --- VECCHIO ENDPOINT: IL CALCOLATORE ROI (Rimane uguale) ---
@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    valore_catastale = dati.rendita_catastale * 1.05 * 120
    imposta_registro = max(1000, valore_catastale * 0.09)
    tasse_totali = imposta_registro + 100
    
    if dati.costo_lavori_custom > 0:
        costo_lavori = dati.costo_lavori_custom
    else:
        costi_mq = {"Nuovo": 0, "Rinfrescata": 300, "Ristrutturazione": 700}
        costo_lavori = dati.mq * costi_mq.get(dati.stato_immobile, 0)
    
    costi_mantenimento = dati.mesi_operazione * dati.spese_condominio_mensili
    notaio = 1200 + (dati.prezzo_acquisto * 0.004) * 1.22
    agenzia = dati.prezzo_acquisto * (dati.agenzia_percentuale / 100) * 1.22
    
    investimento_totale = dati.prezzo_acquisto + tasse_totali + costo_lavori + notaio + agenzia + costi_mantenimento
    utile_netto = dati.stima_rivendita - investimento_totale
    roi = 0 if investimento_totale == 0 else (utile_netto / investimento_totale) * 100
    
    return {
        "investimento_totale": round(investimento_totale, 2),
        "costo_lavori": round(costo_lavori, 2),
        "tasse_e_notaio": round(tasse_totali + notaio, 2),
        "agenzia": round(agenzia, 2),
        "costi_mantenimento": round(costi_mantenimento, 2),
        "stima_rivendita": round(dati.stima_rivendita, 2),
        "utile_netto": round(utile_netto, 2),
        "roi_percentuale": round(roi, 2)
    }
