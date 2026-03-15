from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pathlib

app = FastAPI(title="Deal Analyzer Pro API", version="2.0")

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

# IL NUOVO MODELLO DATI (Niente più dati finti)
class InputDeal(BaseModel):
    prezzo_acquisto: float
    rendita_catastale: float
    mq: int
    stato_immobile: str
    stima_rivendita: float           # NUOVO: L'utente inserisce la sua stima
    agenzia_percentuale: float       # NUOVO: % agenzia variabile
    mesi_operazione: int             # NUOVO: Durata cantiere + vendita
    spese_condominio_mensili: float  # NUOVO: Costo fisso mensile
    costo_lavori_custom: float       # NUOVO: Preventivo reale (opzionale)

@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    
    # 1. TASSE (Con controllo automatico della tassa minima di 1000€)
    valore_catastale = dati.rendita_catastale * 1.05 * 120
    imposta_registro = max(1000, valore_catastale * 0.09)
    tasse_totali = imposta_registro + 100
    
    # 2. LAVORI (Se l'utente inserisce un preventivo usa quello, altrimenti stima IA)
    if dati.costo_lavori_custom > 0:
        costo_lavori = dati.costo_lavori_custom
    else:
        costi_mq = {"Nuovo": 0, "Rinfrescata": 300, "Ristrutturazione": 700}
        costo_lavori = dati.mq * costi_mq.get(dati.stato_immobile, 0)
    
    # 3. HOLDING COSTS (I costi nascosti che fanno fallire i principianti)
    costi_mantenimento = dati.mesi_operazione * dati.spese_condominio_mensili
    
    # 4. SPESE ACCESSORIE (Con IVA di legge)
    notaio = 1200 + (dati.prezzo_acquisto * 0.004) * 1.22
    agenzia = dati.prezzo_acquisto * (dati.agenzia_percentuale / 100) * 1.22
    
    # 5. BUSINESS PLAN (Matematica spietata)
    investimento_totale = dati.prezzo_acquisto + tasse_totali + costo_lavori + notaio + agenzia + costi_mantenimento
    utile_netto = dati.stima_rivendita - investimento_totale
    roi = (utile_netto / investimento_totale) * 100
    
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
