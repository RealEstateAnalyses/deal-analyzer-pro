from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pathlib
import sqlite3
from datetime import datetime

app = FastAPI(title="Deal Analyzer Pro", version="10.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    conn = sqlite3.connect('deals.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS deals
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  data_salvataggio TEXT,
                  strategia TEXT,
                  prezzo_acquisto REAL,
                  mq REAL,
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

class InputDeal(BaseModel):
    prezzo_acquisto: float = 0.0
    mq: float = 0.0 # Messo Float per evitare blocchi del server
    strategia: str = "Vendita"
    
    # NOVITA': Profilo Fiscale per Investitori
    profilo_fiscale: str = "privato_seconda"
    
    rendita_catastale: float = 0.0
    agenzia_percentuale: float = 3.0
    notaio: float = 2500.0
    spese_condominio_mensili: float = 0.0
    spese_extra: float = 0.0
    costo_lavori_totale: float = 0.0
    imprevisti_perc: float = 10.0
    
    # Vendita e Valutazione
    mesi_operazione: float = 6.0
    stima_rivendita: float = 0.0 # Ora usato come "Valore di Mercato" per tutte le strategie
    apprezzamento_annuo: float = 2.0 # % di crescita del mercato
    
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
    anni_messa_a_reddito: float = 5.0

    # Mutuo
    usa_mutuo: bool = False
    capitale_proprio: float = 30000.0
    tasso_mutuo: float = 3.5
    anni_mutuo: float = 20.0

# Modello Database corretto con Float per evitare crash
class DealDaSalvare(BaseModel):
    strategia: str
    prezzo_acquisto: float
    mq: float
    investimento_totale: float
    utile_netto: float
    roi_percentuale: float

@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    
    # 1. AGENZIA E TASSE (Logica Fiscale Istituzionale)
    agenzia = (dati.prezzo_acquisto * dati.agenzia_percentuale) / 100
    
    imposte_stato = 0
    if dati.profilo_fiscale == "privato_prima":
        base_imponibile = (dati.rendita_catastale * 115.5) if dati.rendita_catastale > 0 else dati.prezzo_acquisto
        imposte_stato = max(1000, base_imponibile * 0.02)
    elif dati.profilo_fiscale == "privato_seconda":
        base_imponibile = (dati.rendita_catastale * 126) if dati.rendita_catastale > 0 else dati.prezzo_acquisto
        imposte_stato = max(1000, base_imponibile * 0.09)
    elif dati.profilo_fiscale == "societa_asta":
        imposte_stato = max(1000, dati.prezzo_acquisto * 0.09)
    elif dati.profilo_fiscale == "societa_trading":
        imposte_stato = 600 # 3 imposte fisse: Registro, Ipotecaria, Catastale
        
    tasse_e_notaio = imposte_stato + dati.notaio

    # 2. LAVORI E COSTO TOTALE
    fondo_imprevisti = (dati.costo_lavori_totale * dati.imprevisti_perc) / 100
    costo_lavori = dati.costo_lavori_totale + fondo_imprevisti + dati.spese_extra

    costo_totale_progetto = dati.prezzo_acquisto + tasse_e_notaio + agenzia + costo_lavori
    capitale_investito_reale = costo_totale_progetto

    # 3. MUTUO E LEVA (A prova di Tasso Zero)
    importo_mutuo = 0
    rata_mensile_mutuo = 0
    debito_residuo = 0

    if dati.usa_mutuo and dati.capitale_proprio < costo_totale_progetto:
        importo_mutuo = costo_totale_progetto - dati.capitale_proprio
        capitale_investito_reale = dati.capitale_proprio
        
        if dati.tasso_mutuo > 0 and dati.anni_mutuo > 0:
            r = (dati.tasso_mutuo / 100) / 12
            n = dati.anni_mutuo * 12
            rata_mensile_mutuo = importo_mutuo * (r * (1 + r)**n) / ((1 + r)**n - 1)
        elif dati.tasso_mutuo == 0 and dati.anni_mutuo > 0:
            rata_mensile_mutuo = importo_mutuo / (dati.anni_mutuo * 12)

    # VALORE DI MERCATO INIZIALE (Per i grafici e vendite)
    valore_mercato_iniziale = dati.stima_rivendita if dati.stima_rivendita > 0 else costo_totale_progetto

    # OUTPUT BASE
    risultato = {
        "strategia": dati.strategia,
        "tasse_e_notaio": round(tasse_e_notaio, 2),
        "agenzia": round(agenzia, 2),
        "costo_lavori": round(costo_lavori, 2),
        "costo_totale_progetto": round(costo_totale_progetto, 2),
        "usa_mutuo": dati.usa_mutuo,
        "importo_mutuo": round(importo_mutuo, 2),
        "rata_mensile_mutuo": round(rata_mensile_mutuo, 2),
        "capitale_proprio": round(capitale_investito_reale, 2),
        "valore_mercato_iniziale": round(valore_mercato_iniziale, 2),
        "apprezzamento_annuo": dati.apprezzamento_annuo
    }

    # ==========================================
    # STRATEGIA 1: VENDITA RAPIDA (Flipping)
    # ==========================================
    if dati.strategia == "Vendita":
        costi_mantenimento = dati.spese_condominio_mensili * dati.mesi_operazione
        if dati.usa_mutuo and dati.tasso_mutuo > 0:
            interessi_cantiere = importo_mutuo * (dati.tasso_mutuo / 100) * (dati.mesi_operazione / 12)
            costi_mantenimento += interessi_cantiere

        utile_netto = valore_mercato_iniziale - (costo_totale_progetto + costi_mantenimento)
        
        risultato.update({
            "costi_mantenimento": round(costi_mantenimento, 2),
            "metrica_lorda": round(valore_mercato_iniziale, 2),
            "utile_netto": round(utile_netto, 2),
            "roi_percentuale": round((utile_netto / capitale_investito_reale) * 100, 2) if capitale_investito_reale > 0 else 0
        })

    # ==========================================
    # STRATEGIA 2 & 3: AFFITTO o MISTA (Affitto + Vendita)
    # ==========================================
    else:
        metrica_lorda = dati.canone_mensile * 12 
        
        costi_mantenimento_annui = (
            (dati.spese_condominio_mensili * 12) + (dati.costo_wifi * 12) + (dati.costo_luce * 12) + 
            (dati.costo_gas * 12) + (dati.costo_acqua_tari * 12) + 
            ((metrica_lorda * dati.gestione_property_perc) / 100) + 
            dati.imu_annua + dati.assicurazione_annua
        )

        if dati.usa_mutuo:
            costi_mantenimento_annui += (rata_mensile_mutuo * 12)

        tasse_affitto = (metrica_lorda * dati.cedolare_secca_perc) / 100
        cashflow_annuo_netto = metrica_lorda - costi_mantenimento_annui - tasse_affitto

        if dati.strategia == "Affitto":
            risultato.update({
                "costi_mantenimento": round(costi_mantenimento_annui, 2),
                "metrica_lorda": round(metrica_lorda, 2),
                "utile_netto": round(cashflow_annuo_netto, 2),
                "roi_percentuale": round((cashflow_annuo_netto / capitale_investito_reale) * 100, 2) if capitale_investito_reale > 0 else 0
            })

        elif dati.strategia == "Mista":
            totale_cashflow_accumulato = cashflow_annuo_netto * dati.anni_messa_a_reddito
            
            # Valore Immobile rivalutato negli anni
            valore_futuro_immobile = valore_mercato_iniziale * ((1 + (dati.apprezzamento_annuo / 100)) ** dati.anni_messa_a_reddito)
            
            # Debito Residuo
            debito_residuo = 0
            if dati.usa_mutuo and dati.anni_mutuo > 0:
                mesi_totali = dati.anni_mutuo * 12
                mesi_pagati = dati.anni_messa_a_reddito * 12
                
                if mesi_pagati < mesi_totali:
                    if dati.tasso_mutuo > 0:
                        r = (dati.tasso_mutuo / 100) / 12
                        debito_residuo = importo_mutuo * (((1 + r)**mesi_totali - (1 + r)**mesi_pagati) / ((1 + r)**mesi_totali - 1))
                    else:
                        debito_residuo = importo_mutuo - (rata_mensile_mutuo * mesi_pagati)
            
            incasso_netto_vendita = valore_futuro_immobile - debito_residuo
            utile_totale = totale_cashflow_accumulato + incasso_netto_vendita - capitale_investito_reale

            roi_totale = (utile_totale / capitale_investito_reale) * 100 if capitale_investito_reale > 0 else 0
            roi_annuo_medio = roi_totale / dati.anni_messa_a_reddito if dati.anni_messa_a_reddito > 0 else 0

            risultato.update({
                "costi_mantenimento": round(costi_mantenimento_annui, 2),
                "metrica_lorda": round(valore_futuro_immobile, 2),
                "utile_netto": round(utile_totale, 2),
                "cashflow_annuo": round(cashflow_annuo_netto, 2),
                "debito_residuo": round(debito_residuo, 2),
                "roi_percentuale": round(roi_totale, 2),
                "roi_annuo_medio": round(roi_annuo_medio, 2)
            })

    return risultato

@app.post("/api/salva-deal")
def salva_deal(deal: DealDaSalvare):
    try:
        conn = sqlite3.connect('deals.db')
        c = conn.cursor()
        data_odierna = datetime.now().strftime("%d/%m/%Y %H:%M")
        c.execute("INSERT INTO deals (data_salvataggio, strategia, prezzo_acquisto, mq, investimento_totale, utile_netto, roi_percentuale) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (data_odierna, deal.strategia, deal.prezzo_acquisto, deal.mq, deal.investimento_totale, deal.utile_netto, deal.roi_percentuale))
        conn.commit()
        conn.close()
        return {"successo": True, "messaggio": "Deal salvato nel Garage!"}
    except Exception as e:
        return {"successo": False, "errore": str(e)}

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
