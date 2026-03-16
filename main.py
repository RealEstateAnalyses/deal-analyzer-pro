from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pathlib
import sqlite3
from datetime import datetime

app = FastAPI(title="Deal Analyzer Pro", version="6.0")

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


# --- MODELLI DATI (Il "Buttafuori" aggiornato con i nuovi campi) ---
class InputDeal(BaseModel):
    prezzo_acquisto: float = 0.0
    mq: int = 0
    strategia: str = "Vendita"
    rendita_catastale: float = 0.0
    agenzia_percentuale: float = 3.0
    notaio: float = 2500.0
    spese_condominio_mensili: float = 0.0
    spese_extra: float = 0.0
    costo_lavori_totale: float = 0.0
    imprevisti_perc: float = 10.0
    mesi_operazione: float = 6.0
    stima_rivendita: float = 0.0
    canone_mensile: float = 0.0
    cedolare_secca_perc: float = 21.0
    costo_wifi: float = 0.0
    gestione_property_perc: float = 0.0
    imu_annua: float = 0.0 # Paracadute nel caso servisse l'IMU

class DealDaSalvare(BaseModel):
    strategia: str
    prezzo_acquisto: float
    mq: int
    investimento_totale: float
    utile_netto: float
    roi_percentuale: float


# --- IL MOTORE MATEMATICO ---
@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    
    # 1. ACQUISTO E TASSE
    agenzia = (dati.prezzo_acquisto * dati.agenzia_percentuale) / 100
    
    # Calcolo Tasse (Stima 9% come seconda casa sulla rendita catastale)
    # Se la rendita catastale è 0, calcola le tasse sul prezzo di acquisto (come per gli immobili commerciali/aste)
    valore_catastale = (dati.rendita_catastale * 126) if dati.rendita_catastale > 0 else dati.prezzo_acquisto
    imposte_stato = valore_catastale * 0.09
    tasse_e_notaio = imposte_stato + dati.notaio

    # 2. LAVORI E IMPREVISTI
    fondo_imprevisti = (dati.costo_lavori_totale * dati.imprevisti_perc) / 100
    costo_lavori = dati.costo_lavori_totale + fondo_imprevisti + dati.spese_extra

    # 3. VARIABILI GLOBALI
    costi_mantenimento = 0
    investimento_totale = 0
    metrica_lorda = 0
    utile_netto = 0
    roi_percentuale = 0

    # ==========================================
    # STRATEGIA 1: FLIPPING (Vendita)
    # ==========================================
    if dati.strategia == "Vendita":
        # Spese di mantenimento in cantiere
        costi_mantenimento = dati.spese_condominio_mensili * dati.mesi_operazione
        
        investimento_totale = dati.prezzo_acquisto + tasse_e_notaio + agenzia + costo_lavori + costi_mantenimento
        metrica_lorda = dati.stima_rivendita
        utile_netto = metrica_lorda - investimento_totale
        
        if investimento_totale > 0:
            roi_percentuale = (utile_netto / investimento_totale) * 100

    # ==========================================
    # STRATEGIA 2: AFFITTO
    # ==========================================
    else:
        # Investimento iniziale puro
        investimento_totale = dati.prezzo_acquisto + tasse_e_notaio + agenzia + costo_lavori
        
        # Incasso Lordo Annuo
        metrica_lorda = dati.canone_mensile * 12 

        # Spese fisse annue
        costo_wifi_annuo = dati.costo_wifi * 12
        costo_condominio_annuo = dati.spese_condominio_mensili * 12
        costo_gestione_property = (metrica_lorda * dati.gestione_property_perc) / 100
        
        costi_mantenimento = costo_condominio_annuo + costo_wifi_annuo + costo_gestione_property + dati.imu_annua

        # Tasse sull'incasso
        tasse_affitto = (metrica_lorda * dati.cedolare_secca_perc) / 100
        
        # Utile Netto Annuo (Cashflow)
        utile_netto = metrica_lorda - costi_mantenimento - tasse_affitto

        if investimento_totale > 0:
            roi_percentuale = (utile_netto / investimento_totale) * 100

    # 4. RISPOSTA AL SITO
    return {
        "strategia": dati.strategia,
        "tasse_e_notaio": round(tasse_e_notaio, 2),
        "agenzia": round(agenzia, 2),
        "costo_lavori": round(costo_lavori, 2),
        "fondo_imprevisti": round(fondo_imprevisti, 2),
        "costi_mantenimento": round(costi_mantenimento, 2),
        "investimento_totale": round(investimento_totale, 2),
        "metrica_lorda": round(metrica_lorda, 2),
        "utile_netto": round(utile_netto, 2),
        "roi_percentuale": round(roi_percentuale, 2)
    }

# --- ENDPOINT: SALVA IL DEAL ---
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

# --- ENDPOINT: LEGGI TUTTI I DEAL ---
@app.get("/api/get-deals")
def get_deals():
    conn = sqlite3.connect('deals.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM deals ORDER BY id DESC")
    deals = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"success": True, "deals": deals}

# --- ENDPOINT: ELIMINA UN DEAL ---
@app.delete("/api/delete-deal/{deal_id}")
def delete_deal(deal_id: int):
    conn = sqlite3.connect('deals.db')
    c = conn.cursor()
    c.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
    conn.commit()
    conn.close()
    return {"success": True}
