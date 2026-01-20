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
import base64
from PIL import Image as PILImage
import matplotlib
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from fpdf import FPDF
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from streamlit_drawable_canvas import st_canvas

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CAPA DE DATOS (SQL RELACIONAL) - V11 (Final)
# ==============================================================================
def init_erp_db():
    conn = sqlite3.connect('sgsst_v11_final.db')
    c = conn.cursor()
    
    # --- USUARIOS ---
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        pass_hash = hashlib.sha256("1234".encode()).hexdigest()
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", pass_hash, "ADMINISTRADOR"))
        conn.commit()

    # --- PERSONAL ---
    c.execute('''CREATE TABLE IF NOT EXISTS personal (
                    rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, 
                    centro_costo TEXT, fecha_contrato DATE, estado TEXT)''')
    
    # --- CAPACITACIONES ---
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, responsable TEXT,
                    cargo_responsable TEXT, lugar TEXT, hora_inicio TEXT,
                    tipo_charla TEXT, tema TEXT, estado TEXT,
                    firma_instructor_b64 TEXT)''')
    
    # --- ASISTENCIA ---
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    id_capacitacion INTEGER, 
                    rut_trabajador TEXT, 
                    hora_firma DATETIME, 
                    firma_digital_hash TEXT,
                    firma_imagen_b64 TEXT, 
                    estado TEXT)''')

    # --- MATRIZ IPER ---
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, cargo_asociado TEXT, proceso TEXT, 
                    peligro TEXT, riesgo TEXT, consecuencia TEXT, medida_control TEXT, criticidad TEXT)''')

    # --- INSPECCIONES ---
    c.execute('''CREATE TABLE IF NOT EXISTS inspecciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, rut_responsable TEXT, fecha DATETIME, 
                    tipo_inspeccion TEXT, hallazgos TEXT, estado TEXT)''')

    # --- CARGA MASIVA DE TRABAJADORES ---
    c.execute("SELECT count(*) FROM personal")
    if c.fetchone()[0] < 5: 
        staff_completo = [
            ("16.781.002-0", "ALAN FABIAN GARCIA VIDAL", "APR", "OFICINA", "2025-10-21", "ACTIVO"),
            ("10.518.096-9", "OSCAR EDUARDO TRIVIÑO SALAZAR", "OPERADOR DE MAQUINARIA FORESTAL", "FAENA", "2024-01-01", "ACTIVO"),
            ("12.128.228-2", "LEONEL MOISES MUÑOZ HERNANDEZ", "OPERADOR DE MAQUINARIA FORESTAL", "FAENA", "2023-01-01", "ACTIVO"),
            ("13.376.126-8", "VICTOR DANIEL ROMERO MUÑOZ", "OPERADOR DE MAQUINARIA FORESTAL", "FAENA", "2023-01-01", "ACTIVO"),
            ("17.864.179-4", "HAIMER YONATTAN JIMENEZ SANDOVAL", "OPERADOR DE MAQUINARIA FORESTAL", "FAENA", "2023-01-01", "ACTIVO"),
            ("15.895.613-6", "RAUL OMAR MATUS LIZAMA", "OPERADOR DE MAQUINARIA FORESTAL", "FAENA", "2023-01-01", "ACTIVO"),
            ("18.903.980-8", "LUCIO HERNAN BUSTAMANTE ANDRADE", "MECANICO LIDER", "TALLER", "2023-01-01", "ACTIVO"),
            ("21.794.402-3", "ANGELO ISAAC GARRIDO RIFFO", "AYUDANTE DE MECANICO", "TALLER", "2023-01-01", "ACTIVO"),
            ("11.537.488-5", "JUAN CARLOS TORRES MALDONADO", "OPERADOR DE MAQUINARIA FORESTAL", "FAENA", "2023-01-01", "ACTIVO"),
            ("14.040.057-2", "JESUS ENRIQUE ABURTO MILANCA", "AYUDANTE DE ASERRADERO", "ASERRADERO", "2023-01-01", "ACTIVO"),
            ("13.519.325-9", "CARLOS ALBERTO PAILLALEF GANGA", "OPERADOR DE MAQUINARIA FORESTAL", "FAENA", "2023-01-01", "ACTIVO"),
            ("11.138.634-K", "OSCAR ORLANDO GONZALES CARRILLO", "MOTOSIERRISTA", "FAENA", "2023-01-01", "ACTIVO"),
            ("12.345.678-1", "HECTOR NIBALDO GUZMAN", "OPERADOR FORESTAL", "FAENA", "2023-01-01", "ACTIVO"),
            ("15.282.021-6", "ALBERTO LOAIZA MANSILLA", "JEFE DE PATIO", "ASERRADERO", "2023-05-10", "ACTIVO"),
            ("9.914.127-1", "JOSE MIGUEL OPORTO GODOY", "OPERADOR ASERRADERO", "ASERRADERO", "2022-03-15", "ACTIVO"),
            ("23.076.765-3", "GIVENS ABURTO CAMINO", "AYUDANTE", "ASERRADERO", "2025-02-01", "ACTIVO"),
            ("13.736.331-3", "MAURICIO LOPEZ GUTIÉRREZ", "ADMINISTRATIVO", "OFICINA", "2025-06-06", "ACTIVO")
        ]
        c.executemany("INSERT OR IGNORE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", staff_completo)

    c.execute("SELECT count(*) FROM matriz_iper")
    if c.fetchone()[0] == 0:
        iper_data = [
            ("OPERADOR DE MAQUINARIA FORESTAL", "Cosecha Mecanizada", "Pendiente Abrupta", "Volcamiento", "Muerte/Invalidez", "Cabina Certificada ROPS/FOPS, Cinturón", "CRITICO"),
            ("OPERADOR ASERRADERO", "Corte Principal", "Sierra en movimiento", "Corte/Amputación", "Lesión Grave", "Guardas Fijas y Móviles", "ALTO"),
            ("MECANICO LIDER", "Mantención", "Fluidos a presión", "Proyección", "Quemadura/Inyección", "Despresurización previa", "MEDIO")
        ]
        c.executemany("INSERT INTO matriz_iper (cargo_asociado, proceso, peligro, riesgo, consecuencia, medida_control, criticidad) VALUES (?,?,?,?,?,?,?)", iper_data)

    conn.commit()
    conn.close()

# ==============================================================================
# 2. FUNCIONES DE SOPORTE
# ==============================================================================
CSV_FILE = "base_datos_galvez_v26.csv"
LOGO_FILE = "logo_empresa_persistente.png"
MESES_ORDEN = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
COLOR_PRIMARY = (183, 28, 28)
COLOR_SECONDARY = (50, 50, 50)

def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_user(username, password):
    conn = sqlite3.connect('sgsst_v11_final.db')
    c = conn.cursor()
    c.execute("SELECT rol FROM usuarios WHERE username=? AND password=?", (username, hash_pass(password)))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

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
        if col not in cols_exclude: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
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

def generar_pdf_asistencia_rggd02(id_cap):
    conn = sqlite3.connect('sgsst_v11_final.db')
    try:
        cap = conn.execute("SELECT * FROM capacitaciones WHERE id=?", (id_cap,)).fetchone()
        if cap is None:
            return None
            
        asistentes = conn.execute("""
            SELECT p.nombre, p.rut, p.cargo, a.firma_digital_hash, a.firma_imagen_b64 
            FROM asistencia_capacitacion a
            JOIN personal p ON a.rut_trabajador = p.rut
            WHERE a.id_capacitacion = ? AND a.estado = 'FIRMADO'
        """, (id_cap,)).fetchall()
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=15, bottomMargin=15, leftMargin=20, rightMargin=20)
        elements = []
        styles = getSampleStyleSheet()
        style_center = ParagraphStyle(name='Center', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10)
        style_title = ParagraphStyle(name='Title', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, fontName='Helvetica-Bold')
        style_small = ParagraphStyle(name='Small', parent=styles['Normal'], fontSize=8)
        style_cell_header = ParagraphStyle(name='CellHeader', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8, textColor=colors.white, fontName='Helvetica-Bold')

        G_BLUE = colors.navy
        G_WHITE = colors.white

        logo_text = Paragraph("<b>MADERAS G&D</b>", style_title)
        center_text = Paragraph("SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA<br/>SISTEMA DE GESTION<br/>SALUD Y SEGURIDAD OCUPACIONAL", style_center)
        
        # --- FIX: Convertir a STRING ---
        f_fecha = str(datetime.now().strftime('%d/%m/%Y'))
        
        control_data = [["REGISTRO DE CAPACITACIÓN"], ["CODIGO: RG-GD-02"], ["VERSION: 01"], [f"FECHA: {f_fecha}"], ["PAGINA: 1"]]
        t_control = Table(control_data, colWidths=[130], rowHeights=[12,12,12,12,12])
        t_control.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('FONTSIZE', (0,0), (-1,-1), 7), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('BACKGROUND', (0,0), (0,0), G_BLUE), ('TEXTCOLOR', (0,0), (0,0), G_WHITE), ('FONTNAME', (0,0), (0,0), 'Helvetica-Bold')]))
        data_header = [[logo_text, center_text, t_control]]
        t_head = Table(data_header, colWidths=[100, 250, 140])
        t_head.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        elements.append(t_head); elements.append(Spacer(1, 10))

        # --- FIX: Convertir a STRING para evitar el error int() argument ... ---
        def safe_str(val):
            return str(val) if val is not None else ""

        c_tipo = safe_str(cap[6])
        c_resp = safe_str(cap[2])
        c_lug = safe_str(cap[4])
        c_fec = safe_str(cap[1])
        c_carg = safe_str(cap[3])
        c_tema = safe_str(cap[7])

        h_act = Paragraph("ACTIVIDAD", style_cell_header); h_rel = Paragraph("RELATOR", style_cell_header); h_lug = Paragraph("LUGAR", style_cell_header); h_fec = Paragraph("FECHA", style_cell_header)
        d_act = Paragraph(c_tipo, style_center); d_rel = Paragraph(c_resp, style_center); d_lug = Paragraph(c_lug, style_center); d_fec = Paragraph(c_fec, style_center)
        t_row1 = Table([[h_act, h_rel, h_lug, h_fec], [d_act, d_rel, d_lug, d_fec]], colWidths=[180, 130, 120, 60])
        t_row1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), G_BLUE), ('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elements.append(t_row1)
        t_row2 = Table([[f"CARGO: {c_carg}", "DURACIÓN: 15 min"]], colWidths=[310, 180])
        t_row2.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('FONTSIZE', (0,0), (-1,-1), 8), ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold')]))
        elements.append(t_row2); elements.append(Spacer(1, 5))

        t_temario_title = Table([[Paragraph("TEMARIO / CONTENIDOS", style_cell_header)]], colWidths=[490])
        t_temario_title.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), G_BLUE), ('ALIGN', (0,0), (-1,-1), 'LEFT')]))
        elements.append(t_temario_title)
        t_temario_body = Table([[Paragraph(c_tema, style_small)]], colWidths=[490], rowHeights=[60])
        t_temario_body.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
        elements.append(t_temario_body); elements.append(Spacer(1, 10))

        header_asis = [Paragraph("NOMBRE", style_cell_header), Paragraph("RUT", style_cell_header), Paragraph("CARGO", style_cell_header), Paragraph("FIRMA", style_cell_header)]
        data_asis = [header_asis]
        for idx, (nom, rut, car, firma_hash, firma_b64) in enumerate(asistentes, 1):
            row = [Paragraph(safe_str(nom), style_center), Paragraph(safe_str(rut), style_center), Paragraph(safe_str(car), style_center)]
            if firma_b64:
                try:
                    img_bytes = base64.b64decode(firma_b64); img_stream = io.BytesIO(img_bytes); img_rl = Image(img_stream, width=60, height=20); row.append(img_rl)
                except: row.append("Firma Digital")
            else: row.append("Validado")
            data_asis.append(row)
        
        t_asis = Table(data_asis, colWidths=[180, 70, 120, 120])
        t_asis.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), G_BLUE), ('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        elements.append(t_asis); elements.append(Spacer(1, 15))

        img_instructor = Paragraph("", style_center)
        if cap[9]: 
             try: img_bytes_inst = base64.b64decode(cap[9]); img_stream_inst = io.BytesIO(img_bytes_inst); img_instructor = Image(img_stream_inst, width=100, height=40)
             except: pass
        c_evidencia = [[Paragraph("EVIDENCIA FOTOGRÁFICA", style_center)], ["\n\n\n(Espacio para foto)\n\n\n"]]
        t_evi = Table(c_evidencia, colWidths=[240])
        t_evi.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (0,0), 'Helvetica-Bold')]))
        c_valid = [[Paragraph("VALIDACIÓN INSTRUCTOR", style_center)], [img_instructor], [Paragraph(f"<b>{c_resp}</b><br/>Relator/Instructor", style_center)]]
        t_val = Table(c_valid, colWidths=[240])
        t_val.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (0,0), 'Helvetica-Bold')]))
        t_footer = Table([[t_evi, Spacer(10,0), t_val]], colWidths=[240, 10, 240])
        elements.append(t_footer)
        doc.build(elements); buffer.seek(0); return buffer
    except Exception as e: st.error(f"Error técnico generando PDF: {e}"); return None
    finally: conn.close()

# ==============================================================================
# 3. INTERFAZ PROFESIONAL (FRONTEND)
# ==============================================================================
st.set_page_config(page_title="ERP SGSST - G&D", layout="wide")
init_erp_db()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False; st.session_state['user_role'] = None; st.session_state['username'] = None
if not st.session_state['logged_in']:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("<h1 style='text-align: center;'>🔐 Acceso Corporativo</h1>", unsafe_allow_html=True); st.info("Sistema de Gestión SST - Maderas G&D"); user_input = st.text_input("Usuario"); pass_input = st.text_input("Contraseña", type="password")
        if st.button("Iniciar Sesión", use_container_width=True):
            role = login_user(user_input, pass_input)
            if role: st.session_state['logged_in'] = True; st.session_state['user_role'] = role; st.session_state['username'] = user_input; st.rerun()
            else: st.error("Credenciales incorrectas")
    st.markdown("---"); st.caption("Admin Default: admin / 1234"); st.stop()

with st.sidebar:
    st.markdown("## MADERAS G&D"); st.markdown("### ERP GESTIÓN INTEGRAL"); st.success(f"Bienvenido: {st.session_state['username']}\nRol: {st.session_state['user_role']}"); 
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()
    st.divider(); opciones_menu = ["📊 Dashboard BI", "👥 Nómina & Personal", "📱 App Móvil", "🎓 Gestión Capacitación", "📄 Generador IRL", "⚠️ Matriz IPER"]; 
    if st.session_state['user_role'] == "ADMINISTRADOR": opciones_menu.append("🔐 Gestión Usuarios")
    menu = st.radio("MÓDULOS ACTIVOS:", opciones_menu)

if menu == "📊 Dashboard BI":
    if 'df_main' not in st.session_state: st.session_state['df_main'] = load_data()
    st.sidebar.markdown("---"); st.sidebar.markdown("### ⚙️ Config. BI"); factor_hht = st.sidebar.number_input("Horas Base (HHT)", value=210)
    if 'factor_hht_cache' not in st.session_state or st.session_state['factor_hht_cache'] != factor_hht: st.session_state['df_main'] = procesar_datos(st.session_state['df_main'], factor_hht); st.session_state['factor_hht_cache'] = factor_hht
    years_present = st.session_state['df_main']['Año'].unique(); c_y1, c_y2 = st.sidebar.columns(2); new_year_input = c_y1.number_input("Nuevo Año", 2000, 2050, 2024)
    if c_y2.button("Crear Año"):
        if new_year_input not in years_present: df_new = get_structure_for_year(new_year_input); st.session_state['df_main'] = pd.concat([st.session_state['df_main'], df_new], ignore_index=True); save_data(st.session_state['df_main'], factor_hht); st.rerun()
    def to_excel(df):
        output = BytesIO(); 
        with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name='SST_Data')
        return output.getvalue()
    excel_data = to_excel(st.session_state['df_main']); st.sidebar.download_button("📊 Excel Base", data=excel_data, file_name="Base_SST_Completa.xlsx"); meta_ta = st.sidebar.slider("Meta Tasa Acc.", 0.0, 8.0, 3.0); meta_gestion = st.sidebar.slider("Meta Gestión", 50, 100, 90); metas = {'meta_ta': meta_ta, 'meta_gestion': meta_gestion}; df = st.session_state['df_main']; tab_dash, tab_editor = st.tabs(["📊 DASHBOARD EJECUTIVO", "📝 EDITOR DE DATOS"]); years = sorted(df['Año'].unique(), reverse=True);  
    if not years: years = [2026]
    with tab_dash:
        c1, c2 = st.columns([1, 4])
        with c1: 
            if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, width=160)
        with c2: st.title("SOCIEDAD MADERERA GALVEZ Y DI GENOVA LTDA"); st.markdown(f"### 🛡️ CONTROL DE MANDO EJECUTIVO (Base HHT: {factor_hht})")
        col_y, col_m = st.columns(2); sel_year = col_y.selectbox("Año Fiscal", years); df_year = df[df['Año'] == sel_year].copy(); df_year['Mes_Idx'] = df_year['Mes'].apply(lambda x: MESES_ORDEN.index(x) if x in MESES_ORDEN else 99); df_year = df_year.sort_values('Mes_Idx'); months_avail = df_year['Mes'].tolist()
        if not months_avail: st.warning("Sin datos."); st.stop()
        sel_month = col_m.selectbox("Mes de Corte", months_avail, index=len(months_avail)-1 if months_avail else 0); row_mes = df_year[df_year['Mes'] == sel_month].iloc[0]; idx_corte = MESES_ORDEN.index(sel_month); df_acum = df_year[df_year['Mes_Idx'] <= idx_corte]; sum_acc = df_acum['Accidentes CTP'].sum(); sum_fatales = df_acum['Accidentes Fatales'].sum(); sum_ep = df_acum['Enf. Profesionales'].sum(); sum_dias_acc = df_acum['Días Perdidos'].sum(); sum_dias_ep = df_acum['Días Perdidos EP'].sum(); sum_pensionados = df_acum['Pensionados'].sum(); sum_indemnizados = df_acum['Indemnizados'].sum(); sum_hht = df_acum['HHT'].sum(); df_masa_ok = df_acum[df_acum['Masa Laboral'] > 0]; avg_masa = df_masa_ok['Masa Laboral'].mean() if not df_masa_ok.empty else 0; ta_acum = (sum_acc / avg_masa * 100) if avg_masa > 0 else 0; ts_acum = (sum_dias_acc / avg_masa * 100) if avg_masa > 0 else 0; if_acum = (sum_acc * 1000000 / sum_hht) if sum_hht > 0 else 0; sum_dias_cargo = df_acum['Días Cargo'].sum(); ig_acum = ((sum_dias_acc + sum_dias_cargo) * 1000000 / sum_hht) if sum_hht > 0 else 0
        def safe_div(a, b): return (a/b*100) if b > 0 else 0
        p_insp = safe_div(row_mes['Insp. Ejecutadas'], row_mes['Insp. Programadas']); p_cap = safe_div(row_mes['Cap. Ejecutadas'], row_mes['Cap. Programadas']); p_medidas = safe_div(row_mes['Medidas Cerradas'], row_mes['Medidas Abiertas']) if row_mes['Medidas Abiertas']>0 else 100; p_salud = safe_div(row_mes['Vig. Salud Vigente'], row_mes['Expuestos Silice/Ruido']) if row_mes['Expuestos Silice/Ruido']>0 else 100; insight_text = generar_insight_automatico(row_mes, ta_acum, metas); st.info("💡 **ANÁLISIS INTELIGENTE DEL SISTEMA:**"); st.markdown(f"<div style='background-color:#e3f2fd; padding:10px; border-radius:5px;'>{insight_text}</div>", unsafe_allow_html=True); col_g1, col_g2, col_g3, col_g4 = st.columns(4)
        def plot_gauge(value, title, max_val, threshold, inverse=False):
            colors = {'good': '#2E7D32', 'bad': '#C62828'}; bar_color = colors['good'] if (value <= threshold if inverse else value >= threshold) else colors['bad']
            fig = go.Figure(go.Indicator(mode = "gauge+number", value = value, title = {'text': title, 'font': {'size': 14}}, gauge = {'axis': {'range': [0, max_val]}, 'bar': {'color': bar_color}})); fig.update_layout(height=200, margin=dict(t=30,b=10,l=20,r=20)); return fig
        with col_g1: st.plotly_chart(plot_gauge(ta_acum, "Tasa Acc. Acum", 8, metas['meta_ta'], True), use_container_width=True)
        with col_g2: st.plotly_chart(plot_gauge(ts_acum, "Tasa Sin. Acum", 50, 10, True), use_container_width=True)
        with col_g3: st.plotly_chart(plot_gauge(if_acum, "Ind. Frec. Acum", 50, 10, True), use_container_width=True)
        with col_g4: st.markdown("<br>", unsafe_allow_html=True); st.metric("Total HHT (Año)", f"{int(sum_hht):,}".replace(",", ".")); st.caption(f"Calculado con Factor {factor_hht}")
        st.markdown("---"); st.markdown("#### 📋 LISTADO MAESTRO DE INDICADORES (DS67)"); stats_data = {'Indicador': ['Nº de Accidentes CTP', 'Nº de Enfermedades Profesionales', 'Días Perdidos (Acc. Trabajo)', 'Días Perdidos (Enf. Prof.)', 'Promedio de Trabajadores', 'Nº de Accidentes Fatales', 'Nº de Pensionados', 'Nº de Indemnizados', 'Tasa Siniestralidad (Inc. Temporal)', 'Dias Cargo (Factor Inv/Muerte)', 'Tasa de Accidentabilidad', 'Tasa de Frecuencia', 'Tasa de Gravedad', 'Horas Hombre (HHT)'], 'Mes Actual': [int(row_mes['Accidentes CTP']), int(row_mes['Enf. Profesionales']), int(row_mes['Días Perdidos']), int(row_mes['Días Perdidos EP']), f"{row_mes['Masa Laboral']:.1f}", int(row_mes['Accidentes Fatales']), int(row_mes['Pensionados']), int(row_mes['Indemnizados']), f"{row_mes['Tasa Sin.']:.2f}", int(row_mes['Días Cargo']), f"{row_mes['Tasa Acc.']:.2f}%", f"{row_mes['Indice Frec.']:.2f}", f"{row_mes['Indice Grav.']:.0f}", int(row_mes['HHT'])], 'Acumulado Anual': [int(sum_acc), int(sum_ep), int(sum_dias_acc), int(sum_dias_ep), f"{avg_masa:.1f}", int(sum_fatales), int(sum_pensionados), int(sum_indemnizados), f"{ts_acum:.2f}", int(sum_dias_cargo), f"{ta_acum:.2f}%", f"{if_acum:.2f}", f"{ig_acum:.0f}", int(sum_hht)]}; st.table(pd.DataFrame(stats_data)); st.markdown("---"); g1, g2, g3, g4 = st.columns(4)
        def donut(val, title, col_obj):
            color = "#66BB6A" if val >= metas['meta_gestion'] else "#EF5350"; fig = go.Figure(go.Pie(values=[val, 100-val], hole=0.7, marker_colors=[color, '#eee'], textinfo='none')); fig.update_layout(height=140, margin=dict(t=0,b=0,l=0,r=0), annotations=[dict(text=f"{val:.0f}%", x=0.5, y=0.5, font_size=20, showarrow=False)]); col_obj.markdown(f"<div style='text-align:center; font-size:13px;'>{title}</div>", unsafe_allow_html=True); col_obj.plotly_chart(fig, use_container_width=True, key=title)
        donut(p_insp, "Inspecciones", g1); donut(p_cap, "Capacitaciones", g2); donut(p_medidas, "Cierre Hallazgos", g3); donut(p_salud, "Salud Ocupacional", g4); st.markdown("---")
        if st.button("📄 Generar Reporte Ejecutivo PDF"):
            try:
                pdf = PDF_SST(orientation='P', format='A4'); pdf.add_page(); pdf.set_font('Arial', 'B', 12); pdf.cell(0, 10, f"PERIODO: {sel_month.upper()} {sel_year}", 0, 1, 'R'); pdf.section_title("1. INDICADORES VISUALES (MES vs ACUMULADO)"); y_start = pdf.get_y(); pdf.draw_kpi_circle_pair("TASA ACCIDENTABILIDAD", row_mes['Tasa Acc.'], ta_acum, 8, metas['meta_ta'], "%", 10, y_start); pdf.draw_kpi_circle_pair("TASA SINIESTRALIDAD", row_mes['Tasa Sin.'], ts_acum, 50, 10, "Dias", 110, y_start); y_start += 55; pdf.draw_kpi_circle_pair("TASA FRECUENCIA", row_mes['Indice Frec.'], if_acum, 50, 10, "IF", 10, y_start); pdf.draw_kpi_circle_pair("TASA GRAVEDAD", row_mes['Indice Grav.'], ig_acum, 200, 50, "IG", 110, y_start); pdf.set_y(y_start + 60); pdf.section_title("2. ESTADÍSTICA DE SINIESTRALIDAD (DS 67)"); pdf.ln(2); table_rows = [("Nro de Accidentes CTP", int(row_mes['Accidentes CTP']), int(sum_acc), False), ("Nro de Enfermedades Profesionales", int(row_mes['Enf. Profesionales']), int(sum_ep), False), ("Dias Perdidos (Acc. Trabajo)", int(row_mes['Días Perdidos']), int(sum_dias_acc), False), ("Dias Perdidos (Enf. Profesional)", int(row_mes['Días Perdidos EP']), int(sum_dias_ep), False), ("Promedio de Trabajadores", f"{row_mes['Masa Laboral']:.1f}", f"{avg_masa:.1f}", False), ("Nro Accidentes Fatales", int(row_mes['Accidentes Fatales']), int(sum_fatales), False), ("Nro Pensionados (Invalidez)", int(row_mes['Pensionados']), int(sum_pensionados), False), ("Nro Indemnizados", int(row_mes['Indemnizados']), int(sum_indemnizados), False), ("Tasa Siniestralidad (Inc. Temporal)", f"{row_mes['Tasa Sin.']:.2f}", f"{ts_acum:.2f}", False), ("Dias Cargo (Inv. y Muerte)", int(row_mes['Días Cargo']), int(sum_dias_cargo), False), ("Tasa de Accidentabilidad (%)", f"{row_mes['Tasa Acc.']:.2f}", f"{ta_acum:.2f}", True), ("Tasa de Frecuencia", f"{row_mes['Indice Frec.']:.2f}", f"{if_acum:.2f}", True), ("Tasa de Gravedad", f"{row_mes['Indice Grav.']:.0f}", f"{ig_acum:.0f}", True), ("Horas Hombre (HHT)", int(row_mes['HHT']), int(sum_hht), False)]; pdf.draw_detailed_stats_table(table_rows); pdf.add_page(); pdf.section_title("3. CUMPLIMIENTO PROGRAMA GESTIÓN"); insp_txt = f"{int(row_mes['Insp. Ejecutadas'])} de {int(row_mes['Insp. Programadas'])}"; cap_txt = f"{int(row_mes['Cap. Ejecutadas'])} de {int(row_mes['Cap. Programadas'])}"; med_txt = f"{int(row_mes['Medidas Cerradas'])} de {int(row_mes['Medidas Abiertas'])}"; salud_txt = f"{int(row_mes['Vig. Salud Vigente'])} de {int(row_mes['Expuestos Silice/Ruido'])}"; data_gest = [("Inspecciones", p_insp, insp_txt), ("Capacitaciones", p_cap, cap_txt), ("Hallazgos", p_medidas, med_txt), ("Salud Ocup.", p_salud, salud_txt)]; y_circles = pdf.get_y()
                for i, (label, val, txt) in enumerate(data_gest): x_pos = 15 + (i * 48); color_hex = '#4CAF50' if val >= metas['meta_gestion'] else '#F44336'; pdf.draw_donut_chart_image(val, color_hex, x_pos, y_circles, size=30); pdf.set_text_color(0,0,0); pdf.set_xy(x_pos - 5, y_circles + 32); pdf.set_font('Arial', 'B', 8); pdf.cell(40, 4, label, 0, 1, 'C'); pdf.set_xy(x_pos - 5, y_circles + 36); pdf.set_font('Arial', '', 7); pdf.set_text_color(100); pdf.cell(40, 4, txt, 0, 1, 'C'); pdf.set_text_color(0)
                pdf.set_y(y_circles + 45); pdf.section_title("4. OBSERVACIONES DEL EXPERTO"); pdf.set_font('Arial', '', 10); pdf.set_text_color(0,0,0); clean_insight = pdf.clean_text(insight_text.replace("<b>","").replace("</b>","").replace("<br>","\n").replace("⚠️","").replace("✅","").replace("🚑","")); obs_raw = str(row_mes['Observaciones']); 
                if obs_raw.lower() in ["nan", "none", "0", "0.0", ""]: obs_raw = "Sin observaciones registradas."
                clean_obs = pdf.clean_text(obs_raw); pdf.multi_cell(0, 6, f"ANALISIS SISTEMA:\n{clean_insight}\n\nCOMENTARIOS EXPERTO:\n{clean_obs}", 1, 'L'); pdf.ln(20); pdf.footer_signatures(); out = pdf.output(dest='S').encode('latin-1'); st.download_button("📥 Descargar Reporte Ejecutivo", out, f"Reporte_SST_{sel_month}.pdf", "application/pdf")
            except Exception as e: st.error(f"Error PDF: {e}")
    with tab_editor:
        st.subheader("📝 Carga de Datos"); c_y, c_m = st.columns(2); edit_year = c_y.selectbox("Año:", years, key="ed_y"); m_list = df[df['Año'] == edit_year]['Mes'].tolist(); m_list.sort(key=lambda x: MESES_ORDEN.index(x) if x in MESES_ORDEN else 99); edit_month = c_m.selectbox("Mes:", m_list, key="ed_m")
        try:
            row_idx = df.index[(df['Año'] == edit_year) & (df['Mes'] == edit_month)].tolist()[0]
            with st.form("edit_form"):
                st.info(f"Editando: **{edit_month} {edit_year}**"); c1, c2, c3 = st.columns(3); val_masa = c1.number_input("Nº Trabajadores", value=float(df.at[row_idx, 'Masa Laboral'])); val_extras = c2.number_input("Horas Extras", value=float(df.at[row_idx, 'Horas Extras'])); val_aus = c3.number_input("Horas Ausentismo", value=float(df.at[row_idx, 'Horas Ausentismo'])); c6, c7, c8 = st.columns(3); val_acc = c6.number_input("Nº Accidentes CTP", value=float(df.at[row_idx, 'Accidentes CTP'])); val_dias = c7.number_input("Días Perdidos (Acc)", value=float(df.at[row_idx, 'Días Perdidos'])); val_fatales = c8.number_input("Nº Accidentes Fatales", value=float(df.at[row_idx, 'Accidentes Fatales'])); c9, c10, c11 = st.columns(3); val_ep = c9.number_input("Nº Enf. Profesionales", value=float(df.at[row_idx, 'Enf. Profesionales'])); val_dias_ep = c10.number_input("Días Perdidos (EP)", value=float(df.at[row_idx, 'Días Perdidos EP'])); val_cargo = c11.number_input("Días Cargo", value=float(df.at[row_idx, 'Días Cargo'])); c12, c13 = st.columns(2); val_pen = c12.number_input("Nº Pensionados", value=float(df.at[row_idx, 'Pensionados'])); val_ind = c13.number_input("Nº Indemnizados", value=float(df.at[row_idx, 'Indemnizados'])); c14, c15 = st.columns(2); val_insp_p = c14.number_input("Insp. Programadas", value=float(df.at[row_idx, 'Insp. Programadas'])); val_insp_e = c15.number_input("Insp. Ejecutadas", value=float(df.at[row_idx, 'Insp. Ejecutadas'])); c16, c17 = st.columns(2); val_cap_p = c16.number_input("Cap. Programadas", value=float(df.at[row_idx, 'Cap. Programadas'])); val_cap_e = c17.number_input("Cap. Ejecutadas", value=float(df.at[row_idx, 'Cap. Ejecutadas'])); c18, c19 = st.columns(2); val_med_ab = c18.number_input("Hallazgos Abiertos", value=float(df.at[row_idx, 'Medidas Abiertas'])); val_med_ce = c19.number_input("Hallazgos Cerrados", value=float(df.at[row_idx, 'Medidas Cerradas'])); c20, c21 = st.columns(2); val_exp = c20.number_input("Expuestos", value=float(df.at[row_idx, 'Expuestos Silice/Ruido'])); val_vig = c21.number_input("Vigilancia Salud", value=float(df.at[row_idx, 'Vig. Salud Vigente'])); c_obs = str(df.at[row_idx, 'Observaciones']); 
                if c_obs.lower() in ["nan", "none", "0", ""]: c_obs = ""
                val_obs = st.text_area("Texto del Reporte:", value=c_obs, height=100)
                if st.form_submit_button("💾 GUARDAR DATOS"): df.at[row_idx, 'Masa Laboral'] = val_masa; df.at[row_idx, 'Horas Extras'] = val_extras; df.at[row_idx, 'Horas Ausentismo'] = val_aus; df.at[row_idx, 'Accidentes CTP'] = val_acc; df.at[row_idx, 'Días Perdidos'] = val_dias; df.at[row_idx, 'Accidentes Fatales'] = val_fatales; df.at[row_idx, 'Días Cargo'] = val_cargo; df.at[row_idx, 'Enf. Profesionales'] = val_ep; df.at[row_idx, 'Días Perdidos EP'] = val_dias_ep; df.at[row_idx, 'Pensionados'] = val_pen; df.at[row_idx, 'Indemnizados'] = val_ind; df.at[row_idx, 'Insp. Programadas'] = val_insp_p; df.at[row_idx, 'Insp. Ejecutadas'] = val_insp_e; df.at[row_idx, 'Cap. Programadas'] = val_cap_p; df.at[row_idx, 'Cap. Ejecutadas'] = val_cap_e; df.at[row_idx, 'Medidas Abiertas'] = val_med_ab; df.at[row_idx, 'Medidas Cerradas'] = val_med_ce; df.at[row_idx, 'Expuestos Silice/Ruido'] = val_exp; df.at[row_idx, 'Vig. Salud Vigente'] = val_vig; df.at[row_idx, 'Observaciones'] = val_obs; st.session_state['df_main'] = save_data(df, factor_hht); st.success("Guardado."); st.rerun()
        except Exception as e: st.error(f"Error al cargar registro: {e}")

# --- 2. GESTIÓN NÓMINA ---
elif menu == "👥 Nómina & Personal":
    st.title("Base de Datos Maestra de Personal")
    tab_lista, tab_agregar, tab_excel = st.tabs(["📋 Lista Completa", "➕ Gestión Manual", "📂 Carga Masiva"])
    conn = sqlite3.connect('sgsst_v11_final.db')
    with tab_lista:
        df = pd.read_sql("SELECT nombre, rut, cargo, centro_costo as 'Lugar', estado FROM personal", conn); st.dataframe(df, use_container_width=True, hide_index=True); st.markdown("---"); st.subheader("🗑️ Dar de Baja / Eliminar"); col_del, col_btn = st.columns([3, 1]); rut_a_borrar = col_del.selectbox("Seleccione Trabajador a Eliminar:", df['rut'] + " - " + df['nombre'])
        if col_btn.button("Eliminar Trabajador"): rut_clean = rut_a_borrar.split(" - ")[0]; c = conn.cursor(); c.execute("DELETE FROM personal WHERE rut=?", (rut_clean,)); conn.commit(); st.success(f"Trabajador {rut_clean} eliminado."); st.rerun()
    with tab_agregar:
        st.subheader("Ingresar Nuevo Trabajador")
        with st.form("add_worker_manual"):
            c1, c2 = st.columns(2); n_rut = c1.text_input("RUT (Ej: 12.345.678-9)"); n_nom = c2.text_input("Nombre Completo"); n_cargo = c1.selectbox("Cargo", ["OPERADOR", "AYUDANTE", "CHOFER", "ADMINISTRATIVO", "MECANICO"]); n_lugar = c2.selectbox("Lugar", ["ASERRADERO", "FAENA", "OFICINA", "TALLER"])
            if st.form_submit_button("Guardar en Base de Datos"):
                if n_rut and n_nom:
                    c = conn.cursor(); 
                    try: c.execute("INSERT INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (n_rut, n_nom, n_cargo, n_lugar, date.today(), "ACTIVO")); conn.commit(); st.success("Trabajador guardado exitosamente."); st.rerun()
                    except: st.error("Error: El RUT ya existe.")
                else: st.warning("Complete RUT y Nombre.")
    with tab_excel:
        col_plantilla, col_upload = st.columns([1, 2])
        with col_plantilla:
            st.info("¿Necesitas el formato?")
            def generar_plantilla_excel_detallada():
                output = io.BytesIO(); data = {'NOMBRE': ['JUAN PEREZ (EJEMPLO)', 'MARIA SOTO (EJEMPLO)'], 'RUT': ['11.222.333-K', '12.345.678-9'], 'CARGO': ['OPERADOR ASERRADERO', 'AYUDANTE'], 'LUGAR DE TRABAJO': ['ASERRADERO', 'FAENA'], 'F. CONTRATO': ['2025-01-01', '01-03-2024'], 'DIRECCION': ['CALLE 1, OSORNO', 'AVENIDA 2'], 'ESTADO CIVIL': ['SOLTERO', 'CASADA'], 'SALUD': ['FONASA', 'ISAPRE'], 'AFP': ['MODELO', 'CAPITAL'], 'CORREO': ['ejemplo@gyd.cl', ''], 'TELEFONO': ['912345678', '']}; df_template = pd.DataFrame(data)
                with pd.ExcelWriter(output, engine='openpyxl') as writer: pd.DataFrame(["GUÍA DE FORMATO OBLIGATORIO - LEA ANTES DE LLENAR - LOS DATOS COMIENZAN EN LA FILA 4"]).to_excel(writer, startrow=0, startcol=0, index=False, header=False); pd.DataFrame(["RUT: Con puntos y guion (Ej: 11.222.333-K) | FECHAS: DD-MM-AAAA o AAAA-MM-DD | LUGAR: Use solo 'ASERRADERO', 'FAENA', 'OFICINA' | NO BORRAR ENCABEZADOS DE LA FILA 3"]).to_excel(writer, startrow=1, startcol=0, index=False, header=False); df_template.to_excel(writer, startrow=2, index=False, sheet_name='Plantilla')
                return output.getvalue()
            plantilla_data = generar_plantilla_excel_detallada(); st.download_button(label="📥 Bajar Plantilla Instructiva", data=plantilla_data, file_name="plantilla_carga_nomina_v2.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        uploaded_file = st.file_uploader("📂 Actualizar Nómina (Subir Excel Completo)", type=['xlsx', 'csv'])
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'): df_new = pd.read_csv(uploaded_file, header=2)
                else: df_new = pd.read_excel(uploaded_file, header=2)
                df_new.columns = df_new.columns.str.strip().str.upper()
                if 'RUT' in df_new.columns and 'NOMBRE' in df_new.columns:
                    c = conn.cursor(); count = 0
                    for index, row in df_new.iterrows():
                        rut = str(row['RUT']).strip(); nombre = str(row['NOMBRE']).strip(); cargo = str(row.get('CARGO', 'SIN CARGO')).strip(); lugar = str(row.get('LUGAR DE TRABAJO', 'FAENA')).strip()
                        try: f_contrato = pd.to_datetime(row.get('F. CONTRATO', date.today())).date()
                        except: f_contrato = date.today()
                        if len(rut) > 5 and nombre.lower() != "nan": c.execute("INSERT OR REPLACE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (rut, nombre, cargo, lugar, f_contrato, "ACTIVO")); count += 1
                    conn.commit(); st.success(f"✅ Éxito: {count} trabajadores procesados/actualizados."); st.rerun()
                else: st.error("Error: El archivo no contiene las columnas RUT y NOMBRE en la fila 3.")
            except Exception as e: st.error(f"Error técnico: {e}")
    conn.close()

elif menu == "📱 App Móvil":
    st.title("Conexión App Móvil (Operarios)")
    st.markdown("### 📲 Panel de Registro en Terreno")
    conn = sqlite3.connect('sgsst_v11_final.db')
    tab_asist, tab_insp = st.tabs(["✍️ Firmar Asistencia", "🚨 Reportar Hallazgo"])
    with tab_asist:
        st.subheader("Firma Rápida")
        caps = pd.read_sql("SELECT id, tema FROM capacitaciones WHERE estado='PROGRAMADA'", conn)
        if not caps.empty:
            opciones_caps = [f"ID {r['id']} - {r['tema']}" for i, r in caps.iterrows()]
            sel_cap_movil = st.selectbox("Seleccione Actividad:", opciones_caps, key="movil_cap")
            id_cap_movil = int(sel_cap_movil.split(" - ")[0].replace("ID ", ""))
            
            pendientes = pd.read_sql("SELECT p.nombre, p.rut FROM asistencia_capacitacion a JOIN personal p ON a.rut_trabajador = p.rut WHERE a.id_capacitacion = ? AND a.estado = 'PENDIENTE'", conn, params=(id_cap_movil,))
            
            if not pendientes.empty:
                trabajador_firma = st.selectbox("Seleccione su Nombre:", pendientes['nombre'] + " | " + pendientes['rut'])
                rut_firmante = trabajador_firma.split(" | ")[1]
                
                st.write("Dibuje su firma abajo:")
                if 'canvas_key' not in st.session_state: st.session_state['canvas_key'] = 0
                canvas_result = st_canvas(stroke_width=2, stroke_color="#00008B", background_color="#ffffff", height=250, width=600, drawing_mode="freedraw", key=f"canvas_firma_{st.session_state['canvas_key']}")

                if st.button("CONFIRMAR FIRMA"):
                    if canvas_result.image_data is not None:
                        img = PILImage.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA'); buffered = io.BytesIO(); img.save(buffered, format="PNG"); img_str = base64.b64encode(buffered.getvalue()).decode()
                        hash_firma = hashlib.sha256(f"{rut_firmante}{datetime.now()}".encode()).hexdigest()
                        c = conn.cursor()
                        c.execute("UPDATE asistencia_capacitacion SET estado='FIRMADO', hora_firma=?, firma_digital_hash=?, firma_imagen_b64=? WHERE id_capacitacion=? AND rut_trabajador=?", (datetime.now(), hash_firma, img_str, id_cap_movil, rut_firmante))
                        conn.commit(); st.success("✅ Firma registrada correctamente en la nube."); st.session_state['canvas_key'] += 1; st.rerun()
                    else: st.warning("Por favor dibuje su firma antes de confirmar.")
            else: st.info("No hay trabajadores pendientes de firma para esta actividad.")
        else: st.warning("No hay capacitaciones programadas.")
    with tab_insp:
        st.subheader("Inspección de Seguridad")
        with st.form("form_hallazgo"):
            resp = st.text_input("Responsable (RUT):"); tipo = st.selectbox("Tipo:", ["Condición Insegura", "Acto Inseguro", "Incidente"]); desc = st.text_area("Descripción del Hallazgo:")
            if st.form_submit_button("ENVIAR REPORTE"):
                c = conn.cursor(); c.execute("INSERT INTO inspecciones (rut_responsable, fecha, tipo_inspeccion, hallazgos, estado) VALUES (?,?,?,?,?)", (resp, datetime.now(), tipo, desc, "PENDIENTE")); conn.commit(); st.success("Reporte enviado al APR.")
    conn.close()

elif menu == "🎓 Gestión Capacitación":
    st.title("Plan de Capacitación y Entrenamiento"); st.markdown("**Formato Oficial: RG-GD-02**"); tab_prog, tab_firma, tab_hist = st.tabs(["📅 Crear Nueva", "✍️ Asignar/Enviar a Móvil", "🗂️ Historial y PDF"]); conn = sqlite3.connect('sgsst_v11_final.db')
    with tab_prog:
        st.subheader("Nueva Capacitación")
        with st.form("new_cap"):
            col1, col2 = st.columns(2); fecha = col1.date_input("Fecha Ejecución"); hora = col2.time_input("Hora Inicio"); col3, col4 = st.columns(2); resp = col3.text_input("Responsable Capacitación", value="Alan García"); cargo = col4.text_input("Cargo Responsable", value="APR"); lugar = st.text_input("Lugar", "Sala de Capacitación Faena"); tipos = ["Inducción a personal nuevo", "Identificación de peligros y evaluación de riesgos", "Procedimientos", "Programas", "Protocolos", "Difusión"]; tipo_charla = st.selectbox("Tipo de Actividad (RG-GD-02)", tipos); tema = st.text_area("Tema a Tratar")
            if st.form_submit_button("Programar Capacitación"): c = conn.cursor(); c.execute("INSERT INTO capacitaciones (fecha, responsable, cargo_responsable, lugar, hora_inicio, tipo_charla, tema, estado) VALUES (?,?,?,?,?,?,?,?)", (fecha, resp, cargo, lugar, str(hora), tipo_charla, tema, "PROGRAMADA")); conn.commit(); st.success("Capacitación creada bajo formato oficial RG-GD-02."); st.rerun()
        st.markdown("---"); st.subheader("🗑️ Eliminar Capacitación Existente"); df_caps = pd.read_sql("SELECT id, fecha, tema FROM capacitaciones ORDER BY id DESC", conn)
        if not df_caps.empty:
            opciones_del = [f"ID {row['id']} | {row['fecha']} | {row['tema']}" for i, row in df_caps.iterrows()]; sel_del = st.selectbox("Seleccione capacitación a eliminar:", opciones_del)
            if st.button("Eliminar Seleccionada", type="primary"): id_borrar = int(sel_del.split(" | ")[0].replace("ID ", "")); c = conn.cursor(); c.execute("DELETE FROM capacitaciones WHERE id=?", (id_borrar,)); c.execute("DELETE FROM asistencia_capacitacion WHERE id_capacitacion=?", (id_borrar,)); conn.commit(); st.success("Capacitación eliminada correctamente."); st.rerun()
        else: st.info("No hay capacitaciones creadas.")
    with tab_firma:
        caps_activas = pd.read_sql("SELECT id, tema, tipo_charla FROM capacitaciones WHERE estado='PROGRAMADA'", conn)
        if not caps_activas.empty:
            opciones = [f"ID {r['id']} - {r['tema']} ({r['tipo_charla']})" for i, r in caps_activas.iterrows()]; sel_cap = st.selectbox("Seleccione Actividad:", opciones); id_cap_sel = int(sel_cap.split(" - ")[0].replace("ID ", "")); trabajadores = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
            
            def enviar_asistentes_callback(id_cap, df_trab):
                c_cb = sqlite3.connect('sgsst_v11_final.db'); cursor_cb = c_cb.cursor(); selection = st.session_state.selector_asistentes
                if selection:
                    for nombre in selection:
                        rut_t = df_trab[df_trab['nombre'] == nombre]['rut'].values[0]
                        cursor_cb.execute("INSERT INTO asistencia_capacitacion (id_capacitacion, rut_trabajador, estado) VALUES (?,?,?)", (id_cap, rut_t, "PENDIENTE"))
                    c_cb.commit(); st.session_state.exito_msg_envio = True
                c_cb.close(); st.session_state.selector_asistentes = []

            if 'selector_asistentes' not in st.session_state: st.session_state.selector_asistentes = []
            
            st.multiselect("Seleccione Asistentes para Enviar a App Móvil:", trabajadores['nombre'], key="selector_asistentes")
            st.button("Enviar a App Móvil", on_click=enviar_asistentes_callback, args=(id_cap_sel, trabajadores))
            
            if st.session_state.get("exito_msg_envio"):
                st.success("Asistentes generados exitosamente"); st.session_state.exito_msg_envio = False
        else: st.warning("No hay capacitaciones pendientes.")
    with tab_hist:
        historial = pd.read_sql("SELECT * FROM capacitaciones WHERE estado='PROGRAMADA' OR estado='EJECUTADA'", conn)
        if not historial.empty:
            st.dataframe(historial, use_container_width=True); opciones_hist = [f"ID {r['id']} - {r['tema']}" for i, r in historial.iterrows()]; sel_pdf = st.selectbox("Gestionar Capacitación (Firmar/PDF):", opciones_hist); id_pdf = int(sel_pdf.split(" - ")[0].replace("ID ", "")); st.markdown("#### ✍️ Firma del Difusor (Instructor)"); st.info("Firme aquí antes de generar el PDF.")
            if 'canvas_inst_key' not in st.session_state: st.session_state['canvas_inst_key'] = 0
            canvas_inst = st_canvas(stroke_width=2, stroke_color="#00008B", background_color="#ffffff", height=250, width=600, drawing_mode="freedraw", key=f"canvas_inst_{st.session_state['canvas_inst_key']}")
            if st.button("Guardar Firma Difusor"):
                if canvas_inst.image_data is not None:
                    img = PILImage.fromarray(canvas_inst.image_data.astype('uint8'), 'RGBA'); buffered = io.BytesIO(); img.save(buffered, format="PNG"); img_str = base64.b64encode(buffered.getvalue()).decode(); c = conn.cursor(); c.execute("UPDATE capacitaciones SET firma_instructor_b64=? WHERE id=?", (img_str, id_pdf)); conn.commit(); st.success("Firma del instructor guardada."); st.session_state['canvas_inst_key'] += 1; st.rerun()
            st.markdown("---")
            if st.button("📥 Generar PDF (Solo Firmados)"):
                pdf_bytes = generar_pdf_asistencia_rggd02(id_pdf)
                if pdf_bytes: st.download_button(label="Guardar Documento", data=pdf_bytes, file_name=f"RG-GD-02_{id_pdf}.pdf", mime="application/pdf")
                else: st.error("Error: No se encontraron datos para esta capacitación.")
        else: st.info("No hay registros.")
    conn.close()

elif menu == "📄 Generador IRL":
    st.title("Generador de IRL Automático"); conn = sqlite3.connect('sgsst_v11_final.db'); users = pd.read_sql("SELECT nombre, cargo FROM personal", conn); sel = st.selectbox("Trabajador:", users['nombre']); st.write(f"Generando documento para cargo: **{users[users['nombre']==sel]['cargo'].values[0]}**"); st.button("Generar IRL (Simulación)"); conn.close()

elif menu == "⚠️ Matriz IPER":
    st.title("Matriz de Riesgos"); conn = sqlite3.connect('sgsst_v11_final.db'); df_iper = pd.read_sql("SELECT * FROM matriz_iper", conn); st.dataframe(df_iper); conn.close()

elif menu == "🔐 Gestión Usuarios" and st.session_state['user_role'] == "ADMINISTRADOR":
    st.title("Administración de Usuarios del Sistema"); conn = sqlite3.connect('sgsst_v11_final.db')
    with st.form("new_sys_user"):
        st.subheader("Nuevo Usuario"); new_u = st.text_input("Nombre Usuario"); new_p = st.text_input("Contraseña", type="password"); new_r = st.selectbox("Rol", ["ADMINISTRADOR", "SUPERVISOR", "ASISTENTE"])
        if st.form_submit_button("Crear Usuario"):
            if new_u and new_p:
                try: c = conn.cursor(); ph = hashlib.sha256(new_p.encode()).hexdigest(); c.execute("INSERT INTO usuarios (username, password, rol) VALUES (?,?,?)", (new_u, ph, new_r)); conn.commit(); st.success(f"Usuario {new_u} creado."); st.rerun()
                except: st.error("El usuario ya existe.")
    st.markdown("---"); st.subheader("Usuarios Existentes"); users_df = pd.read_sql("SELECT username, rol FROM usuarios", conn); st.dataframe(users_df, use_container_width=True); user_del = st.selectbox("Eliminar Usuario:", users_df['username'])
    if st.button("Eliminar Seleccionado"):
        if user_del == "admin": st.error("No puedes eliminar al administrador principal.")
        else: c = conn.cursor(); c.execute("DELETE FROM usuarios WHERE username=?", (user_del,)); conn.commit(); st.success("Eliminado."); st.rerun()
    conn.close()
