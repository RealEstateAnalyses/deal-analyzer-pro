from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pathlib
import requests
from bs4 import BeautifulSoup
import re

app = FastAPI(title="Deal Analyzer Pro API", version="4.0")

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

# --- IL NUOVO MODELLO DATI (Più potente) ---
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
    
    # NUOVI CAMPI: SPRINT 2 (Preventivo Dettagliato)
    usa_preventivo_dettagliato: bool = False
    costo_demolizioni: float = 0.0
    costo_elettrico: float = 0.0
    costo_idrico: float = 0.0
    costo_murarie: float = 0.0
    costo_pavimenti: float = 0.0
    costo_infissi: float = 0.0
    imprevisti_perc: float = 10.0 # Di default 10% di imprevisti

@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    
    # 1. TASSE E NOTAIO
    valore_catastale = dati.rendita_catastale * 1.05 * 120
    imposta_registro = max(1000, valore_catastale * 0.09)
    tasse_totali = imposta_registro + 100
    notaio = 1200 + (dati.prezzo_acquisto * 0.004) * 1.22
    agenzia = dati.prezzo_acquisto * (dati.agenzia_percentuale / 100) * 1.22
    
    # 2. LAVORI (La nuova logica Spacca-Centesimi)
    if dati.usa_preventivo_dettagliato:
        subtotale_cantiere = (dati.costo_demolizioni + dati.costo_elettrico + 
                             dati.costo_idrico + dati.costo_murarie + 
                             dati.costo_pavimenti + dati.costo_infissi)
        fondo_imprevisti = subtotale_cantiere * (dati.imprevisti_perc / 100)
        costo_lavori = subtotale_cantiere + fondo_imprevisti
    elif dati.costo_lavori_custom > 0:
        costo_lavori = dati.costo_lavori_custom
        fondo_imprevisti = 0
    else:
        costi_mq = {"Nuovo": 0, "Rinfrescata": 300, "Ristrutturazione": 700}
        costo_lavori = dati.mq * costi_mq.get(dati.stato_immobile, 0)
        fondo_imprevisti = 0
    
    # 3. HOLDING COSTS
    costi_mantenimento = dati.mesi_operazione * dati.spese_condominio_mensili
    
    # 4. BUSINESS PLAN E ROI
    investimento_totale = dati.prezzo_acquisto + tasse_totali + costo_lavori + notaio + agenzia + costi_mantenimento
    utile_netto = dati.stima_rivendita - investimento_totale
    roi = 0 if investimento_totale == 0 else (utile_netto / investimento_totale) * 100
    
    return {
        "investimento_totale": round(investimento_totale, 2),
        "costo_lavori": round(costo_lavori, 2),
        "fondo_imprevisti": round(fondo_imprevisti, 2), # Mandiamo indietro anche questo dato
        "tasse_e_notaio": round(tasse_totali + notaio, 2),
        "agenzia": round(agenzia, 2),
        "costi_mantenimento": round(costi_mantenimento, 2),
        "stima_rivendita": round(dati.stima_rivendita, 2),
        "utile_netto": round(utile_netto, 2),
        "roi_percentuale": round(roi, 2)
    }
