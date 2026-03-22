from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import pathlib
import sqlite3
from datetime import datetime

app = FastAPI(title="Deal Analyzer Pro - Fiscal Edition", version="15.0")

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
    tasso_sfitto_perc: float = 5.0
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
    usa_socio: bool = False
    quota_socio_capitale: float = 100.0
    quota_socio_utile: float = 50.0
    
    # NUOVO: Bonus Ristrutturazione
    usa_bonus_lavori: bool = False

class DealDaSalvare(BaseModel):
    strategia: str
    prezzo_acquisto: float
    mq: float
    investimento_totale: float
    utile_netto: float
    roi_percentuale: float

@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    try:
        # 1. TASSE ACQUISTO
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
        
        # 2. CAPEX E BONUS 50%
        fondo_imprevisti = (dati.costo_lavori_totale * dati.imprevisti_perc) / 100
        costo_lavori = dati.costo_lavori_totale + fondo_imprevisti + dati.spese_extra
        
        credito_fiscale_totale = 0.0
        credito_annuo = 0.0
        if dati.usa_bonus_lavori and costo_lavori > 0:
            base_detraibile = min(costo_lavori, 96000.0) # Tetto massimo legge italiana
            credito_fiscale_totale = base_detraibile * 0.50
            credito_annuo = credito_fiscale_totale / 10.0

        costo_totale_progetto = dati.prezzo_acquisto + tasse_e_notaio + agenzia + costo_lavori
        capitale_investito_reale = costo_totale_progetto

        # 3. LEVA FINANZIARIA E JV
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

        tuo_capitale = capitale_investito_reale
        capitale_socio = 0
        if dati.usa_socio:
            capitale_socio = capitale_investito_reale * (dati.quota_socio_capitale / 100)
            tuo_capitale = capitale_investito_reale - capitale_socio

        # 4. IMU INTELLIGENTE
        imu_mensile = dati.imu_annua / 12
        imu_anno_1 = dati.imu_annua
        imu_a_regime = dati.imu_annua
        if dati.profilo_fiscale == "privato_prima":
            # Paghi l'IMU solo finché non prendi la residenza (mesi di cantiere)
            imu_anno_1 = imu_mensile * dati.mesi_lavori
            imu_a_regime = 0.0

        valore_mercato_iniziale = dati.stima_rivendita if dati.stima_rivendita > 0 else costo_totale_progetto
        timeline_cashflow = [-capitale_investito_reale]

        def calcola_tasse_vendita(prezzo_vendita, costo_tot):
            if dati.profilo_fiscale in ["privato_prima", "privato_seconda"]:
                return max(0, prezzo_vendita - costo_tot) * 0.26
            return 0

        # 5. STRATEGIE OPERATIVE
        if dati.strategia == "Vendita":
            metrica_lorda = valore_mercato_iniziale
            costi_mantenimento = dati.spese_condominio_mensili * dati.mesi_lavori + (imu_mensile * dati.mesi_lavori)
            if dati.usa_mutuo: costi_mantenimento += importo_mutuo * (dati.tasso_mutuo / 100) * (dati.mesi_lavori / 12)
            
            tasse_plusvalenza = calcola_tasse_vendita(valore_mercato_iniziale, costo_totale_progetto)
            # L'utile include il credito d'imposta che ti tieni in IRPEF
            utile_totale = valore_mercato_iniziale - (costo_totale_progetto + costi_mantenimento + tasse_plusvalenza) + credito_fiscale_totale
            timeline_cashflow.append(utile_totale + capitale_investito_reale) 
            
            costi_mant_stress = dati.spese_condominio_mensili * (dati.mesi_lavori + 3) + (imu_mensile * (dati.mesi_lavori + 3))
            if dati.usa_mutuo: costi_mant_stress += importo_mutuo * (dati.tasso_mutuo / 100) * ((dati.mesi_lavori + 3) / 12)
            valore_stress = valore_mercato_iniziale * 0.90
            utile_stress = valore_stress - (costo_totale_progetto + costi_mant_stress + calcola_tasse_vendita(valore_stress, costo_totale_progetto)) + credito_fiscale_totale

            cashflow_annuo_pieno = 0.0
            cashflow_mensile_netto = 0.0
            incasso_mensile_lordo = 0.0
            debito_residuo = 0.0

        else:
            incasso_mensile_lordo = dati.canone_mensile * (1 - (dati.tasso_sfitto_perc / 100))
            metrica_lorda = incasso_mensile_lordo * 12
            
            spese_fisse_mensili_base = dati.spese_condominio_mensili + dati.costo_wifi + dati.costo_luce + dati.costo_gas + dati.costo_acqua_tari
            
            # Opex Anno 1 (con IMU temporanea se prima casa)
            spese_fisse_anno_1 = (spese_fisse_mensili_base * 12) + ((metrica_lorda * dati.gestione_property_perc) / 100) + imu_anno_1 + dati.assicurazione_annua
            if dati.usa_mutuo: spese_fisse_anno_1 += (rata_mensile_mutuo * 12)
            
            # Opex a Regime (dal 2° anno)
            spese_fisse_a_regime = (spese_fisse_mensili_base * 12) + ((metrica_lorda * dati.gestione_property_perc) / 100) + imu_a_regime + dati.assicurazione_annua
            if dati.usa_mutuo: spese_fisse_a_regime += (rata_mensile_mutuo * 12)

            tasse_affitto = (metrica_lorda * dati.cedolare_secca_perc) / 100
            
            # Aggiungiamo il Credito d'Imposta al Cashflow Netto
            cashflow_annuo_pieno = metrica_lorda - spese_fisse_a_regime - tasse_affitto + credito_annuo
            cashflow_mensile_netto = cashflow_annuo_pieno / 12
            
            mesi_affitto_anno_1 = max(0, 12 - dati.mesi_lavori)
            incasso_anno_1 = dati.canone_mensile * mesi_affitto_anno_1 * (1 - (dati.tasso_sfitto_perc / 100))
            cashflow_anno_1 = incasso_anno_1 - spese_fisse_anno_1 - ((incasso_anno_1 * dati.cedolare_secca_perc)/100) + credito_annuo
            
            if dati.strategia == "Affitto":
                timeline_cashflow.append(cashflow_anno_1)
                for i in range(2, 6): # Proiezione 5 anni
                    timeline_cashflow.append(cashflow_annuo_pieno) 
                utile_totale = cashflow_annuo_pieno
                
                metrica_lorda_stress = (dati.canone_mensile * 12 * 0.90) * (1 - ((dati.tasso_sfitto_perc * 2) / 100))
                utile_stress = metrica_lorda_stress - spese_fisse_a_regime - ((metrica_lorda_stress * dati.cedolare_secca_perc) / 100) + credito_annuo
                debito_residuo = 0.0
                tasse_plusvalenza = 0.0

            elif dati.strategia == "Mista":
                valore_futuro_immobile = valore_mercato_iniziale * ((1 + (dati.apprezzamento_annuo / 100)) ** dati.anni_messa_a_reddito)
                metrica_lorda = valore_futuro_immobile
                debito_residuo = 0
                if dati.usa_mutuo and dati.anni_mutuo > 0:
                    mesi_pagati = dati.anni_messa_a_reddito * 12
                    if mesi_pagati < dati.anni_mutuo * 12:
                        if dati.tasso_mutuo > 0:
                            r = (dati.tasso_mutuo / 100) / 12
                            debito_residuo = importo_mutuo * (((1 + r)**(dati.anni_mutuo * 12) - (1 + r)**mesi_pagati) / ((1 + r)**(dati.anni_mutuo * 12) - 1))
                        else:
                            debito_residuo = importo_mutuo - (rata_mensile_mutuo * mesi_pagati)
                
                tasse_plusvalenza = calcola_tasse_vendita(valore_futuro_immobile, costo_totale_progetto) if dati.anni_messa_a_reddito <= 5 else 0
                incasso_netto_vendita = valore_futuro_immobile - debito_residuo - tasse_plusvalenza
                
                # Se l'affitto dura meno di 10 anni, incassi il residuo del bonus in fase di vendita (se lo tieni)
                bonus_residuo = credito_fiscale_totale - (credito_annuo * dati.anni_messa_a_reddito) if dati.anni_messa_a_reddito < 10 else 0
                
                tot_cf = cashflow_anno_1 + (cashflow_annuo_pieno * (dati.anni_messa_a_reddito - 1))
                utile_totale = tot_cf + incasso_netto_vendita + bonus_residuo - capitale_investito_reale
                
                for anno in range(1, int(dati.anni_messa_a_reddito) + 1):
                    cf = cashflow_anno_1 if anno == 1 else cashflow_annuo_pieno
                    timeline_cashflow.append(cf + incasso_netto_vendita + bonus_residuo if anno == int(dati.anni_messa_a_reddito) else cf)

                valore_stress = valore_futuro_immobile * 0.90
                incasso_stress = valore_stress - debito_residuo - calcola_tasse_vendita(valore_stress, costo_totale_progetto)
                utile_stress = tot_cf + incasso_stress + bonus_residuo - capitale_investito_reale

        if dati.usa_socio:
            utile_socio = utile_totale * (dati.quota_socio_utile / 100)
            tuo_utile = utile_totale - utile_socio
        else:
            tuo_utile = utile_totale

        tuo_roi = (tuo_utile / tuo_capitale) * 100 if tuo_capitale > 0 else 999.0
        roi_stress = (utile_stress / capitale_investito_reale) * 100 if capitale_investito_reale > 0 else 0

        return {
            "strategia": dati.strategia, "tasse_e_notaio": round(tasse_e_notaio, 2), "agenzia": round(agenzia, 2),
            "costo_lavori": round(costo_lavori, 2), "costo_totale_progetto": round(costo_totale_progetto, 2),
            "usa_mutuo": dati.usa_mutuo, "importo_mutuo": round(importo_mutuo, 2), "rata_mensile_mutuo": round(rata_mensile_mutuo, 2),
            "capitale_proprio_totale": round(capitale_investito_reale, 2), "valore_mercato_iniziale": round(valore_mercato_iniziale, 2),
            "tuo_capitale": round(tuo_capitale, 2), "capitale_socio": round(capitale_socio, 2), "usa_socio": dati.usa_socio,
            "metrica_lorda": round(metrica_lorda, 2), "utile_totale": round(utile_totale, 2), "tuo_utile": round(tuo_utile, 2), "utile_socio": round(utile_socio, 2),
            "roi_percentuale": round((utile_totale / capitale_investito_reale) * 100, 2) if capitale_investito_reale > 0 else 0,
            "tuo_roi": round(tuo_roi, 2), "utile_stress": round(utile_stress, 2), "roi_stress": round(roi_stress, 2),
            "timeline": timeline_cashflow, "incasso_mensile_lordo": round(incasso_mensile_lordo, 2),
            "cashflow_mensile_netto": round(cashflow_mensile_netto, 2), "cashflow_annuo": round(cashflow_annuo_pieno, 2),
            "tasse_plusvalenza": round(tasse_plusvalenza, 2), "debito_residuo": round(debito_residuo, 2),
            "credito_fiscale_totale": round(credito_fiscale_totale, 2), "credito_annuo": round(credito_annuo, 2)
        }
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"detail": f"Errore interno del server Python: {str(e)}"})

@app.post("/api/salva-deal")
def salva_deal(deal: DealDaSalvare):
    conn = sqlite3.connect('deals.db')
    c = conn.cursor()
    c.execute("INSERT INTO deals (data_salvataggio, strategia, prezzo_acquisto, mq, investimento_totale, utile_netto, roi_percentuale) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (datetime.now().strftime("%d/%m/%Y %H:%M"), deal.strategia, deal.prezzo_acquisto, deal.mq, deal.investimento_totale, deal.utile_netto, deal.roi_percentuale))
    conn.commit()
    conn.close()
    return {"successo": True}

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
