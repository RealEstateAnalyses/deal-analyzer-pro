from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
import pathlib
import sqlite3
from datetime import datetime

# Configurazione App - Luxury Pro Edition (Unified Cashflow Engine)
app = FastAPI(title="Deal Analyzer Pro - Luxury", version="20.0")

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

# --- MODELLI DATI (Pydantic) ---
class EventoFuturo(BaseModel):
    anno: int
    tipo: str # 'lavori' o 'sfitto'
    valore: float
    
class InputDeal(BaseModel):
    # Acquisizione
    prezzo_acquisto: float = 0.0
    mq: float = 0.0
    strategia: str = "Vendita"
    profilo_fiscale: str = "privato_seconda"
    rendita_catastale: float = 0.0
    agenzia_percentuale: float = 3.0
    notaio: float = 2500.0
    
    # Capex / Lavori
    mesi_lavori: float = 6.0
    costo_lavori_totale: float = 0.0
    imprevisti_perc: float = 10.0
    spese_extra: float = 0.0
    usa_bonus_lavori: bool = False
    
    # Gestione / B&H
    tipo_affitto: str = "lungo" # 'lungo' o 'breve'
    anni_messa_a_reddito: float = 5.0
    canone_mensile: float = 0.0
    tasso_sfitto_perc: float = 5.0
    cedolare_secca_perc: float = 21.0
    imu_annua: float = 0.0 
    mesi_imu_temporanea: float = 6.0 # Mesi di residenza fittizia IMU Prima Casa
    spese_condominio_mensili: float = 0.0
    
    # Short Rent Extra
    adr_notte: float = 0.0
    occupazione_perc: float = 70.0
    commissioni_piattaforma_perc: float = 15.0
    pulizie_mensili: float = 0.0
    
    # Utenze B&H (a carico proprietario)
    costo_luce: float = 0.0
    costo_gas: float = 0.0
    costo_acqua_tari: float = 0.0
    costo_wifi: float = 0.0
    assicurazione_annua: float = 0.0
    gestione_property_perc: float = 0.0
    
    # Exit / Mista
    stima_rivendita: float = 0.0 
    apprezzamento_annuo: float = 2.0 
    
    # Finanziamento / JV
    usa_mutuo: bool = False
    capitale_proprio: float = 30000.0
    tasso_mutuo: float = 3.5
    anni_mutuo: float = 20.0
    
    usa_socio: bool = False
    percentuali_capitale_soci: list[float] = [100.0]
    percentuali_utile_soci: list[float] = [50.0]
    
    # MACCHINA DEL TEMPO
    eventi_futuri: list[EventoFuturo] = []


class DealDaSalvare(BaseModel):
    strategia: str
    prezzo_acquisto: float
    mq: float
    investimento_totale: float
    utile_netto: float
    roi_percentuale: float


