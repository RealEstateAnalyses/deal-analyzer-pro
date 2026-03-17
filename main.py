from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pathlib
import sqlite3
from datetime import datetime

app = FastAPI(title="Deal Analyzer Pro - Institutional", version="11.1")

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
    mq: float = 0.0
    strategia: str = "Vendita"
    profilo_fiscale: str = "privato_seconda"
    rendita_catastale: float = 0.0
    agenzia_percentuale: float = 3.0
    notaio: float = 2500.0
    spese_condominio_mensili: float = 0.0
    spese_extra: float = 0.0
    costo_lavori_totale: float = 0.0
    imprevisti_perc: float = 10.0
    
    mesi_lavori: float = 6.0
    stima_rivendita: float = 0.0 
    apprezzamento_annuo: float = 2.0 
    
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

    usa_mutuo: bool = False
    capitale_proprio: float = 30000.0
    tasso_mutuo: float = 3.5
    anni_mutuo: float = 20.0

class DealDaSalvare(BaseModel):
    strategia: str
    prezzo_acquisto: float
    mq: float
    investimento_totale: float
    utile_netto: float
    roi_percentuale: float

@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    
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
        imposte_stato = 600 
        
    tasse_e_notaio = imposte_stato + dati.notaio
    fondo_imprevisti = (dati.costo_lavori_totale * dati.imprevisti_perc) / 100
    costo_lavori = dati.costo_lavori_totale + fondo_imprevisti + dati.spese_extra

    costo_totale_progetto = dati.prezzo_acquisto + tasse_e_notaio + agenzia + costo_lavori
    capitale_investito_reale = costo_totale_progetto

    importo_mutuo = 0
    rata_mensile_mutuo = 0

    if dati.usa_mutuo and dati.capitale_proprio < costo_totale_progetto:
        importo_mutuo = costo_totale_progetto - dati.capitale_proprio
        capitale_investito_reale = dati.capitale_proprio
        if dati.tasso_mutuo > 0 and dati.anni_mutuo > 0:
            r = (dati.tasso_mutuo / 100) / 12
            n = dati.anni_mutuo * 12
            rata_mensile_mutuo = importo_mutuo * (r * (1 + r)**n) / ((1 + r)**n - 1)
        elif dati.tasso_mutuo == 0 and dati.anni_mutuo > 0:
            rata_mensile_mutuo = importo_mutuo / (dati.anni_mutuo * 12)

    valore_mercato_iniziale = dati.stima_rivendita if dati.stima_rivendita > 0 else costo_totale_progetto
    timeline_cashflow = [-capitale_investito_reale]

    risultato = {
        "strategia": dati.strategia, "tasse_e_notaio": round(tasse_e_notaio, 2), "agenzia": round(agenzia, 2),
        "costo_lavori": round(costo_lavori, 2), "costo_totale_progetto": round(costo_totale_progetto, 2),
        "usa_mutuo": dati.usa_mutuo, "importo_mutuo": round(importo_mutuo, 2), "rata_mensile_mutuo": round(rata_mensile_mutuo, 2),
        "capitale_proprio": round(capitale_investito_reale, 2), "valore_mercato_iniziale": round(valore_mercato_iniziale, 2),
        "incasso_mensile_lordo": round(dati.canone_mensile, 2)
    }

    def calcola_tasse_vendita(prezzo_vendita):
        if dati.profilo_fiscale in ["privato_prima", "privato_seconda"]:
            plusvalenza = max(0, prezzo_vendita - costo_totale_progetto)
            return plusvalenza * 0.26
        return 0

    if dati.strategia == "Vendita":
        costi_mantenimento = dati.spese_condominio_mensili * dati.mesi_lavori
        if dati.usa_mutuo: costi_mantenimento += importo_mutuo * (dati.tasso_mutuo / 100) * (dati.mesi_lavori / 12)
        
        tasse_plusvalenza = calcola_tasse_vendita(valore_mercato_iniziale)
        utile_netto = valore_mercato_iniziale - (costo_totale_progetto + costi_mantenimento + tasse_plusvalenza)
        timeline_cashflow.append(utile_netto + capitale_investito_reale) 
        
        risultato.update({
            "costi_mantenimento": round(costi_mantenimento, 2), "metrica_lorda": round(valore_mercato_iniziale, 2),
            "tasse_plusvalenza": round(tasse_plusvalenza, 2), "utile_netto": round(utile_netto, 2),
            "roi_percentuale": round((utile_netto / capitale_investito_reale) * 100, 2) if capitale_investito_reale > 0 else 0,
            "timeline": timeline_cashflow, "cashflow_mensile_netto": 0
        })

    else:
        metrica_lorda = dati.canone_mensile * 12 
        spese_fisse_mensili = dati.spese_condominio_mensili + dati.costo_wifi + dati.costo_luce + dati.costo_gas + dati.costo_acqua_tari
        spese_fisse_annue = (spese_fisse_mensili * 12) + ((metrica_lorda * dati.gestione_property_perc) / 100) + dati.imu_annua + dati.assicurazione_annua
        if dati.usa_mutuo: spese_fisse_annue += (rata_mensile_mutuo * 12)

        tasse_affitto = (metrica_lorda * dati.cedolare_secca_perc) / 100
        cashflow_annuo_pieno = metrica_lorda - spese_fisse_annue - tasse_affitto
        cashflow_mensile_netto = cashflow_annuo_pieno / 12
        
        mesi_affitto_anno_1 = max(0, 12 - dati.mesi_lavori)
        incasso_anno_1 = dati.canone_mensile * mesi_affitto_anno_1
        cashflow_anno_1 = incasso_anno_1 - spese_fisse_annue - ((incasso_anno_1 * dati.cedolare_secca_perc)/100)
        
        if dati.strategia == "Affitto":
            timeline_cashflow.append(cashflow_anno_1)
            for _ in range(4): timeline_cashflow.append(cashflow_annuo_pieno) 
            
            risultato.update({
                "costi_mantenimento": round(spese_fisse_annue, 2), "metrica_lorda": round(metrica_lorda, 2),
                "utile_netto": round(cashflow_annuo_pieno, 2), "timeline": timeline_cashflow,
                "cashflow_mensile_netto": round(cashflow_mensile_netto, 2),
                "roi_percentuale": round((cashflow_annuo_pieno / capitale_investito_reale) * 100, 2) if capitale_investito_reale > 0 else 0
            })

        elif dati.strategia == "Mista":
            valore_futuro_immobile = valore_mercato_iniziale * ((1 + (dati.apprezzamento_annuo / 100)) ** dati.anni_messa_a_reddito)
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
            
            tasse_plusvalenza = calcola_tasse_vendita(valore_futuro_immobile) if dati.anni_messa_a_reddito <= 5 else 0
            incasso_netto_vendita = valore_futuro_immobile - debito_residuo - tasse_plusvalenza
            
            totale_cashflow_accumulato = 0
            for anno in range(1, int(dati.anni_messa_a_reddito) + 1):
                cf_anno = cashflow_anno_1 if anno == 1 else cashflow_annuo_pieno
                totale_cashflow_accumulato += cf_anno
                if anno == int(dati.anni_messa_a_reddito):
                    timeline_cashflow.append(cf_anno + incasso_netto_vendita)
                else:
                    timeline_cashflow.append(cf_anno)

            utile_totale = totale_cashflow_accumulato + incasso_netto_vendita - capitale_investito_reale

            risultato.update({
                "costi_mantenimento": round(spese_fisse_annue, 2), "metrica_lorda": round(valore_futuro_immobile, 2),
                "utile_netto": round(utile_totale, 2), "cashflow_annuo": round(cashflow_annuo_pieno, 2),
                "cashflow_mensile_netto": round(cashflow_mensile_netto, 2),
                "debito_residuo": round(debito_residuo, 2), "tasse_plusvalenza": round(tasse_plusvalenza, 2),
                "roi_percentuale": round((utile_totale / capitale_investito_reale) * 100, 2) if capitale_investito_reale > 0 else 0,
                "timeline": timeline_cashflow
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
        return {"successo": True, "messaggio": "Deal salvato nel DB!"}
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
