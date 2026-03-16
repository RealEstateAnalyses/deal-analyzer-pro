from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pathlib
import sqlite3
from datetime import datetime

app = FastAPI(title="Deal Analyzer Pro", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CREAZIONE DATABASE ---
def init_db():
    conn = sqlite3.connect('deals.db')
    c = conn.cursor()
    # Crea la tabella se non esiste
    c.execute('''CREATE TABLE IF NOT EXISTS deals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  data_salvataggio TEXT,
                  strategia TEXT,
                  prezzo_acquisto REAL,
                  mq INTEGER,
                  investimento_totale REAL,
                  utile_netto REAL,
                  roi_percentuale REAL)''')
    conn.commit()
    conn.close()

init_db() # Avvia il database all'accensione del server

@app.get("/", response_class=HTMLResponse)
def mostra_sito():
    html_content = pathlib.Path("index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html_content)

# --- MODELLI DATI ---
# ... (lascia intatto l'inizio del file e l'init_db()) ...

class InputDeal(BaseModel):
    prezzo_acquisto: float
    rendita_catastale: float
    mq: int
    stato_immobile: str
    agenzia_percentuale: float
    spese_condominio_mensili: float
    mesi_operazione: int
    stima_rivendita: float
    strategia: str = "Vendita"
    canone_mensile: float = 0.0
    imu_annua: float = 0.0
    cedolare_secca_perc: float = 21.0
    usa_preventivo_dettagliato: bool = False
    costo_demolizioni: float = 0.0
    costo_elettrico: float = 0.0
    costo_idrico: float = 0.0
    costo_murarie: float = 0.0
    costo_pavimenti: float = 0.0
    costo_infissi: float = 0.0
    imprevisti_perc: float = 10.0
    costo_lavori_custom: float = 0.0
    
    # NOVITÀ SPRINT 4: Costi Occulti
    costo_allacci_utenze: float = 0.0
    tari_cantiere: float = 0.0
    riscaldamento_vuoto: float = 0.0

class DealDaSalvare(BaseModel):
    strategia: str
    prezzo_acquisto: float
    mq: int
    investimento_totale: float
    utile_netto: float
    roi_percentuale: float

@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    valore_catastale = dati.rendita_catastale * 1.05 * 120
    imposta_registro = max(1000, valore_catastale * 0.09)
    tasse_totali = imposta_registro + 100
    notaio = 1200 + (dati.prezzo_acquisto * 0.004) * 1.22
    agenzia = dati.prezzo_acquisto * (dati.agenzia_percentuale / 100) * 1.22
    
    if dati.usa_preventivo_dettagliato:
        subtotale = sum([dati.costo_demolizioni, dati.costo_elettrico, dati.costo_idrico, dati.costo_murarie, dati.costo_pavimenti, dati.costo_infissi])
        fondo_imprevisti = subtotale * (dati.imprevisti_perc / 100)
        costo_lavori = subtotale + fondo_imprevisti
    elif dati.costo_lavori_custom > 0:
        costo_lavori = dati.costo_lavori_custom
        fondo_imprevisti = 0
    else:
        costo_lavori = dati.mq * {"Nuovo": 0, "Rinfrescata": 300, "Ristrutturazione": 700}.get(dati.stato_immobile, 0)
        fondo_imprevisti = 0

    # NOVITÀ: Somma dei costi occulti inseriti dall'utente
    costi_occulti_totali = dati.costo_allacci_utenze + dati.tari_cantiere + dati.riscaldamento_vuoto
    
    if dati.strategia == "Vendita":
        costi_mantenimento = (dati.mesi_operazione * dati.spese_condominio_mensili) + costi_occulti_totali
        investimento_totale = dati.prezzo_acquisto + tasse_totali + notaio + agenzia + costo_lavori + costi_mantenimento
        utile_netto = dati.stima_rivendita - investimento_totale
        roi = 0 if investimento_totale == 0 else (utile_netto / investimento_totale) * 100
        
        return {
            "strategia": "Vendita", "investimento_totale": round(investimento_totale, 2), "costo_lavori": round(costo_lavori, 2),
            "fondo_imprevisti": round(fondo_imprevisti, 2), "tasse_e_notaio": round(tasse_totali + notaio, 2),
            "agenzia": round(agenzia, 2), "costi_mantenimento": round(costi_mantenimento, 2),
            "metrica_lorda": round(dati.stima_rivendita, 2), "utile_netto": round(utile_netto, 2), "roi_percentuale": round(roi, 2)
        }
    else:
        investimento_totale = dati.prezzo_acquisto + tasse_totali + notaio + agenzia + costo_lavori + costi_occulti_totali
        incasso_lordo_annuo = dati.canone_mensile * 12
        spese_fisse_annue = (dati.spese_condominio_mensili * 12) + dati.imu_annua
        cashflow_netto_annuo = incasso_lordo_annuo - (incasso_lordo_annuo * (dati.cedolare_secca_perc / 100)) - spese_fisse_annue
        roi_annuo = 0 if investimento_totale == 0 else (cashflow_netto_annuo / investimento_totale) * 100
        
        return {
            "strategia": "Affitto", "investimento_totale": round(investimento_totale, 2), "costo_lavori": round(costo_lavori, 2),
            "fondo_imprevisti": round(fondo_imprevisti, 2), "tasse_e_notaio": round(tasse_totali + notaio, 2),
            "agenzia": round(agenzia, 2), "costi_mantenimento": round(spese_fisse_annue, 2),
            "metrica_lorda": round(incasso_lordo_annuo, 2), "utile_netto": round(cashflow_netto_annuo, 2), "roi_percentuale": round(roi_annuo, 2)
        }

# ... (lascia intatto il resto del file con i def salva_deal e get_deals) ...

# --- NUOVO ENDPOINT: SALVA IL DEAL ---
@app.post("/api/salva-deal")
def salva_deal(deal: DealDaSalvare):
    conn = sqlite3.connect('deals.db')
    c = conn.cursor()
    data_odierna = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    c.execute("INSERT INTO deals (data_salvataggio, strategia, prezzo_acquisto, mq, investimento_totale, utile_netto, roi_percentuale) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (data_odierna, deal.strategia, deal.prezzo_acquisto, deal.mq, deal.investimento_totale, deal.utile_netto, deal.roi_percentuale))
    
    conn.commit()
    conn.close()
    return {"successo": True, "messaggio": "Deal salvato nel Garage con successo!"}
# --- NUOVO ENDPOINT: LEGGI TUTTI I DEAL ---
@app.get("/api/get-deals")
def get_deals():
    conn = sqlite3.connect('deals.db')
    conn.row_factory = sqlite3.Row # Ci permette di leggere le righe come dizionari
    c = conn.cursor()
    c.execute("SELECT * FROM deals ORDER BY id DESC") # Dal più recente al più vecchio
    deals = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"success": True, "deals": deals}

# --- NUOVO ENDPOINT: ELIMINA UN DEAL ---
@app.delete("/api/delete-deal/{deal_id}")
def delete_deal(deal_id: int):
    conn = sqlite3.connect('deals.db')
    c = conn.cursor()
    c.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
    conn.commit()
    conn.close()
    return {"success": True}
