import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import io
import hashlib
import os
import shutil
import tempfile
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from fpdf import FPDF
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CAPA DE DATOS (SQL RELACIONAL)
# ==============================================================================
def init_erp_db():
    conn = sqlite3.connect('sgsst_master.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS personal (
                    rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, 
                    centro_costo TEXT, fecha_contrato DATE, estado TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, tema TEXT, expositor TEXT, 
                    fecha DATE, duracion TEXT, estado TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, id_capacitacion INTEGER, 
                    rut_trabajador TEXT, hora_firma DATETIME, firma_digital_hash TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, cargo_asociado TEXT, proceso TEXT, 
                    peligro TEXT, riesgo TEXT, consecuencia TEXT, medida_control TEXT, criticidad TEXT)''')

    # Carga inicial de datos si está vacío
    c.execute("SELECT count(*) FROM personal")
    if c.fetchone()[0] == 0:
        staff_real = [
            ("16.781.002-0", "ALAN FABIAN GARCIA VIDAL", "APR", "OFICINA", "2025-10-21", "ACTIVO"),
            ("10.518.096-9", "OSCAR EDUARDO TRIVIÑO SALAZAR", "OPERADOR HARVESTER", "FAENA", "2024-01-01", "ACTIVO"),
            ("15.282.021-6", "ALBERTO LOAIZA MANSILLA", "JEFE DE PATIO", "ASERRADERO", "2023-05-10", "ACTIVO"),
            ("9.914.127-1", "JOSE MIGUEL OPORTO GODOY", "OPERADOR ASERRADERO", "ASERRADERO", "2022-03-15", "ACTIVO"),
            ("23.076.765-3", "GIVENS ABURTO CAMINO", "AYUDANTE", "ASERRADERO", "2025-02-01", "ACTIVO"),
            ("13.736.331-3", "MAURICIO LOPEZ GUTIÉRREZ", "ADMINISTRATIVO", "OFICINA", "2025-06-06", "ACTIVO")
        ]
        c.executemany("INSERT INTO personal VALUES (?,?,?,?,?,?)", staff_real)

    c.execute("SELECT count(*) FROM matriz_iper")
    if c.fetchone()[0] == 0:
        iper_data = [
            ("OPERADOR HARVESTER", "Cosecha", "Pendiente", "Volcamiento", "Muerte", "Cabina ROPS", "CRITICO"),
            ("OPERADOR ASERRADERO", "Corte", "Sierra Móvil", "Corte/Amputación", "Lesión Grave", "Guardas Fijas", "ALTO")
        ]
        c.executemany("INSERT INTO matriz_iper (cargo_asociado, proceso, peligro, riesgo, consecuencia, medida_control, criticidad) VALUES (?,?,?,?,?,?,?)", iper_data)

    conn.commit()
    conn.close()

# ==============================================================================
# 2. FUNCIONES DE SOPORTE DASHBOARD BI
# ==============================================================================
CSV_FILE = "base_datos_galvez_v26.csv"
LOGO_FILE = "logo_empresa_persistente.png"
MESES_ORDEN = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
COLOR_PRIMARY = (183, 28, 28)
COLOR_SECONDARY = (50, 50, 50)

def get_structure_for_year(year):
    data = []
    for m in MESES_ORDEN:
        data.append({
            'Año': int(year), 'Mes': m,
            'Masa Laboral': 0.0, 'Horas Extras': 0.0, 'Horas Ausentismo': 0.0,
            'Accidentes CTP': 0.0, 'Accidentes Fatales': 0.0, 'Días Perdidos': 0.0, 'Días Cargo': 0.0,
            'Enf. Profesionales': 0.0, 'Días Perdidos EP': 0.0, 'Pensionados': 0.0, 'Indemnizados': 0.0,
            'Insp. Programadas': 0.0, 'Insp. Ejecutadas': 0.0, 'Cap. Programadas': 0.0, 'Cap. Ejecutadas': 0.0,
            'Medidas Abiertas': 0.0, 'Medidas Cerradas': 0.0, 'Expuestos Silice/Ruido': 0.0, 'Vig. Salud Vigente': 0.0,
            'Observaciones': "", 'HHT': 0.0, 'Tasa Acc.': 0.0, 'Tasa Sin.': 0.0, 'Indice Frec.': 0.0, 'Indice Grav.': 0.0
        })
    return pd.DataFrame(data)

def inicializar_db_completa():
    df_24 = get_structure_for_year(2024); df_25 = get_structure_for_year(2025); df_26 = get_structure_for_year(2026)
    return pd.concat([df_24, df_25, df_26], ignore_index=True)

def procesar_datos(df, factor_base=210):
    cols_exclude = ['Año', 'Mes', 'Observaciones']
    for col in df.columns:
        if col not in cols_exclude:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['Año'] = df['Año'].fillna(2026).astype(int)
    if 'Observaciones' not in df.columns: df['Observaciones'] = ""
    df['Observaciones'] = df['Observaciones'].fillna("").astype(str)
    df['HHT'] = (df['Masa Laboral'] * factor_base) + df['Horas Extras'] - df['Horas Ausentismo']
    df['HHT'] = df['HHT'].apply(lambda x: x if x > 0 else 0)
    
    def calc_row(row):
        masa = row['Masa Laboral']; hht = row['HHT']
        if masa <= 0 or hht <= 0: return 0, 0, 0, 0
        ta = (row['Accidentes CTP'] / masa) * 100
        ts = (row['Días Perdidos'] / masa) * 100 
        if_ = (row['Accidentes CTP'] * 1000000) / hht
        ig = ((row['Días Perdidos'] + row['Días Cargo']) * 1000000) / hht
        return ta, ts, if_, ig

    result = df.apply(calc_row, axis=1, result_type='expand')
    df['Tasa Acc.'] = result[0]; df['Tasa Sin.'] = result[1]; df['Indice Frec.'] = result[2]; df['Indice Grav.'] = result[3]
    return df

def load_data():
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            if df.empty: return inicializar_db_completa()
            ref_df = get_structure_for_year(2026)
            for col in ref_df.columns:
                if col not in df.columns:
                    if col == 'Observaciones': df[col] = ""
                    else: df[col] = 0.0
            return procesar_datos(df[ref_df.columns], 210)
        except: return inicializar_db_completa()
    return inicializar_db_completa()

def save_data(df, factor_base):
    df_calc = procesar_datos(df, factor_base)
    if os.path.exists(CSV_FILE):
        try: shutil.copy(CSV_FILE, f"{CSV_FILE}.bak")
        except: pass
    df_calc.to_csv(CSV_FILE, index=False)
    return df_calc

def generar_insight_automatico(row_mes, ta_acum, metas):
    insights = []
    if ta_acum > metas['meta_ta']: insights.append(f"⚠️ <b>ALERTA:</b> Tasa Acumulada ({ta_acum:.2f}%) excede meta")
    elif ta_acum > (metas['meta_ta'] * 0.8): insights.append(f"🔸 <b>PRECAUCIÓN:</b> Tasa Acumulada al límite.")
    else: insights.append(f"✅ <b>EXCELENTE:</b> Accidentabilidad bajo control.")
    if row_mes['Tasa Sin.'] > 0: insights.append(f"🚑 <b>DÍAS PERDIDOS:</b> {int(row_mes['Días Perdidos'])} días perdidos.")
    if not insights: return "Sin desviaciones."
    return "<br>".join(insights)

class PDF_SST(FPDF):
    def header(self):
        self.set_fill_color(245, 245, 245); self.rect(0, 0, 210, 40, 'F')
        if os.path.exists(LOGO_FILE): self.image(LOGO_FILE, 10, 8, 35)
        self.set_xy(50, 10); self.set_font('Arial', 'B', 16); self.set_text_color(*COLOR_PRIMARY)
        self.cell(0, 8, 'SOCIEDAD MADERERA GALVEZ Y DI GENOVA LTDA', 0, 1, 'L')
        self.set_xy(50, 18); self.set_font('Arial', 'B', 11); self.set_text_color(*COLOR_SECONDARY)
        self.cell(0, 6, 'INFORME EJECUTIVO DE GESTIÓN SST (DS 44)', 0, 1, 'L')
        self.set_draw_color(*COLOR_PRIMARY); self.set_line_width(1); self.line(10, 38, 200, 38); self.ln(30)

    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.set_text_color(150)
        self.cell(0, 10, f'Documento Oficial SGSST - Pagina {self.page_no()}', 0, 0, 'C')

    def section_title(self, title):
        self.set_font('Arial', 'B', 12); self.set_fill_color(*COLOR_SECONDARY); self.set_text_color(255, 255, 255)
        self.cell(0, 8, f"  {title}", 0, 1, 'L', 1); self.set_text_color(0, 0, 0); self.ln(4)

    def draw_donut_chart_image(self, val_pct, color_hex, x, y, size=30):
        try:
            val_plot = min(val_pct, 100); val_plot = max(val_plot, 0)
            fig, ax = plt.subplots(figsize=(2, 2))
            ax.pie([val_plot, 100-val_plot], colors=[color_hex, '#eeeeee'], startangle=90, counterclock=False, wedgeprops=dict(width=0.4, edgecolor='white'))
            ax.text(0, 0, f"{val_pct:.0f}%", ha='center', va='center', fontsize=12, fontweight='bold', color='#333333')
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                plt.savefig(tmp.name, format='png', transparent=True, dpi=100, bbox_inches='tight')
                tmp_name = tmp.name
            plt.close(fig); self.image(tmp_name, x=x, y=y, w=size, h=size); os.unlink(tmp_name)
        except: pass

    def draw_kpi_circle_pair(self, title, val_m, val_a, max_scale, meta, unit, x, y):
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(4, 2))
            color_m = '#4CAF50' if val_m <= meta else '#F44336'
            if "Gest" in title: color_m = '#4CAF50' if val_m >= meta else '#F44336'
            val_m_plot = min(val_m, max_scale); rem_m = max_scale - val_m_plot
            ax1.pie([val_m_plot, rem_m], colors=[color_m, '#EEEEEE'], startangle=90, counterclock=False, wedgeprops=dict(width=0.3, edgecolor='white'))
            ax1.text(0, 0, f"{val_m:.1f}\n{unit}", ha='center', va='center', fontsize=10, fontweight='bold')
            ax1.set_title("MENSUAL", fontsize=8, color='#555555')
            color_a = '#4CAF50' if val_a <= meta else '#F44336'
            if "Gest" in title: color_a = '#4CAF50' if val_a >= meta else '#F44336'
            val_a_plot = min(val_a, max_scale); rem_a = max_scale - val_a_plot
            ax2.pie([val_a_plot, rem_a], colors=[color_a, '#EEEEEE'], startangle=90, counterclock=False, wedgeprops=dict(width=0.3, edgecolor='white'))
            ax2.text(0, 0, f"{val_a:.1f}\n{unit}", ha='center', va='center', fontsize=10, fontweight='bold')
            ax2.set_title("ACUMULADO", fontsize=8, color='#555555')
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                plt.savefig(tmp.name, format='png', bbox_inches='tight', dpi=100)
                tmp_name = tmp.name
            plt.close(fig); self.set_xy(x, y); self.set_font('Arial', 'B', 9)
            self.cell(90, 8, title, 0, 1, 'C'); self.image(tmp_name, x=x+5, y=y+8, w=80, h=40); os.unlink(tmp_name)
        except: pass

    def clean_text(self, text):
        replacements = {'\u2013': '-', '\u2014': '-', '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2022': '*', '€': 'EUR'}
        for k, v in replacements.items(): text = text.replace(k, v)
        return text.encode('latin-1', 'replace').decode('latin-1')

    def footer_signatures(self):
        y_pos = self.get_y() + 10
        if y_pos > 250: self.add_page(); y_pos = self.get_y() + 20
        self.set_y(y_pos); self.line(20, y_pos, 90, y_pos)
        self.set_xy(20, y_pos + 2); self.set_font('Arial', 'B', 9); self.set_text_color(0,0,0)
        self.cell(70, 5, "RODRIGO GALVEZ REBOLLEDO", 0, 1, 'C')
        self.set_xy(20, y_pos + 7); self.set_font('Arial', '', 8)
        self.cell(70, 5, "Gerente General / Rep. Legal", 0, 1, 'C')
        self.line(120, y_pos, 190, y_pos)
        self.set_xy(120, y_pos + 2); self.set_font('Arial', 'B', 9)
        self.cell(70, 5, "ALAN GARCIA VIDAL", 0, 1, 'C')
        self.set_xy(120, y_pos + 7); self.set_font('Arial', '', 8)
        self.cell(70, 5, "Ingeniero en Prevención de Riesgos", 0, 1, 'C')
        self.ln(15); self.set_font('Arial', 'I', 7); self.set_text_color(128)
        self.multi_cell(0, 4, "Este documento es parte integrante del SGSST. Confidencial.", 0, 'C')

    def draw_detailed_stats_table(self, data_list):
        self.set_font('Arial', 'B', 9); self.set_fill_color(230, 230, 230); self.set_text_color(0, 0, 0)
        self.cell(100, 8, "INDICADOR (DS 67 / DS 40)", 1, 0, 'L', 1)
        self.cell(45, 8, "MES ACTUAL", 1, 0, 'C', 1)
        self.cell(45, 8, "ACUMULADO ANUAL", 1, 1, 'C', 1)
        self.set_font('Arial', '', 9)
        for label, val_m, val_a, is_bold in data_list:
            if is_bold: self.set_font('Arial', 'B', 9)
            else: self.set_font('Arial', '', 9)
            self.ln()
            self.cell(100, 7, f" {label}", 1, 0, 'L'); self.cell(45, 7, str(val_m), 1, 0, 'C'); self.cell(45, 7, str(val_a), 1, 1, 'C')

def generar_pdf_asistencia(id_cap):
    conn = sqlite3.connect('sgsst_master.db')
    cap = conn.execute("SELECT * FROM capacitaciones WHERE id=?", (id_cap,)).fetchone()
    asistentes = conn.execute("SELECT p.nombre, p.rut, p.cargo, a.hora_firma, a.firma_digital_hash FROM asistencia_capacitacion a JOIN personal p ON a.rut_trabajador = p.rut WHERE a.id_capacitacion = ?", (id_cap,)).fetchall()
    conn.close()
    buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=landscape(letter)); elements = []; styles = getSampleStyleSheet()
    elements.append(Paragraph("<b>REGISTRO DE CAPACITACIÓN Y ENTRENAMIENTO</b>", styles['Title']))
    elements.append(Paragraph("Decreto Supremo N°40, Art. 21 - Gestión DS 44", styles['Normal'])); elements.append(Spacer(1, 15))
    data_header = [["TEMA:", cap[1], "FECHA:", cap[3]], ["EXPOSITOR:", cap[2], "DURACIÓN:", cap[4]]]
    t_head = Table(data_header, colWidths=[80, 400, 80, 100])
    t_head.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (0,-1), colors.lightgrey)]))
    elements.append(t_head); elements.append(Spacer(1, 20))
    headers = ['NOMBRE TRABAJADOR', 'RUT', 'CARGO', 'HORA', 'FIRMA DIGITAL (HASH)']; table_data = [headers]
    for asis in asistentes:
        hash_visual = f"VALIDADO: {asis[4][:15]}..."
        row = [asis[0], asis[1], asis[2], asis[3][:16], hash_visual]
        table_data.append(row)
    t_asist = Table(table_data, colWidths=[200, 80, 120, 100, 200])
    t_asist.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.navy), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTSIZE', (0,0), (-1,-1), 9)]))
    elements.append(t_asist); elements.append(Spacer(1, 30))
    elements.append(Paragraph("El instructor certifica que los trabajadores individualizados recibieron la instrucción descrita.", styles['Normal']))
    doc.build(elements); buffer.seek(0)
    return buffer

# ==============================================================================
# 3. INTERFAZ PROFESIONAL (FRONTEND)
# ==============================================================================
st.set_page_config(page_title="ERP SGSST - G&D", layout="wide")
init_erp_db()

with st.sidebar:
    st.markdown("## MADERAS G&D")
    st.markdown("### ERP GESTIÓN INTEGRAL")
    st.info(f"Usuario: Alan García\nRol: Administrador APR")
    st.divider()
    menu = st.radio("MÓDULOS ACTIVOS:", 
             ["📊 Dashboard BI", "👥 Nómina (Base Excel)", "🎓 Gestión Capacitación", 
              "📄 Generador IRL", "⚠️ Matriz IPER"])

# --- 1. DASHBOARD BI (INTEGRADO) ---
if menu == "📊 Dashboard BI":
    if 'df_main' not in st.session_state: st.session_state['df_main'] = load_data()
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ Config. BI")
    factor_hht = st.sidebar.number_input("Horas Base (HHT)", value=210)
    if 'factor_hht_cache' not in st.session_state or st.session_state['factor_hht_cache'] != factor_hht:
        st.session_state['df_main'] = procesar_datos(st.session_state['df_main'], factor_hht)
        st.session_state['factor_hht_cache'] = factor_hht
    years_present = st.session_state['df_main']['Año'].unique()
    c_y1, c_y2 = st.sidebar.columns(2)
    new_year_input = c_y1.number_input("Nuevo Año", 2000, 2050, 2024)
    if c_y2.button("Crear Año"):
        if new_year_input not in years_present:
            df_new = get_structure_for_year(new_year_input)
            st.session_state['df_main'] = pd.concat([st.session_state['df_main'], df_new], ignore_index=True)
            save_data(st.session_state['df_main'], factor_hht); st.rerun()
    def to_excel(df):
        output = BytesIO(); 
        with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name='SST_Data')
        return output.getvalue()
    excel_data = to_excel(st.session_state['df_main'])
    st.sidebar.download_button("📊 Excel Base", data=excel_data, file_name="Base_SST_Completa.xlsx")
    meta_ta = st.sidebar.slider("Meta Tasa Acc.", 0.0, 8.0, 3.0)
    meta_gestion = st.sidebar.slider("Meta Gestión", 50, 100, 90)
    metas = {'meta_ta': meta_ta, 'meta_gestion': meta_gestion}

    df = st.session_state['df_main']
    tab_dash, tab_editor = st.tabs(["📊 DASHBOARD EJECUTIVO", "📝 EDITOR DE DATOS"])
    years = sorted(df['Año'].unique(), reverse=True)
    if not years: years = [2026]

    with tab_dash:
        c1, c2 = st.columns([1, 4])
        with c1:
            if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=160)
        with c2:
            st.title("SOCIEDAD MADERERA GALVEZ Y DI GENOVA LTDA")
            st.markdown(f"### 🛡️ CONTROL DE MANDO EJECUTIVO (Base HHT: {factor_hht})")
        col_y, col_m = st.columns(2)
        sel_year = col_y.selectbox("Año Fiscal", years)
        df_year = df[df['Año'] == sel_year].copy()
        df_year['Mes_Idx'] = df_year['Mes'].apply(lambda x: MESES_ORDEN.index(x) if x in MESES_ORDEN else 99)
        df_year = df_year.sort_values('Mes_Idx')
        months_avail = df_year['Mes'].tolist()
        if not months_avail: st.warning("Sin datos."); st.stop()
        sel_month = col_m.selectbox("Mes de Corte", months_avail, index=len(months_avail)-1 if months_avail else 0)
        
        row_mes = df_year[df_year['Mes'] == sel_month].iloc[0]
        idx_corte = MESES_ORDEN.index(sel_month)
        df_acum = df_year[df_year['Mes_Idx'] <= idx_corte]
        
        sum_acc = df_acum['Accidentes CTP'].sum(); sum_fatales = df_acum['Accidentes Fatales'].sum()
        sum_ep = df_acum['Enf. Profesionales'].sum(); sum_dias_acc = df_acum['Días Perdidos'].sum()
        sum_dias_ep = df_acum['Días Perdidos EP'].sum(); sum_pensionados = df_acum['Pensionados'].sum()
        sum_indemnizados = df_acum['Indemnizados'].sum(); sum_hht = df_acum['HHT'].sum()
        df_masa_ok = df_acum[df_acum['Masa Laboral'] > 0]
        avg_masa = df_masa_ok['Masa Laboral'].mean() if not df_masa_ok.empty else 0
        ta_acum = (sum_acc / avg_masa * 100) if avg_masa > 0 else 0
        ts_acum = (sum_dias_acc / avg_masa * 100) if avg_masa > 0 else 0 
        if_acum = (sum_acc * 1000000 / sum_hht) if sum_hht > 0 else 0
        sum_dias_cargo = df_acum['Días Cargo'].sum()
        ig_acum = ((sum_dias_acc + sum_dias_cargo) * 1000000 / sum_hht) if sum_hht > 0 else 0
        def safe_div(a, b): return (a/b*100) if b > 0 else 0
        p_insp = safe_div(row_mes['Insp. Ejecutadas'], row_mes['Insp. Programadas'])
        p_cap = safe_div(row_mes['Cap. Ejecutadas'], row_mes['Cap. Programadas'])
        p_medidas = safe_div(row_mes['Medidas Cerradas'], row_mes['Medidas Abiertas']) if row_mes['Medidas Abiertas']>0 else 100
        p_salud = safe_div(row_mes['Vig. Salud Vigente'], row_mes['Expuestos Silice/Ruido']) if row_mes['Expuestos Silice/Ruido']>0 else 100
        insight_text = generar_insight_automatico(row_mes, ta_acum, metas)
        st.info("💡 **ANÁLISIS INTELIGENTE DEL SISTEMA:**")
        st.markdown(f"<div style='background-color:#e3f2fd; padding:10px; border-radius:5px;'>{insight_text}</div>", unsafe_allow_html=True)
        col_g1, col_g2, col_g3, col_g4 = st.columns(4)
        def plot_gauge(value, title, max_val, threshold, inverse=False):
            colors = {'good': '#2E7D32', 'bad': '#C62828'}
            bar_color = colors['good'] if (value <= threshold if inverse else value >= threshold) else colors['bad']
            fig = go.Figure(go.Indicator(mode = "gauge+number", value = value, title = {'text': title, 'font': {'size': 14}}, gauge = {'axis': {'range': [0, max_val]}, 'bar': {'color': bar_color}}))
            fig.update_layout(height=200, margin=dict(t=30,b=10,l=20,r=20))
            return fig
        with col_g1: st.plotly_chart(plot_gauge(ta_acum, "Tasa Acc. Acum", 8, metas['meta_ta'], True), use_container_width=True)
        with col_g2: st.plotly_chart(plot_gauge(ts_acum, "Tasa Sin. Acum", 50, 10, True), use_container_width=True)
        with col_g3: st.plotly_chart(plot_gauge(if_acum, "Ind. Frec. Acum", 50, 10, True), use_container_width=True)
        with col_g4: st.markdown("<br>", unsafe_allow_html=True); st.metric("Total HHT (Año)", f"{int(sum_hht):,}".replace(",", ".")); st.caption(f"Calculado con Factor {factor_hht}")
        st.markdown("---"); st.markdown("#### 📋 LISTADO MAESTRO DE INDICADORES (DS67)")
        stats_data = {
            'Indicador': ['Nº de Accidentes CTP', 'Nº de Enfermedades Profesionales', 'Días Perdidos (Acc. Trabajo)', 'Días Perdidos (Enf. Prof.)', 'Promedio de Trabajadores', 'Nº de Accidentes Fatales', 'Nº de Pensionados', 'Nº de Indemnizados', 'Tasa Siniestralidad (Inc. Temporal)', 'Dias Cargo (Factor Inv/Muerte)', 'Tasa de Accidentabilidad', 'Tasa de Frecuencia', 'Tasa de Gravedad', 'Horas Hombre (HHT)'],
            'Mes Actual': [int(row_mes['Accidentes CTP']), int(row_mes['Enf. Profesionales']), int(row_mes['Días Perdidos']), int(row_mes['Días Perdidos EP']), f"{row_mes['Masa Laboral']:.1f}", int(row_mes['Accidentes Fatales']), int(row_mes['Pensionados']), int(row_mes['Indemnizados']), f"{row_mes['Tasa Sin.']:.2f}", int(row_mes['Días Cargo']), f"{row_mes['Tasa Acc.']:.2f}%", f"{row_mes['Indice Frec.']:.2f}", f"{row_mes['Indice Grav.']:.0f}", int(row_mes['HHT'])],
            'Acumulado Anual': [int(sum_acc), int(sum_ep), int(sum_dias_acc), int(sum_dias_ep), f"{avg_masa:.1f}", int(sum_fatales), int(sum_pensionados), int(sum_indemnizados), f"{ts_acum:.2f}", int(sum_dias_cargo), f"{ta_acum:.2f}%", f"{if_acum:.2f}", f"{ig_acum:.0f}", int(sum_hht)]
        }
        st.table(pd.DataFrame(stats_data))
        st.markdown("---")
        g1, g2, g3, g4 = st.columns(4)
        def donut(val, title, col_obj):
            color = "#66BB6A" if val >= metas['meta_gestion'] else "#EF5350"
            fig = go.Figure(go.Pie(values=[val, 100-val], hole=0.7, marker_colors=[color, '#eee'], textinfo='none'))
            fig.update_layout(height=140, margin=dict(t=0,b=0,l=0,r=0), annotations=[dict(text=f"{val:.0f}%", x=0.5, y=0.5, font_size=20, showarrow=False)])
            col_obj.markdown(f"<div style='text-align:center; font-size:13px;'>{title}</div>", unsafe_allow_html=True); col_obj.plotly_chart(fig, use_container_width=True, key=title)
        donut(p_insp, "Inspecciones", g1); donut(p_cap, "Capacitaciones", g2); donut(p_medidas, "Cierre Hallazgos", g3); donut(p_salud, "Salud Ocupacional", g4)
        st.markdown("---")
        if st.button("📄 Generar Reporte Ejecutivo PDF"):
            try:
                pdf = PDF_SST(orientation='P', format='A4'); pdf.add_page(); pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, f"PERIODO: {sel_month.upper()} {sel_year}", 0, 1, 'R')
                pdf.section_title("1. INDICADORES VISUALES (MES vs ACUMULADO)")
                y_start = pdf.get_y(); pdf.draw_kpi_circle_pair("TASA ACCIDENTABILIDAD", row_mes['Tasa Acc.'], ta_acum, 8, metas['meta_ta'], "%", 10, y_start)
                pdf.draw_kpi_circle_pair("TASA SINIESTRALIDAD", row_mes['Tasa Sin.'], ts_acum, 50, 10, "Dias", 110, y_start); y_start += 55
                pdf.draw_kpi_circle_pair("TASA FRECUENCIA", row_mes['Indice Frec.'], if_acum, 50, 10, "IF", 10, y_start); pdf.draw_kpi_circle_pair("TASA GRAVEDAD", row_mes['Indice Grav.'], ig_acum, 200, 50, "IG", 110, y_start)
                pdf.set_y(y_start + 60); pdf.section_title("2. ESTADÍSTICA DE SINIESTRALIDAD (DS 67)"); pdf.ln(2)
                table_rows = [("Nro de Accidentes CTP", int(row_mes['Accidentes CTP']), int(sum_acc), False), ("Nro de Enfermedades Profesionales", int(row_mes['Enf. Profesionales']), int(sum_ep), False), ("Dias Perdidos (Acc. Trabajo)", int(row_mes['Días Perdidos']), int(sum_dias_acc), False), ("Dias Perdidos (Enf. Profesional)", int(row_mes['Días Perdidos EP']), int(sum_dias_ep), False), ("Promedio de Trabajadores", f"{row_mes['Masa Laboral']:.1f}", f"{avg_masa:.1f}", False), ("Nro Accidentes Fatales", int(row_mes['Accidentes Fatales']), int(sum_fatales), False), ("Nro Pensionados (Invalidez)", int(row_mes['Pensionados']), int(sum_pensionados), False), ("Nro Indemnizados", int(row_mes['Indemnizados']), int(sum_indemnizados), False), ("Tasa Siniestralidad (Inc. Temporal)", f"{row_mes['Tasa Sin.']:.2f}", f"{ts_acum:.2f}", False), ("Dias Cargo (Inv. y Muerte)", int(row_mes['Días Cargo']), int(sum_dias_cargo), False), ("Tasa de Accidentabilidad (%)", f"{row_mes['Tasa Acc.']:.2f}", f"{ta_acum:.2f}", True), ("Tasa de Frecuencia", f"{row_mes['Indice Frec.']:.2f}", f"{if_acum:.2f}", True), ("Tasa de Gravedad", f"{row_mes['Indice Grav.']:.0f}", f"{ig_acum:.0f}", True), ("Horas Hombre (HHT)", int(row_mes['HHT']), int(sum_hht), False)]
                pdf.draw_detailed_stats_table(table_rows); pdf.add_page(); pdf.section_title("3. CUMPLIMIENTO PROGRAMA GESTIÓN")
                insp_txt = f"{int(row_mes['Insp. Ejecutadas'])} de {int(row_mes['Insp. Programadas'])}"; cap_txt = f"{int(row_mes['Cap. Ejecutadas'])} de {int(row_mes['Cap. Programadas'])}"
                med_txt = f"{int(row_mes['Medidas Cerradas'])} de {int(row_mes['Medidas Abiertas'])}"; salud_txt = f"{int(row_mes['Vig. Salud Vigente'])} de {int(row_mes['Expuestos Silice/Ruido'])}"
                data_gest = [("Inspecciones", p_insp, insp_txt), ("Capacitaciones", p_cap, cap_txt), ("Hallazgos", p_medidas, med_txt), ("Salud Ocup.", p_salud, salud_txt)]
                y_circles = pdf.get_y()
                for i, (label, val, txt) in enumerate(data_gest):
                    x_pos = 15 + (i * 48); color_hex = '#4CAF50' if val >= metas['meta_gestion'] else '#F44336'
                    pdf.draw_donut_chart_image(val, color_hex, x_pos, y_circles, size=30); pdf.set_text_color(0,0,0)
                    pdf.set_xy(x_pos - 5, y_circles + 32); pdf.set_font('Arial', 'B', 8); pdf.cell(40, 4, label, 0, 1, 'C')
                    pdf.set_xy(x_pos - 5, y_circles + 36); pdf.set_font('Arial', '', 7); pdf.set_text_color(100); pdf.cell(40, 4, txt, 0, 1, 'C'); pdf.set_text_color(0)
                pdf.set_y(y_circles + 45); pdf.section_title("4. OBSERVACIONES DEL EXPERTO"); pdf.set_font('Arial', '', 10); pdf.set_text_color(0,0,0)
                clean_insight = pdf.clean_text(insight_text.replace("<b>","").replace("</b>","").replace("<br>","\n").replace("⚠️","").replace("✅","").replace("🚑",""))
                obs_raw = str(row_mes['Observaciones']); 
                if obs_raw.lower() in ["nan", "none", "0", "0.0", ""]: obs_raw = "Sin observaciones registradas."
                clean_obs = pdf.clean_text(obs_raw)
                pdf.multi_cell(0, 6, f"ANALISIS SISTEMA:\n{clean_insight}\n\nCOMENTARIOS EXPERTO:\n{clean_obs}", 1, 'L')
                pdf.ln(20); pdf.footer_signatures(); out = pdf.output(dest='S').encode('latin-1')
                st.download_button("📥 Descargar Reporte Ejecutivo", out, f"Reporte_SST_{sel_month}.pdf", "application/pdf")
            except Exception as e: st.error(f"Error PDF: {e}")

    with tab_editor:
        st.subheader("📝 Carga de Datos")
        c_y, c_m = st.columns(2)
        edit_year = c_y.selectbox("Año:", years, key="ed_y")
        m_list = df[df['Año'] == edit_year]['Mes'].tolist(); m_list.sort(key=lambda x: MESES_ORDEN.index(x) if x in MESES_ORDEN else 99)
        edit_month = c_m.selectbox("Mes:", m_list, key="ed_m")
        try:
            row_idx = df.index[(df['Año'] == edit_year) & (df['Mes'] == edit_month)].tolist()[0]
            with st.form("edit_form"):
                st.info(f"Editando: **{edit_month} {edit_year}**")
                st.markdown("##### 🏭 Datos Base")
                c1, c2, c3 = st.columns(3)
                val_masa = c1.number_input("Nº Trabajadores", value=float(df.at[row_idx, 'Masa Laboral'])); val_extras = c2.number_input("Horas Extras", value=float(df.at[row_idx, 'Horas Extras'])); val_aus = c3.number_input("Horas Ausentismo", value=float(df.at[row_idx, 'Horas Ausentismo']))
                hht_prev = (val_masa * factor_hht) + val_extras - val_aus; st.caption(f"HHT Estimadas (Factor {factor_hht}): {hht_prev:,.0f}")
                st.markdown("##### 🚑 Siniestralidad")
                c6, c7, c8 = st.columns(3)
                val_acc = c6.number_input("Nº Accidentes CTP", value=float(df.at[row_idx, 'Accidentes CTP'])); val_dias = c7.number_input("Días Perdidos (Acc)", value=float(df.at[row_idx, 'Días Perdidos'])); val_fatales = c8.number_input("Nº Accidentes Fatales", value=float(df.at[row_idx, 'Accidentes Fatales']))
                c9, c10, c11 = st.columns(3)
                val_ep = c9.number_input("Nº Enf. Profesionales", value=float(df.at[row_idx, 'Enf. Profesionales'])); val_dias_ep = c10.number_input("Días Perdidos (EP)", value=float(df.at[row_idx, 'Días Perdidos EP'])); val_cargo = c11.number_input("Días Cargo (Inv/Muerte)", value=float(df.at[row_idx, 'Días Cargo']))
                c12, c13 = st.columns(2)
                val_pen = c12.number_input("Nº Pensionados", value=float(df.at[row_idx, 'Pensionados'])); val_ind = c13.number_input("Nº Indemnizados", value=float(df.at[row_idx, 'Indemnizados']))
                st.markdown("##### 📋 Gestión")
                c14, c15 = st.columns(2); val_insp_p = c14.number_input("Insp. Programadas", value=float(df.at[row_idx, 'Insp. Programadas'])); val_insp_e = c15.number_input("Insp. Ejecutadas", value=float(df.at[row_idx, 'Insp. Ejecutadas']))
                c16, c17 = st.columns(2); val_cap_p = c16.number_input("Cap. Programadas", value=float(df.at[row_idx, 'Cap. Programadas'])); val_cap_e = c17.number_input("Cap. Ejecutadas", value=float(df.at[row_idx, 'Cap. Ejecutadas']))
                c18, c19 = st.columns(2); val_med_ab = c18.number_input("Hallazgos Abiertos", value=float(df.at[row_idx, 'Medidas Abiertas'])); val_med_ce = c19.number_input("Hallazgos Cerrados", value=float(df.at[row_idx, 'Medidas Cerradas']))
                c20, c21 = st.columns(2); val_exp = c20.number_input("Expuestos (Silice/Ruido)", value=float(df.at[row_idx, 'Expuestos Silice/Ruido'])); val_vig = c21.number_input("Vigilancia Salud Vigente", value=float(df.at[row_idx, 'Vig. Salud Vigente']))
                st.markdown("##### 📝 Observaciones"); c_obs = str(df.at[row_idx, 'Observaciones']); 
                if c_obs.lower() in ["nan", "none", "0", ""]: c_obs = ""
                val_obs = st.text_area("Texto del Reporte:", value=c_obs, height=100)
                if st.form_submit_button("💾 GUARDAR DATOS"):
                    df.at[row_idx, 'Masa Laboral'] = val_masa; df.at[row_idx, 'Horas Extras'] = val_extras; df.at[row_idx, 'Horas Ausentismo'] = val_aus
                    df.at[row_idx, 'Accidentes CTP'] = val_acc; df.at[row_idx, 'Días Perdidos'] = val_dias; df.at[row_idx, 'Accidentes Fatales'] = val_fatales; df.at[row_idx, 'Días Cargo'] = val_cargo
                    df.at[row_idx, 'Enf. Profesionales'] = val_ep; df.at[row_idx, 'Días Perdidos EP'] = val_dias_ep; df.at[row_idx, 'Pensionados'] = val_pen; df.at[row_idx, 'Indemnizados'] = val_ind
                    df.at[row_idx, 'Insp. Programadas'] = val_insp_p; df.at[row_idx, 'Insp. Ejecutadas'] = val_insp_e; df.at[row_idx, 'Cap. Programadas'] = val_cap_p; df.at[row_idx, 'Cap. Ejecutadas'] = val_cap_e
                    df.at[row_idx, 'Medidas Abiertas'] = val_med_ab; df.at[row_idx, 'Medidas Cerradas'] = val_med_ce; df.at[row_idx, 'Expuestos Silice/Ruido'] = val_exp; df.at[row_idx, 'Vig. Salud Vigente'] = val_vig; df.at[row_idx, 'Observaciones'] = val_obs
                    st.session_state['df_main'] = save_data(df, factor_hht); st.success("Guardado."); st.rerun()
        except Exception as e: st.error(f"Error al cargar registro: {e}")

# --- 2. GESTIÓN NÓMINA ---
elif menu == "👥 Nómina (Base Excel)":
    st.title("Base de Datos Maestra de Personal")
    st.markdown("Datos cargados desde 'listado de trabajadores.xlsx'.")
    conn = sqlite3.connect('sgsst_master.db')
    uploaded_file = st.file_uploader("📂 Actualizar Nómina (Subir Excel Completo)", type=['xlsx', 'csv'])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'): df_new = pd.read_csv(uploaded_file, header=2)
            else: df_new = pd.read_excel(uploaded_file, header=2)
            df_new.columns = df_new.columns.str.strip().str.upper()
            columnas_necesarias = ['RUT', 'NOMBRE', 'CARGO', 'LUGAR DE TRABAJO']
            if all(col in df_new.columns for col in columnas_necesarias):
                c = conn.cursor(); count = 0
                for index, row in df_new.iterrows():
                    rut = str(row['RUT']).strip(); nombre = str(row['NOMBRE']).strip(); cargo = str(row['CARGO']).strip(); lugar = str(row.get('LUGAR DE TRABAJO', 'FAENA')).strip()
                    try: f_contrato = pd.to_datetime(row['F. CONTRATO']).date()
                    except: f_contrato = date.today()
                    if len(rut) > 5 and nombre != "nan":
                        c.execute("INSERT OR REPLACE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (rut, nombre, cargo, lugar, f_contrato, "ACTIVO"))
                        count += 1
                conn.commit(); st.success(f"✅ Éxito: {count} trabajadores procesados."); st.rerun()
            else: st.error(f"Formato incorrecto. Columnas detectadas: {list(df_new.columns)}")
        except Exception as e: st.error(f"Error técnico: {e}")
    df = pd.read_sql("SELECT * FROM personal", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()

# --- 3. MÓDULO DE CAPACITACIÓN ---
elif menu == "🎓 Gestión Capacitación":
    st.title("Plan de Capacitación y Entrenamiento"); tab_prog, tab_firma, tab_hist = st.tabs(["📅 Programar / Crear", "✍️ Firma Digital", "🗂️ Historial y PDF"]); conn = sqlite3.connect('sgsst_master.db')
    with tab_prog:
        with st.form("new_cap"):
            col1, col2 = st.columns(2); tema = col1.text_input("Tema de Capacitación", placeholder="Ej: Uso de Extintores"); expositor = col2.text_input("Relator / Expositor", value="Alan García (APR)")
            fecha = col1.date_input("Fecha Ejecución"); duracion = col2.text_input("Duración", "1 Hora")
            if st.form_submit_button("Guardar Actividad"):
                c = conn.cursor(); c.execute("INSERT INTO capacitaciones (tema, expositor, fecha, duracion, estado) VALUES (?,?,?,?,?)", (tema, expositor, fecha, duracion, "PROGRAMADA")); conn.commit(); st.success("Capacitación creada correctamente."); st.rerun()
    with tab_firma:
        caps_activas = pd.read_sql("SELECT id, tema FROM capacitaciones WHERE estado='PROGRAMADA'", conn)
        if not caps_activas.empty:
            sel_cap = st.selectbox("Seleccione Capacitación:", caps_activas['tema']); id_cap_sel = caps_activas[caps_activas['tema'] == sel_cap]['id'].values[0]
            trabajadores = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn); asistentes = st.multiselect("Seleccione Asistentes:", trabajadores['nombre'])
            if asistentes:
                st.write("### Panel de Firma Digital"); st.info("Se generará un Hash Criptográfico único por trabajador.")
                if st.button("✍️ FIRMAR ASISTENCIA DIGITALMENTE"):
                    c = conn.cursor()
                    for nombre in asistentes:
                        rut_t = trabajadores[trabajadores['nombre'] == nombre]['rut'].values[0]; raw_string = f"{rut_t}{datetime.now()}{id_cap_sel}"; hash_firma = hashlib.sha256(raw_string.encode()).hexdigest()
                        c.execute("INSERT INTO asistencia_capacitacion (id_capacitacion, rut_trabajador, hora_firma, firma_digital_hash) VALUES (?,?,?,?)", (id_cap_sel, rut_t, datetime.now(), hash_firma))
                    c.execute("UPDATE capacitaciones SET estado='EJECUTADA' WHERE id=?", (id_cap_sel,)); conn.commit(); st.success(f"Se registraron {len(asistentes)} firmas."); st.rerun()
        else: st.warning("No hay capacitaciones pendientes.")
    with tab_hist:
        historial = pd.read_sql("SELECT * FROM capacitaciones WHERE estado='EJECUTADA'", conn)
        if not historial.empty:
            st.dataframe(historial, use_container_width=True); sel_pdf = st.selectbox("Seleccione para descargar Acta:", historial['tema']); id_pdf = historial[historial['tema'] == sel_pdf]['id'].values[0]
            if st.button("📥 Descargar Registro de Asistencia (PDF)"):
                pdf_bytes = generar_pdf_asistencia(id_pdf); st.download_button(label="Guardar PDF", data=pdf_bytes, file_name=f"Registro_{sel_pdf}.pdf", mime="application/pdf")
        else: st.info("Aún no se han ejecutado capacitaciones.")
    conn.close()

# --- 4. GENERADOR IRL ---
elif menu == "📄 Generador IRL":
    st.title("Generador de IRL Automático"); conn = sqlite3.connect('sgsst_master.db'); users = pd.read_sql("SELECT nombre, cargo FROM personal", conn)
    sel = st.selectbox("Trabajador:", users['nombre']); st.write(f"Generando documento para cargo: **{users[users['nombre']==sel]['cargo'].values[0]}**"); st.button("Generar IRL (Simulación)"); conn.close()

# --- 5. MATRIZ IPER ---
elif menu == "⚠️ Matriz IPER":
    st.title("Matriz de Riesgos"); conn = sqlite3.connect('sgsst_master.db'); df_iper = pd.read_sql("SELECT * FROM matriz_iper", conn); st.dataframe(df_iper); conn.close()
