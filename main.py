from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pathlib
import sqlite3
from datetime import datetime

app = FastAPI(title="Deal Analyzer Pro", version="8.0")

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

init_db()

@app.get("/", response_class=HTMLResponse)
def mostra_sito():
    html_content = pathlib.Path("index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html_content)

# --- MODELLI DATI (Aggiunti i campi per il Mutuo) ---
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
    
    # Affitto
    canone_mensile: float = 0.0
    cedolare_secca_perc: float = 21.0
    imu_annua: float = 0.0 
    gestione_property_perc: float = 0.0
    costo_wifi: float = 0.0
    costo_luce: float = 0.0
    costo_gas: float = 0.0
    costo_acqua_tari: float = 0.0
    assicurazione_annua: float = 0.0

    # LEVA FINANZIARIA (Mutuo)
    usa_mutuo: bool = False
    capitale_proprio: float = 30000.0
    tasso_mutuo: float = 3.5
    anni_mutuo: int = 20

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
    
    # 1. ACQUISTO, TASSE E LAVORI
    agenzia = (dati.prezzo_acquisto * dati.agenzia_percentuale) / 100
    valore_catastale = (dati.rendita_catastale * 126) if dati.rendita_catastale > 0 else dati.prezzo_acquisto
    imposte_stato = valore_catastale * 0.09
    tasse_e_notaio = imposte_stato + dati.notaio

    fondo_imprevisti = (dati.costo_lavori_totale * dati.imprevisti_perc) / 100
    costo_lavori = dati.costo_lavori_totale + fondo_imprevisti + dati.spese_extra

    # 2. VARIABILI GLOBALI E MUTUO
    costi_mantenimento = 0
    costo_totale_progetto = 0
    metrica_lorda = 0
    utile_netto = 0
    roi_percentuale = 0
    
    importo_mutuo = 0
    rata_mensile_mutuo = 0
    interessi_cantiere = 0

    # ==========================================
    # STRATEGIA 1: FLIPPING (Vendita)
    # ==========================================
    if dati.strategia == "Vendita":
        costi_mantenimento = dati.spese_condominio_mensili * dati.mesi_operazione
        costo_totale_progetto = dati.prezzo_acquisto + tasse_e_notaio + agenzia + costo_lavori + costi_mantenimento
        capitale_investito_reale = costo_totale_progetto # Di default paghi tutto cash

        # Applica Mutuo se richiesto
        if dati.usa_mutuo and dati.capitale_proprio < costo_totale_progetto:
            importo_mutuo = costo_totale_progetto - dati.capitale_proprio
            capitale_investito_reale = dati.capitale_proprio
            # Nel flipping si calcolano gli interessi passivi per i mesi di cantiere
            interessi_cantiere = importo_mutuo * (dati.tasso_mutuo / 100) * (dati.mesi_operazione / 12)
            costi_mantenimento += interessi_cantiere
            costo_totale_progetto += interessi_cantiere # I costi salgono per via degli interessi

        metrica_lorda = dati.stima_rivendita
        utile_netto = metrica_lorda - costo_totale_progetto
        
        if capitale_investito_reale > 0:
            roi_percentuale = (utile_netto / capitale_investito_reale) * 100

    # ==========================================
    # STRATEGIA 2: AFFITTO
    # ==========================================
    else:
        costo_totale_progetto = dati.prezzo_acquisto + tasse_e_notaio + agenzia + costo_lavori
        capitale_investito_reale = costo_totale_progetto # Di default cash

        metrica_lorda = dati.canone_mensile * 12 # Incasso Annuo

        # Spese Fisse Annue Base
        costo_wifi_annuo = dati.costo_wifi * 12
        costo_luce_annuo = dati.costo_luce * 12
        costo_gas_annuo = dati.costo_gas * 12
        costo_acqua_annuo = dati.costo_acqua_tari * 12
        costo_condominio_annuo = dati.spese_condominio_mensili * 12
        costo_gestione_property = (metrica_lorda * dati.gestione_property_perc) / 100
        
        costi_mantenimento = (costo_condominio_annuo + costo_wifi_annuo + costo_luce_annuo + 
                              costo_gas_annuo + costo_acqua_annuo + costo_gestione_property + 
                              dati.imu_annua + dati.assicurazione_annua)

        # Applica Mutuo (Ammortamento alla francese) se richiesto
        if dati.usa_mutuo and dati.capitale_proprio < costo_totale_progetto:
            importo_mutuo = costo_totale_progetto - dati.capitale_proprio
            capitale_investito_reale = dati.capitale_proprio
            
            if dati.tasso_mutuo > 0 and dati.anni_mutuo > 0:
                r = (dati.tasso_mutuo / 100) / 12
                n = dati.anni_mutuo * 12
                rata_mensile_mutuo = importo_mutuo * (r * (1 + r)**n) / ((1 + r)**n - 1)
            elif dati.anni_mutuo > 0:
                rata_mensile_mutuo = importo_mutuo / (dati.anni_mutuo * 12)
                
            rata_annua_mutuo = rata_mensile_mutuo * 12
            costi_mantenimento += rata_annua_mutuo # La banca diventa un costo fisso

        tasse_affitto = (metrica_lorda * dati.cedolare_secca_perc) / 100
        
        # Cashflow Netto (Utile Netto in tasca)
        utile_netto = metrica_lorda - costi_mantenimento - tasse_affitto

        if capitale_investito_reale > 0:
            roi_percentuale = (utile_netto / capitale_investito_reale) * 100

    return {
        "strategia": dati.strategia,
        "tasse_e_notaio": round(tasse_e_notaio, 2),
        "agenzia": round(agenzia, 2),
        "costo_lavori": round(costo_lavori, 2),
        "costi_mantenimento": round(costi_mantenimento, 2),
        "costo_totale_progetto": round(costo_totale_progetto, 2), # Ex investimento totale
        "metrica_lorda": round(metrica_lorda, 2),
        "utile_netto": round(utile_netto, 2),
        "roi_percentuale": round(roi_percentuale, 2),
        
        # DATI MUTUO E CAPITALE
        "usa_mutuo": dati.usa_mutuo,
        "importo_mutuo": round(importo_mutuo, 2),
        "rata_mensile_mutuo": round(rata_mensile_mutuo, 2),
        "capitale_proprio": round(capitale_investito_reale, 2)
    }

# --- ENDPOINT DATABASE ---
@app.post("/api/salva-deal")
def salva_deal(deal: DealDaSalvare):
    conn = sqlite3.connect('deals.db')
    c = conn.cursor()
    data_odierna = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("INSERT INTO deals (data_salvataggio, strategia, prezzo_acquisto, mq, investimento_totale, utile_netto, roi_percentuale) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (data_odierna, deal.strategia, deal.prezzo_acquisto, deal.mq, deal.investimento_totale, deal.utile_netto, deal.roi_percentuale))
    conn.commit()
    conn.close()
    return {"successo": True, "messaggio": "Deal salvato nel Garage!"}

@app.get("/api/get-deals")
def get_deals():
    conn = sqlite3.connect('deals.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM deals ORDER BY id DESC")
    deals = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"success": True, "deals": deals}

@app.delete("/api/delete-deal/{deal_id}")
def delete_deal(deal_id: int):
    conn = sqlite3.connect('deals.db')
    c = conn.cursor()
    c.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
    conn.commit()
    conn.close()
    return {"success": True}