# --- MOTORE DI CALCOLO UNIFICATO ---
@app.post("/api/calcola-roi")
def calcola_roi(dati: InputDeal):
    try:
        # 1. Costi Acquisizione
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
        
        # 2. CAPEX e Bonus
        fondo_imprevisti = (dati.costo_lavori_totale * dati.imprevisti_perc) / 100
        costo_lavori = dati.costo_lavori_totale + fondo_imprevisti + dati.spese_extra
        
        credito_fiscale_totale = 0.0
        credito_annuo = 0.0
        if dati.usa_bonus_lavori and costo_lavori > 0:
            base_detraibile = min(costo_lavori, 96000.0) 
            credito_fiscale_totale = base_detraibile * 0.50
            credito_annuo = credito_fiscale_totale / 10.0

        costo_totale_progetto = dati.prezzo_acquisto + tasse_e_notaio + agenzia + costo_lavori
        
        # Equity iniziale reale da coprire
        capitale_investito_reale = costo_totale_progetto

        # 3. Leva Finanziaria
        importo_mutuo = 0
        rata_mensile_mutuo = 0
        if dati.usa_mutuo and dati.capitale_proprio < costo_totale_progetto:
            importo_mutuo = costo_totale_progetto - dati.capitale_proprio
            capitale_investito_reale = dati.capitale_proprio # L'equity diventa la tua disponibilità dichiarata
            
            if dati.anni_mutuo > 0:
                if dati.tasso_mutuo > 0:
                    r = (dati.tasso_mutuo / 100) / 12
                    n = dati.anni_mutuo * 12
                    rata_mensile_mutuo = importo_mutuo * (r * (1 + r)**n) / ((1 + r)**n - 1)
                else:
                    rata_mensile_mutuo = importo_mutuo / (dati.anni_mutuo * 12)

        # 4. Joint Venture (Split Equity Iniziale)
        tuo_capitale_jv = capitale_investito_reale
        totale_capitale_soci = 0.0
        
        if dati.usa_socio and dati.percentuali_capitale_soci:
            # Calcolo basato su equity reale (capitale_investito_reale)
            for perc in dati.percentuali_capitale_soci:
                if perc <= 0: continue
                totale_capitale_soci += capitale_investito_reale * (perc / 100)
            
            tuo_capitale_jv = capitale_investito_reale - totale_capitale_soci

        # 5. IMU Chirurgica
        imu_mensile = dati.imu_annua / 12
        imu_anno_1 = dati.imu_annua
        imu_a_regime = dati.imu_annua
        if dati.profilo_fiscale == "privato_prima":
            imu_anno_1 = imu_mensile * dati.mesi_imu_temporanea # Paghi IMU Seconda Casa per X mesi pre-residenza
            imu_a_regime = 0.0 # Poi diventa Prima Casa esente (assumiamo A/2, A/3)

        timeline_cashflow = [-capitale_investito_reale]
        
        # Base di calcolo per exit o timeline
        valore_mercato_iniziale = dati.stima_rivendita if dati.stima_rivendita > 0 else costo_totale_progetto

        def calcola_tasse_vendita(prezzo_vendita, costo_tot, profilo_fiscale):
            # Assumiamo possesso < 5 anni per il Capital Gain 26% (tranne mista lungo termine)
            if profilo_fiscale in ["privato_prima", "privato_seconda"]:
                return max(0, prezzo_vendita - costo_tot) * 0.26
            return 0

        # Inizializzatori metriche per Buy&Hold/Mista (evitano crash se usate in visualizzazione)
        incasso_mensile_lordo_visualizzazione = 0.0
        cashflow_mensile_netto_visualizzazione = 0.0
        tasse_plusvalenza_visualizzazione = 0.0
        debito_residuo_visualizzazione = 0.0
        cashflow_annuo_visualizzazione = 0.0 # Per Affitto (somma utile totale)

        # --- SCENARIO 1: FLIPPING (Vendita Pura) ---
        if dati.strategia == "Vendita":
            # Costi mantenimento cantiere
            # IMU chirurgica se prima casa
            imu_totale_vendita = imu_anno_1 if dati.profilo_fiscale == "privato_prima" else (imu_mensile * dati.mesi_lavori)
            
            costi_mantenimento = (dati.spese_condominio_mensili * dati.mesi_lavori) + imu_totale_vendita
            
            # Interessi preammortamento se mutuo (mesi lavori)
            if dati.usa_mutuo and importo_mutuo > 0:
                # Approssimazione preammortamento tecnico solo quota interessi
                costi_mantenimento += importo_mutuo * (dati.tasso_mutuo / 100) * (dati.mesi_lavori / 12)
            
            tasse_plusvalenza_visualizzazione = calcola_tasse_vendita(valore_mercato_iniziale, costo_totale_progetto, dati.profilo_fiscale)
            
            utile_totale = valore_mercato_iniziale - (costo_totale_progetto + costi_mantenimento + tasse_plusvalenza_visualizzazione) + credito_fiscale_totale
            timeline_cashflow.append(utile_totale + capitale_investito_reale) # Cash-on-Cash Exit
            
            metrica_lorda_visualizzazione = valore_mercato_iniziale
            
            # Stress Test Flipping: Valore uscita -10%, cantiere +3 mesi
            valore_stress = valore_mercato_iniziale * 0.90
            mesi_lavori_stress = dati.mesi_lavori + 3
            
            imu_stress_vendita = (imu_mensile * dati.mesi_imu_temporanea) if dati.profilo_fiscale == "privato_prima" else (imu_mensile * mesi_lavori_stress)
            
            costi_mantenimento_stress = dati.spese_condominio_mensili * mesi_lavori_stress + imu_stress_vendita
            if dati.usa_mutuo: costi_mantenimento_stress += importo_mutuo * (dati.tasso_mutuo / 100) * (mesi_lavori_stress / 12)
            
            utile_stress = valore_stress - (costo_totale_progetto + costi_mantenimento_stress + calcola_tasse_vendita(valore_stress, costo_totale_progetto, dati.profilo_fiscale)) + credito_fiscale_totale

        # --- SCENARIO 2 & 3: B&H e MISTA (Buy, Rent & Sell) ---
        else:
            utile_totale = 0.0
            timeline_cashflow = [-capitale_investito_reale]
            
            spese_fisse_mensili_proprietario_base = (dati.spese_condominio_mensili + dati.costo_wifi + dati.costo_luce + dati.costo_gas + dati.costo_acqua_tari)
            
            # Calcolo Revenue & Opex Mensile Assoluto (A REGIME)
            if dati.tipo_affitto == "breve":
                rev_mensile_lorda_regime = (dati.adr_notte * 30.4) * (dati.occupazione_perc / 100)
                opex_gestione_breve = (rev_mensile_lorda_regime * (dati.commissioni_piattaforma_perc / 100)) + dati.pulizie_mensili
                incasso_mensile_netto_property = rev_mensile_lorda_regime - opex_gestione_breve
            else:
                incasso_mensile_netto_property = dati.canone_mensile * (1 - (dati.tasso_sfitto_perc / 100))

            # Calcolo Opex Fisse Mensili Regime (Property Mgr, IMU, Assicurazione)
            incasso_annuo_regime_metrica_lorda = incasso_mensile_netto_property * 12
            property_mgr_fee = (incasso_annuo_regime_metrica_lorda * (dati.gestione_property_perc / 100)) / 12
            
            spese_proprietario_regime_no_mutuo_mensili = spese_fisse_mensili_base + property_mgr_fee + (imu_a_regime / 12) + (dati.assicurazione_annua / 12)
            tasse_mensili_regime = (incasso_annuo_regime_metrica_lorda * (dati.cedolare_secca_perc / 100)) / 12
            
            base_cashflow_mensile_regime_no_credito = incasso_mensile_netto_property - spese_proprietario_regime_no_mutuo_mensili - tasse_mensili_regime
            if dati.usa_mutuo: base_cashflow_mensile_regime_no_credito -= rata_mensile_mutuo

            # Visualizzazioni per UI (A REGIME)
            # Incasso lordo property mgr
            incasso_mensile_lordo_visualizzazione = dati.canone_mensile if dati.tipo_affitto == "lungo" else incasso_mensile_netto_property 
            # Netto tasca a regime
            cashflow_mensile_netto_visualizzazione = base_cashflow_mensile_regime_no_credito + (credito_annuo / 12)
            cashflow_annuo_pieno_regime = cashflow_mensile_netto_visualizzazione * 12

            # --- MOTORE MACCHINA DEL TEMPO (CICLO ANNUO) ---
            totale_anni = int(dati.anni_messa_a_reddito) if dati.strategia == "Mista" else 5
            
            for anno in range(1, totale_anni + 1):
                cf_anno = 0.0
                
                if anno == 1:
                    # Anno 1 chirurgico: Mesi Cantiere (no incasso, opex piene, preammortamento) vs Mesi Affitto
                    mesi_affitto = max(0, 12 - dati.mesi_lavori)
                    
                    # Costi cantiere fissi (condominio, utenze cantiere ridotte se non dichiarate, assicurazione, IMU Temporanea)
                    costi_mantenimento_cantiere = (dati.spese_condominio_mensili * dati.mesi_lavori) + imu_anno_1 + (dati.assicurazione_annua)
                    
                    # Preammortamento mutuo se presente
                    if dati.usa_mutuo and importo_mutuo > 0:
                        costi_mantenimento_cantiere += importo_mutuo * (dati.tasso_mutuo / 100) * (dati.mesi_lavori / 12)
                    
                    # Cashflow mesi affitto a regime
                    cashflow_mesi_affitto = (base_cashflow_mensile_regime_no_credito if dati.usa_mutuo else (incasso_mensile_netto_property - spese_proprietario_regime_no_mutuo_mensili - tasse_mensili_regime)) * mesi_affitto
                    # NOTA: se c'è mutuo, la rata mensile la paghi anche nei mesi affitto se hai finito preammortamento, ma qui semplifichiamo a regime.
                    
                    cf_anno = cashflow_mesi_affitto - costi_mantenimento_cantiere + credito_annuo
                else:
                    # Anni 2+ a regime
                    cf_anno = cashflow_annuo_pieno_regime

                # --- APPLICAZIONE EVENTI FUTURI (MACCHINA DEL TEMPO) ---
                for ev in dati.eventi_futuri:
                    if ev.anno == anno:
                        if ev.tipo == "lavori":
                            cf_anno -= ev.valore
                        elif ev.tipo == "sfitto":
                            # valore = mesi di sfitto volontario (perdi incasso lordo property mgr mensile)
                            cf_anno -= incasso_mensile_netto_property * ev.valore

                # --- EXIT STRATEGY (MISTA - ULTIMO ANNO) ---
                if dati.strategia == "Mista" and anno == totale_anni:
                    # Calcolo apprezzamento composto
                    valore_futuro_immobile = valore_mercato_iniziale * ((1 + (dati.apprezzamento_annuo / 100)) ** totale_anni)
                    metrica_lorda_visualizzazione = valore_futuro_immobile
                    
                    # Estinzione Debito Residuo Mutuo
                    debito_residuo_visualizzazione = 0.0
                    if dati.usa_mutuo and importo_mutuo > 0 and dati.anni_mutuo > 0:
                        mesi_passati = totale_anni * 12
                        mesi_tot_mutuo = dati.anni_mutuo * 12
                        
                        if mesi_passati < mesi_tot_mutuo:
                            # Formula Standard Debito Residuo Mutuo Ammortamento Francese
                            r = (dati.tasso_mutuo / 100) / 12
                            debito_residuo_visualizzazione = importo_mutuo * ( ((1+r)**mesi_tot_mutuo) - ((1+r)**mesi_passati) ) / ( ((1+r)**mesi_tot_mutuo) - 1 )
                        else:
                            debito_residuo_visualizzazione = 0.0 # Mutuo finito
                    
                    # Tasse Plusvalenza ( Capital Gain se possesso < 5 anni)
                    tasse_plusvalenza_visualizzazione = calcola_tasse_vendita(valore_futuro_immobile, costo_totale_progetto, dati.profilo_fiscale) if totale_anni <= 5 else 0.0
                    
                    # Incasso Netto Exit Mista
                    incasso_netto_exit = valore_futuro_immobile - debito_residuo_visualizzazione - tasse_plusvalenza_visualizzazione
                    
                    # Crediti fiscali residui (bonus ristrutturazione 10y)
                    bonus_residuo = credito_fiscale_totale - (credito_annuo * totale_anni) if totale_anni < 10 else 0.0
                    
                    # Aggiungiamo exit netta al cashflow dell'ultimo anno
                    cf_anno += incasso_netto_exit + bonus_residuo
                
                # Popola Timeline
                timeline_cashflow.append(cf_anno)
                utile_totale += cf_anno

            # Sottraiamo l'equity iniziale per ottenere l'utile netto finale totale simulazione
            utile_totale -= capitale_investito_reale
            
            # Stress Test Buy&Hold/Mista (Assumiamo crollo affitti -10%, sfitto raddoppiato)
            incasso_stress_mensile = dati.canone_mensile * 0.90 * (1 - ((dati.tasso_sfitto_perc * 2) / 100))
            incasso_annuo_stress_metrica = incasso_stress_mensile * 12
            
            opex_gestione_stress = (incasso_annuo_stress_metrica * (dati.gestione_property_perc / 100))
            
            # Opex fisse stress (IMU, Condominio, Assicurazione)
            opex_fisse_stress_annue = (dati.spese_condominio_mensili * 12) + opex_gestione_stress + imu_a_regime + dati.assicurazione_annua
            tasse_stress = (incasso_annuo_stress_metrica * dati.cedolare_secca_perc) / 100
            
            utile_stress_annuo = incasso_annuo_stress_metrica - opex_fisse_stress_annue - tasse_stress + credito_annuo
            
            if dati.usa_mutuo: utile_stress_annuo -= (rata_mensile_mutuo * 12)
            
            # Utile stress calcolato su tutto il periodo simulazione
            utile_stress = (utile_stress_annuo * totale_anni) - capitale_investito_reale
            cashflow_annuo_visualizzazione = utile_totale # Per Affitto UI

        # 6. Joint Venture Utile Split (Calcolo ROI reale tuo)
        tuo_utile_netto_jv = utile_totale
        totale_utile_soci = 0.0
        soci_risultati_finali = []
        
        if dati.usa_socio and dati.percentuali_capitale_soci and dati.percentuali_utile_soci:
            for i in range(len(dati.percentuali_capitale_soci)):
                perc_cap = dati.percentuali_capitale_soci[i]
                perc_utile_concordata = dati.percentuali_utile_soci[min(i, len(dati.percentuali_utile_soci)-1)] # Sicurezza array corto
                
                if perc_cap <= 0: continue
                
                capitale_socio_i = capitale_investito_reale * (perc_cap / 100)
                utile_netto_socio_i = utile_totale * (perc_utile_concordata / 100)
                
                totale_utile_soci += utile_netto_socio_i
                
                soci_risultati_finali.append({
                    "id": i + 1,
                    "capitale_investito": round(capitale_socio_i, 2),
                    "utile_netto": round(utile_netto_socio_i, 2),
                    "percentuale_utile_concordata": perc_utile_concordata
                })
            
            tuo_utile_netto_jv = utile_totale - totale_utile_soci

        tuo_roi_reale_jv = (tuo_utile_netto_jv / tuo_capitale_jv * 100) if tuo_capitale_jv > 0 else (999.0 if tuo_utile_netto_jv > 0 else 0.0) # ROI infinito se no capital
        
        # 7. Output Finale UI
        return {
            "strategia": dati.strategia, "profilo_fiscale": dati.profilo_fiscale,
            "metrica_lorda": round(valore_mercato_iniziale, 2), # Flipping/Mista
            "tasse_e_notaio": round(tasse_e_notaio, 2), "agenzia": round(agenzia, 2),
            "costo_lavori": round(costo_lavori, 2), "costo_totale_progetto": round(costo_totale_progetto, 2),
            "credito_fiscale_totale": round(credito_fiscale_totale, 2),
            
            "usa_mutuo": dati.usa_mutuo, "importo_mutuo": round(importo_mutuo, 2), "rata_mensile_mutuo": round(rata_mensile_mutuo, 2),
            "tasse_plusvalenza": round(tasse_plusvalenza_visualizzazione, 2), "debito_residuo": round(debito_residuo_visualizzazione, 2),
            
            "usa_socio": dati.usa_socio, "capitale_proprio_totale": round(capitale_investito_reale, 2),
            "tuo_capitale": round(tuo_capitale_jv, 2), "capitale_soci": round(totale_capitale_soci, 2),
            "lista_dettagliata_soci": soci_risultati_finali,
            
            "utile_totale": round(utile_totale, 2), "tuo_utile": round(tuo_utile_netto_jv, 2), "utile_soci": round(totale_utile_soci, 2),
            "roi_percentuale": round((utile_totale / capitale_investito_reale * 100), 2) if capitale_investito_reale > 0 else 0.0,
            "tuo_roi": round(tuo_roi_reale_jv, 2),
            
            "incasso_mensile_lordo": round(incasso_mensile_lordo_visualizzazione, 2), "cashflow_mensile_netto": round(cashflow_mensile_netto_visualizzazione, 2),
            "cashflow_annuo": round(cashflow_annuo_visualizzazione, 2),
            
            "timeline": timeline_cashflow, "utile_stress": round(utile_stress, 2), "roi_stress": round((utile_stress / capitale_investito_reale * 100), 2) if capitale_investito_reale > 0 else 0.0
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"⚠️ ERRORE MOTORE PYTHON: {str(e)}"})

# --- DB MANAGEMENT ---
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
