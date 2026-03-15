from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse # NUOVO IMPORT
from pydantic import BaseModel
import pathlib # NUOVO IMPORT

# Inizializziamo l'app
app = FastAPI(title="Deal Analyzer Pro API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NUOVA ROTTA: Quando qualcuno apre il sito, FastAPI gli spedisce il tuo file index.html
@app.get("/", response_class=HTMLResponse)
def mostra_sito():
    # Legge il file HTML che hai creato e lo mostra nel browser
    html_content = pathlib.Path("index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html_content)

# Definiamo cosa l'utente ci deve mandare dall'HTML
class InputDeal(BaseModel):
    prezzo_acquisto: float
    rendita_catastale: float
    mq: int
    stato_immobile: str

# Creiamo l'"Endpoint" dei calcoli (QUESTO RIMANE UGUALE A PRIMA)
@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    
    # 1. Calcolo Tasse (Prezzo-Valore Persona Fisica)
    valore_catastale = dati.rendita_catastale * 1.05 * 120
    imposta_registro = max(1000, valore_catastale * 0.09)
    tasse_totali = imposta_registro + 100
    
    # 2. Calcolo Lavori
    costi_mq = {"Nuovo": 0, "Rinfrescata": 300, "Ristrutturazione": 700}
    costo_lavori = dati.mq * costi_mq.get(dati.stato_immobile, 0)
    
    # 3. Calcolo Spese Accessorie
    notaio = 1200 + (dati.prezzo_acquisto * 0.004) * 1.22
    agenzia = dati.prezzo_acquisto * 0.04 * 1.22
    
    # 4. Stima Rivendita Automatica
    prezzo_medio_zona_ristrutturato = 3200
    stima_rivendita = dati.mq * prezzo_medio_zona_ristrutturato
    
    # 5. La Matematica
    investimento_totale = dati.prezzo_acquisto + tasse_totali + costo_lavori + notaio + agenzia
    utile_netto = stima_rivendita - investimento_totale
    roi = (utile_netto / investimento_totale) * 100
    
    return {
        "investimento_totale": round(investimento_totale, 2),
        "costo_lavori": round(costo_lavori, 2),
        "tasse_e_notaio": round(tasse_totali + notaio, 2),
        "stima_rivendita": round(stima_rivendita, 2),
        "utile_netto": round(utile_netto, 2),
        "roi_percentuale": round(roi, 2)
    }