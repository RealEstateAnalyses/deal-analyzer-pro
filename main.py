from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pathlib

app = FastAPI(title="Deal Analyzer Pro", version="5.0")

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

# MODELLO DATI AGGIORNATO (Sprint 3)
class InputDeal(BaseModel):
    prezzo_acquisto: float
    rendita_catastale: float
    mq: int
    stato_immobile: str
    agenzia_percentuale: float
    spese_condominio_mensili: float
    mesi_operazione: int
    
    # Dati Flipping
    stima_rivendita: float
    
    # Nuovi Dati Affitto
    strategia: str = "Vendita" # "Vendita" o "Affitto"
    canone_mensile: float = 0.0
    imu_annua: float = 0.0
    cedolare_secca_perc: float = 21.0
    
    # Dati Lavori
    usa_preventivo_dettagliato: bool = False
    costo_demolizioni: float = 0.0
    costo_elettrico: float = 0.0
    costo_idrico: float = 0.0
    costo_murarie: float = 0.0
    costo_pavimenti: float = 0.0
    costo_infissi: float = 0.0
    imprevisti_perc: float = 10.0
    costo_lavori_custom: float = 0.0

@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    
    # 1. TASSE E NOTAIO ACQUISTO (Uguale per tutti)
    valore_catastale = dati.rendita_catastale * 1.05 * 120
    imposta_registro = max(1000, valore_catastale * 0.09)
    tasse_totali = imposta_registro + 100
    notaio = 1200 + (dati.prezzo_acquisto * 0.004) * 1.22
    agenzia = dati.prezzo_acquisto * (dati.agenzia_percentuale / 100) * 1.22
    
    # 2. LAVORI (Modulo Spacca-Centesimi)
    if dati.usa_preventivo_dettagliato:
        subtotale = sum([dati.costo_demolizioni, dati.costo_elettrico, dati.costo_idrico, dati.costo_murarie, dati.costo_pavimenti, dati.costo_infissi])
        fondo_imprevisti = subtotale * (dati.imprevisti_perc / 100)
        costo_lavori = subtotale + fondo_imprevisti
    elif dati.costo_lavori_custom > 0:
        costo_lavori = dati.costo_lavori_custom
        fondo_imprevisti = 0
    else:
        costi_mq = {"Nuovo": 0, "Rinfrescata": 300, "Ristrutturazione": 700}
        costo_lavori = dati.mq * costi_mq.get(dati.stato_immobile, 0)
        fondo_imprevisti = 0
    
    # IL BIVIO STRATEGICO
    if dati.strategia == "Vendita":
        costi_mantenimento = dati.mesi_operazione * dati.spese_condominio_mensili
        investimento_totale = dati.prezzo_acquisto + tasse_totali + notaio + agenzia + costo_lavori + costi_mantenimento
        
        utile_netto = dati.stima_rivendita - investimento_totale
        roi = 0 if investimento_totale == 0 else (utile_netto / investimento_totale) * 100
        
        return {
            "strategia": "Vendita", "investimento_totale": round(investimento_totale, 2), "costo_lavori": round(costo_lavori, 2),
            "fondo_imprevisti": round(fondo_imprevisti, 2), "tasse_e_notaio": round(tasse_totali + notaio, 2),
            "agenzia": round(agenzia, 2), "costi_mantenimento": round(costi_mantenimento, 2),
            "metrica_lorda": round(dati.stima_rivendita, 2), # È la rivendita
            "utile_netto": round(utile_netto, 2), "roi_percentuale": round(roi, 2)
        }
        
    else: # STRATEGIA AFFITTO
        # L'investimento totale non include i mesi di cantiere nel mantenimento (lo semplifichiamo per ora)
        investimento_totale = dati.prezzo_acquisto + tasse_totali + notaio + agenzia + costo_lavori
        
        # Calcolo Cashflow Annuo
        incasso_lordo_annuo = dati.canone_mensile * 12
        tasse_affitto_annue = incasso_lordo_annuo * (dati.cedolare_secca_perc / 100)
        spese_fisse_annue = (dati.spese_condominio_mensili * 12) + dati.imu_annua
        
        cashflow_netto_annuo = incasso_lordo_annuo - tasse_affitto_annue - spese_fisse_annue
        roi_annuo = 0 if investimento_totale == 0 else (cashflow_netto_annuo / investimento_totale) * 100
        
        return {
            "strategia": "Affitto", "investimento_totale": round(investimento_totale, 2), "costo_lavori": round(costo_lavori, 2),
            "fondo_imprevisti": round(fondo_imprevisti, 2), "tasse_e_notaio": round(tasse_totali + notaio, 2),
            "agenzia": round(agenzia, 2), "costi_mantenimento": round(spese_fisse_annue, 2), # Sono le spese fisse annue
            "metrica_lorda": round(incasso_lordo_annuo, 2), # È l'incasso lordo annuo
            "utile_netto": round(cashflow_netto_annuo, 2), "roi_percentuale": round(roi_annuo, 2)
        }
