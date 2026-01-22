import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
import io
import hashlib
import os
import shutil
import tempfile
import numpy as np
import base64
import uuid
from PIL import Image as PILImage
import matplotlib
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from fpdf import FPDF
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape, legal
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from streamlit_drawable_canvas import st_canvas

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CAPA DE DATOS (SQL RELACIONAL) - V47 (Auto Time + PDF Photo Fix)
# ==============================================================================
def init_erp_db():
    conn = sqlite3.connect('sgsst_v47_final_pro.db') 
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    fecha DATE, 
                    responsable TEXT,
                    cargo_responsable TEXT, 
                    lugar TEXT, 
                    hora_inicio TEXT,
                    hora_termino TEXT,
                    duracion TEXT,
                    tipo_charla TEXT, 
                    tema TEXT, 
                    estado TEXT,
                    firma_instructor_b64 TEXT,
                    evidencia_foto_b64 TEXT)''')
    
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    cargo_asociado TEXT, 
                    proceso TEXT, 
                    peligro TEXT, 
                    riesgo TEXT, 
                    consecuencia TEXT, 
                    medida_control TEXT, 
                    metodo_correcto TEXT,
                    criticidad TEXT)''')

    # --- INSPECCIONES ---
    c.execute('''CREATE TABLE IF NOT EXISTS inspecciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, rut_responsable TEXT, fecha DATETIME, 
                    tipo_inspeccion TEXT, hallazgos TEXT, estado TEXT)''')

    # --- REGISTRO EPP ---
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grupo_id TEXT, 
                    rut_trabajador TEXT,
                    nombre_trabajador TEXT,
                    cargo_trabajador TEXT, 
                    producto TEXT,
                    cantidad INTEGER,
                    talla TEXT,
                    motivo TEXT,
                    fecha_entrega DATE,
                    firma_trabajador_b64 TEXT)''')

    # --- ENTREGA RIOHS ---
    c.execute('''CREATE TABLE IF NOT EXISTS entrega_riohs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rut_trabajador TEXT,
                    nombre_trabajador TEXT,
                    tipo_entrega TEXT,
                    correo_trabajador TEXT,
                    fecha_entrega DATE,
                    firma_trabajador_b64 TEXT)''')

    # --- CARGA MASIVA DE TRABAJADORES (Default) ---
    c.execute("SELECT count(*) FROM personal")
    if c.fetchone()[0] == 0: 
        staff_completo = [
            ("16.781.002-0", "ALAN FABIAN GARCIA VIDAL", "PREVENCIONISTA DE RIESGOS", "OFICINA", "2025-10-21", "ACTIVO"),
            ("10.518.096-9", "OSCAR EDUARDO TRIVIÑO SALAZAR", "OPERADOR DE MAQUINARIA", "FAENA", "2024-01-01", "ACTIVO")
        ]
        c.executemany("INSERT OR IGNORE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", staff_completo)

    # --- MATRIZ IPER BASE ---
    c.execute("SELECT count(*) FROM matriz_iper")
    if c.fetchone()[0] == 0:
        iper_data = [
            ("OPERADOR DE MAQUINARIA", "Cosecha Mecanizada", "Pendiente Abrupta", "Volcamiento de Maquinaria", "Muerte, Amputación, Fracturas", "Cabina Certificada ROPS/FOPS, Cinturón", "Realizar Check List pre-operacional. Operar solo en pendientes autorizadas.", "CRITICO")
        ]
        c.executemany("INSERT INTO matriz_iper (cargo_asociado, proceso, peligro, riesgo, consecuencia, medida_control, metodo_correcto, criticidad) VALUES (?,?,?,?,?,?,?,?)", iper_data)

    conn.commit()
    conn.close()

# ==============================================================================
# 2. FUNCIONES DE SOPORTE
# ==============================================================================
CSV_FILE = "base_datos_galvez_v26.csv"
LOGO_FILE = "logo_empresa.png"
MESES_ORDEN = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
COLOR_PRIMARY = (183, 28, 28)
COLOR_SECONDARY = (50, 50, 50)

# LISTA OFICIAL DE CARGOS
LISTA_CARGOS = [
    "GERENTE GENERAL", 
    "GERENTE FINANZAS", 
    "PREVENCIONISTA DE RIESGOS", 
    "ADMINISTRATIVO", 
    "JEFE DE PATIO", 
    "OPERADOR DE ASERRADERO", 
    "ASISTENTE DE ASERRADERO", 
    "MECANICO LIDER", 
    "AYUDANTE MECANICO", 
    "OPERADOR DE MAQUINARIA", 
    "MOTOSIERRISTA", 
    "ESTROBERO", 
    "CALIBRADOR", 
    "PAÑOLERO"
]

def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_user(username, password):
    conn = sqlite3.connect('sgsst_v47_final_pro.db')
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

# --- HELPER FORMATO RUT CHILE ---
def formatear_rut_chile(rut_raw):
    if not rut_raw: return ""
    rut_clean = str(rut_raw).upper().replace(".", "").replace("-", "").replace(" ", "").strip()
    if "." in rut_clean and rut_clean.replace(".", "").isdigit():
         rut_clean = rut_clean.split(".")[0]
    if len(rut_clean) < 2: return rut_raw
    cuerpo = rut_clean[:-1]
    dv = rut_clean[-1]
    try:
        cuerpo_fmt = "{:,}".format(int(cuerpo)).replace(",", ".")
        return f"{cuerpo_fmt}-{dv}"
    except:
        return rut_raw 

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

# ==============================================================================
# 3. MOTORES PDF 
# ==============================================================================
def clean(val): return str(val).strip() if val is not None else " "

def get_scaled_logo(path, max_w, max_h):
    if not os.path.exists(path): return None
    try:
        pil_img = PILImage.open(path)
        orig_w, orig_h = pil_img.size
        ratio = min(max_w/orig_w, max_h/orig_h)
        return Image(path, width=new_w, height=new_h, hAlign='CENTER')
    except: return None

def generar_pdf_asistencia_rggd02(id_cap):
    conn = sqlite3.connect('sgsst_v47_final_pro.db')
    try:
        cap = conn.execute("SELECT * FROM capacitaciones WHERE id=?", (id_cap,)).fetchone()
        if cap is None: return None
        asistentes = conn.execute("SELECT p.nombre, p.rut, p.cargo, a.firma_digital_hash, a.firma_imagen_b64 FROM asistencia_capacitacion a JOIN personal p ON a.rut_trabajador = p.rut WHERE a.id_capacitacion = ? AND a.estado = 'FIRMADO'", (id_cap,)).fetchall()
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=15, bottomMargin=15, leftMargin=20, rightMargin=20)
        elements = []
        styles = getSampleStyleSheet()
        style_center = ParagraphStyle(name='Center', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10)
        style_title = ParagraphStyle(name='Title', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12, fontName='Helvetica-Bold')
        style_small = ParagraphStyle(name='Small', parent=styles['Normal'], fontSize=8)
        style_cell_header = ParagraphStyle(name='CellHeader', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8, textColor=colors.white, fontName='Helvetica-Bold')
        G_BLUE = colors.navy; G_WHITE = colors.white
        logo_obj = Paragraph("<b>MADERAS G&D</b>", style_title)
        if os.path.exists(LOGO_FILE):
            try: logo_obj = Image(LOGO_FILE, width=80, height=45, hAlign='CENTER', preserveAspectRatio=True)
            except: pass
        center_text = Paragraph("SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA<br/>SISTEMA DE GESTION<br/>SALUD Y SEGURIDAD OCUPACIONAL", style_center)
        f_fecha = clean(datetime.now().strftime('%d/%m/%Y'))
        control_data = [["REGISTRO DE CAPACITACIÓN"], ["CODIGO: RG-GD-02"], ["VERSION: 01"], [f"FECHA: {f_fecha}"], ["PAGINA: 1"]]
        t_control = Table(control_data, colWidths=[130]) 
        t_control.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('FONTSIZE', (0,0), (-1,-1), 7), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('BACKGROUND', (0,0), (0,0), G_BLUE), ('TEXTCOLOR', (0,0), (0,0), G_WHITE), ('FONTNAME', (0,0), (0,0), 'Helvetica-Bold')]))
        data_header = [[logo_obj, center_text, t_control]]
        t_head = Table(data_header, colWidths=[110, 260, 130])
        t_head.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        elements.append(t_head); elements.append(Spacer(1, 10))
        c_tipo = clean(cap[8]); c_tema = clean(cap[9]); c_resp = clean(cap[2]); c_lug = clean(cap[4]); c_fec = clean(cap[1]); c_carg = clean(cap[3]); c_dur = clean(cap[7]) if cap[7] else "00:00"
        h_act = Paragraph("ACTIVIDAD", style_cell_header); h_rel = Paragraph("RELATOR", style_cell_header); h_lug = Paragraph("LUGAR", style_cell_header); h_fec = Paragraph("FECHA", style_cell_header)
        d_act = Paragraph(c_tipo, style_center); d_rel = Paragraph(c_resp, style_center); d_lug = Paragraph(c_lug, style_center); d_fec = Paragraph(c_fec, style_center)
        t_row1 = Table([[h_act, h_rel, h_lug, h_fec], [d_act, d_rel, d_lug, d_fec]], colWidths=[180, 130, 120, 60])
        t_row1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), G_BLUE), ('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        elements.append(t_row1)
        t_row2 = Table([[f"CARGO: {c_carg}", f"DURACIÓN: {c_dur}"]], colWidths=[310, 180])
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
            row = [Paragraph(clean(nom), style_center), Paragraph(clean(rut), style_center), Paragraph(clean(car), style_center)]
            img_inserted = False
            if firma_b64 and len(str(firma_b64)) > 100:
                try: img_bytes = base64.b64decode(firma_b64); img_stream = io.BytesIO(img_bytes); img_rl = Image(img_stream, width=60, height=20); row.append(img_rl); img_inserted = True
                except: pass
            if not img_inserted: row.append(Paragraph("Firma Digital", style_center))
            data_asis.append(row)
        if len(data_asis) > 1:
            t_asis = Table(data_asis, colWidths=[180, 80, 130, 120])
            t_asis.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), G_BLUE), ('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            elements.append(t_asis); elements.append(Spacer(1, 20))
        img_instructor = Paragraph("", style_center); firma_inst_data = cap[11]; 
        if firma_inst_data and len(str(firma_inst_data)) > 100:
             try: img_bytes_inst = base64.b64decode(firma_inst_data); img_stream_inst = io.BytesIO(img_bytes_inst); img_instructor = Image(img_stream_inst, width=150, height=60)
             except: pass
        img_evidencia = Paragraph("(Sin Foto)", style_center); foto_b64 = cap[12]; 
        if foto_b64 and len(str(foto_b64)) > 100:
            try:
                # FIX: Save to temp file for reliability
                img_bytes_ev = base64.b64decode(foto_b64)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf:
                    tf.write(img_bytes_ev)
                    tf_path = tf.name
                img_evidencia = Image(tf_path, width=250, height=140)
            except: pass
        t_footer_data = [[Paragraph("EVIDENCIA FOTOGRÁFICA", style_center), "", Paragraph("VALIDACIÓN INSTRUCTOR", style_center)], [img_evidencia, "", img_instructor], ["", "", Paragraph(f"<b>{c_resp}</b><br/>Relator/Instructor", style_center)]]
        t_footer = Table(t_footer_data, colWidths=[270, 30, 210]); t_footer.setStyle(TableStyle([('GRID', (0,0), (0,1), 1, colors.black), ('GRID', (2,0), (2,1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')])); elements.append(t_footer)
        elements.append(Spacer(1, 15)); elements.append(Paragraph("Este documento constituye un registro válido del Sistema de Gestión de Seguridad y Salud en el Trabajo.", style_center))
        doc.build(elements); buffer.seek(0); return buffer
    except Exception as e: st.error(f"Error Generando PDF: {str(e)}"); return None
    finally: conn.close()

def generar_pdf_epp_grupo(grupo_id):
    conn = sqlite3.connect('sgsst_v47_final_pro.db')
    try:
        regs = conn.execute("SELECT * FROM registro_epp WHERE grupo_id=?", (grupo_id,)).fetchall()
        if not regs: return None
        rut_t = clean(regs[0][2]); nom_t = clean(regs[0][3]); cargo_t = clean(regs[0][4]); fecha_t = clean(regs[0][9]); firma_b64 = regs[0][10]
        buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=20, bottomMargin=20, leftMargin=20, rightMargin=20); elements = []; styles = getSampleStyleSheet()
        style_center = ParagraphStyle(name='Center', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10); style_head = ParagraphStyle(name='Head', parent=styles['Normal'], textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER, fontSize=9); style_cell = ParagraphStyle(name='Cell', parent=styles['Normal'], alignment=TA_CENTER, fontSize=9); style_title_log = ParagraphStyle(name='TitleLog', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER); G_BLUE = colors.navy; G_WHITE = colors.white
        logo_obj = Paragraph("<b>MADERAS G&D</b>", style_title_log)
        if os.path.exists(LOGO_FILE):
             try: logo_obj = Image(LOGO_FILE, width=80, height=45, hAlign='CENTER', preserveAspectRatio=True)
             except: pass
        center_text = Paragraph("SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA<br/>SISTEMA DE GESTION SST", style_center); f_fecha = "05/01/2026"
        control_data = [[Paragraph("REGISTRO DE EPP", ParagraphStyle('tiny', fontSize=6, textColor=G_WHITE, alignment=TA_CENTER))], [Paragraph("CODIGO: RG-GD-01", ParagraphStyle('tiny', fontSize=6, alignment=TA_CENTER))], [Paragraph("VERSION: 01", ParagraphStyle('tiny', fontSize=6, alignment=TA_CENTER))], [Paragraph(f"FECHA: {f_fecha}", ParagraphStyle('tiny', fontSize=6, alignment=TA_CENTER))], [Paragraph("PAGINA: 1", ParagraphStyle('tiny', fontSize=6, alignment=TA_CENTER))]]; t_control = Table(control_data, colWidths=[120]); t_control.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black),('BACKGROUND', (0,0), (0,0), G_BLUE),('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        t_head = Table([[logo_obj, center_text, t_control]], colWidths=[110, 270, 130]); t_head.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (0,0), 'CENTER')])); elements.append(t_head); elements.append(Spacer(1, 20))
        d_nom = Paragraph(f"<b>NOMBRE:</b> {nom_t}", style_center); d_rut = Paragraph(f"<b>RUT:</b> {rut_t}", style_center); d_car = Paragraph(f"<b>CARGO:</b> {cargo_t}", style_center); d_fec = Paragraph(f"<b>FECHA:</b> {fecha_t}", style_center); t_personal = Table([[d_nom, d_rut], [d_car, d_fec]], colWidths=[250, 250]); t_personal.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black),('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),('VALIGN', (0,0), (-1,-1), 'MIDDLE')])); elements.append(t_personal); elements.append(Spacer(1, 20))
        h_prod = Paragraph("ELEMENTO DE PROTECCIÓN (EPP)", style_head); h_cant = Paragraph("CANT.", style_head); h_talla = Paragraph("TALLA", style_head); h_mot = Paragraph("MOTIVO ENTREGA", style_head); data_epp = [[h_prod, h_cant, h_talla, h_mot]]
        for r in regs: data_epp.append([Paragraph(clean(r[5]), style_cell), Paragraph(str(r[6]), style_cell), Paragraph(clean(r[7]), style_cell), Paragraph(clean(r[8]), style_cell)])
        t_epp = Table(data_epp, colWidths=[220, 60, 60, 160]); t_epp.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), G_BLUE), ('GRID', (0,0), (-1,-1), 1, colors.black),('ALIGN', (0,0), (-1,-1), 'CENTER'),('VALIGN', (0,0), (-1,-1), 'MIDDLE')])); elements.append(t_epp); elements.append(Spacer(1, 30))
        legal_text = """<b>DECLARACIÓN DE RECEPCIÓN Y RESPONSABILIDAD:</b><br/><br/>Declaro haber recibido los Elementos de Protección Personal (EPP) detallados anteriormente, de forma gratuita y en buen estado de conservación. Me comprometo a utilizarlos correctamente durante mi jornada laboral, a cuidarlos y a solicitar su reposición inmediata en caso de deterioro o pérdida, dando estricto cumplimiento a lo establecido en el Art. 53 del D.S. 594 y el Reglamento Interno de Orden, Higiene y Seguridad de la empresa. Entiendo que el uso de estos elementos es obligatorio para proteger mi integridad física y salud."""
        style_legal = ParagraphStyle('Legal', parent=styles['Normal'], fontSize=9, alignment=TA_JUSTIFY, leading=12); elements.append(Paragraph(legal_text, style_legal)); elements.append(Spacer(1, 50))
        img_firma = Paragraph("Sin Firma Digital", style_center)
        if firma_b64 and len(str(firma_b64)) > 100:
             try: img_bytes = base64.b64decode(firma_b64); img_io = io.BytesIO(img_bytes); img_firma = Image(img_io, width=250, height=100)
             except: pass
        t_sign = Table([[img_firma], [Paragraph(f"<b>{nom_t}</b><br/>{rut_t}<br/>FIRMA TRABAJADOR", style_center)]], colWidths=[300]); t_sign.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'),('VALIGN', (0,0), (-1,-1), 'BOTTOM'),('LINEABOVE', (0,1), (0,1), 1, colors.black)])); elements.append(t_sign); elements.append(Spacer(1, 20)); elements.append(Paragraph("Este documento constituye un registro válido del Sistema de Gestión de Seguridad y Salud en el Trabajo.", style_center))
        doc.build(elements); buffer.seek(0); return buffer
    except Exception as e: st.error(f"Error PDF EPP: {e}"); return None
    finally: conn.close()

def generar_pdf_riohs(id_reg):
    conn = sqlite3.connect('sgsst_v47_final_pro.db')
    try:
        reg = conn.execute("SELECT * FROM entrega_riohs WHERE id=?", (id_reg,)).fetchone()
        if not reg: return None
        rut_t = clean(reg[1]); nom_t = clean(reg[2]); tipo = clean(reg[3]); correo = clean(reg[4]); fecha = clean(reg[5]); firma_b64 = reg[6]
        buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=20, bottomMargin=20); elements = []; styles = getSampleStyleSheet(); style_center = ParagraphStyle(name='Center', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10); style_title_log = ParagraphStyle(name='TitleLog', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER); G_BLUE = colors.navy; G_WHITE = colors.white
        logo_obj = Paragraph("<b>MADERAS G&D</b>", style_title_log)
        if os.path.exists(LOGO_FILE):
             try: logo_obj = Image(LOGO_FILE, width=80, height=45, hAlign='CENTER', preserveAspectRatio=True)
             except: pass
        center_text = Paragraph("SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA<br/>SISTEMA DE GESTION SST", style_center); f_fecha = "05/01/2026"; control_data = [[Paragraph("ENTREGA RIOHS", ParagraphStyle('tiny', fontSize=6, textColor=G_WHITE, alignment=TA_CENTER))], [Paragraph("CODIGO: RG-GD-03", ParagraphStyle('tiny', fontSize=6, alignment=TA_CENTER))], [Paragraph("VERSION: 01", ParagraphStyle('tiny', fontSize=6, alignment=TA_CENTER))], [Paragraph(f"FECHA: {f_fecha}", ParagraphStyle('tiny', fontSize=6, alignment=TA_CENTER))], [Paragraph("PAGINA: 1", ParagraphStyle('tiny', fontSize=6, alignment=TA_CENTER))]]; t_control = Table(control_data, colWidths=[120]); t_control.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black),('BACKGROUND', (0,0), (0,0), G_BLUE),('VALIGN', (0,0), (-1,-1), 'MIDDLE')])); t_head = Table([[logo_obj, center_text, t_control]], colWidths=[110, 270, 130]); t_head.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (0,0), 'CENTER')])); elements.append(t_head); elements.append(Spacer(1, 40))
        preamble = """En cumplimiento a lo dispuesto en el Artículo 156, inciso 2° del Código del Trabajo y la Ley N° 16.744, la empresa <b>SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA</b> cumple con la obligación legal de entregar gratuitamente el Reglamento Interno de Orden, Higiene y Seguridad."""; style_just = ParagraphStyle('Just', parent=styles['Normal'], alignment=TA_JUSTIFY, fontSize=11, leading=14); elements.append(Paragraph(preamble, style_just)); elements.append(Spacer(1, 20))
        txt = f"""Por el presente acto, yo <b>{nom_t}</b>, cédula de identidad N° <b>{rut_t}</b>, certifico haber recibido una copia del citado Reglamento Interno.<br/><br/>Asimismo, me comprometo a leerlo, estudiarlo y dar fiel cumplimiento a las normas, obligaciones y prohibiciones en él contenidas, entendiendo que estas regulaciones buscan proteger mi vida, salud e integridad física dentro de la organización."""; elements.append(Paragraph(txt, style_just)); elements.append(Spacer(1, 40))
        data_det = [["FECHA RECEPCIÓN:", fecha], ["FORMATO DE ENTREGA:", tipo]]; 
        if correo and len(correo) > 3: data_det.append(["CORREO ELECTRÓNICO:", correo])
        t_det = Table(data_det, colWidths=[150, 300]); t_det.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke)])); elements.append(t_det); elements.append(Spacer(1, 60))
        img_firma = Paragraph("Sin Firma Digital", style_center)
        if firma_b64 and len(str(firma_b64)) > 100:
             try: img_bytes = base64.b64decode(firma_b64); img_io = io.BytesIO(img_bytes); img_firma = Image(img_io, width=250, height=100)
             except: pass
        t_sign = Table([[img_firma], [Paragraph(f"<b>{nom_t}</b><br/>FIRMA TRABAJADOR", style_center)]], colWidths=[300]); t_sign.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'),('VALIGN', (0,0), (-1,-1), 'BOTTOM'),('LINEABOVE', (0,1), (0,1), 1, colors.black)])); elements.append(t_sign); elements.append(Spacer(1, 20)); elements.append(Paragraph("Este documento constituye un registro válido del Sistema de Gestión de Seguridad y Salud en el Trabajo.", style_center))
        doc.build(elements); buffer.seek(0); return buffer
    except Exception as e: st.error(f"Error PDF RIOHS: {e}"); return None
    finally: conn.close()

def generar_pdf_irl(rut_trabajador):
    conn = sqlite3.connect('sgsst_v47_final_pro.db')
    try:
        trab = conn.execute("SELECT * FROM personal WHERE rut=?", (rut_trabajador,)).fetchone()
        if not trab: return None
        nombre = trab[1]; cargo = trab[2]
        riesgos = conn.execute("SELECT peligro, riesgo, consecuencia, medida_control FROM matriz_iper WHERE cargo_asociado=?", (cargo,)).fetchall()
        buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=legal, topMargin=20, bottomMargin=20); elements = []; styles = getSampleStyleSheet()
        s_title = ParagraphStyle(name='Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=12); s_normal = ParagraphStyle(name='Normal', parent=styles['Normal'], fontSize=9, alignment=TA_JUSTIFY); s_table_head = ParagraphStyle(name='TH', parent=styles['Normal'], fontSize=8, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER); s_table_cell = ParagraphStyle(name='TC', parent=styles['Normal'], fontSize=8, alignment=TA_LEFT)
        logo_obj = Paragraph("<b>MADERAS G&D</b>", s_title)
        if os.path.exists(LOGO_FILE):
             try: logo_obj = Image(LOGO_FILE, width=80, height=45, hAlign='CENTER', preserveAspectRatio=True)
             except: pass
        t_head = Table([[logo_obj, Paragraph("OBLIGACION DE INFORMAR RIESGOS LABORALES (ODI)<br/>(Art. 21 DS 40)", s_title)]], colWidths=[100, 400]); t_head.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('GRID', (0,0), (-1,-1), 1, colors.black)])); elements.append(t_head); elements.append(Spacer(1, 15))
        data_personal = [["NOMBRE:", nombre, "RUT:", rut_trabajador], ["CARGO:", cargo, "FECHA:", datetime.now().strftime("%d/%m/%Y")]]; t_pers = Table(data_personal, colWidths=[60, 190, 40, 100]); t_pers.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke), ('FONTSIZE', (0,0), (-1,-1), 8)])); elements.append(t_pers); elements.append(Spacer(1, 15))
        intro = """De acuerdo con lo establecido en el Decreto Supremo N° 40, Art. 21, "Obligación de Informar los Riesgos Laborales", la empresa informa al trabajador sobre los riesgos que entrañan sus labores, las medidas preventivas y los métodos de trabajo correctos."""; elements.append(Paragraph(intro, s_normal)); elements.append(Spacer(1, 15))
        elements.append(Paragraph("<b>1. RIESGOS ESPECÍFICOS DEL CARGO</b>", s_title)); elements.append(Spacer(1, 5))
        if riesgos:
            header = [Paragraph("PELIGRO / RIESGO", s_table_head), Paragraph("CONSECUENCIA", s_table_head), Paragraph("MEDIDAS DE CONTROL", s_table_head)]; data_riesgos = [header]
            for r in riesgos:
                peligro_riesgo = f"<b>{r[0]}</b><br/>{r[1]}"; data_riesgos.append([Paragraph(peligro_riesgo, s_table_cell), Paragraph(r[2], s_table_cell), Paragraph(r[3], s_table_cell)])
            t_riesgos = Table(data_riesgos, colWidths=[150, 150, 200], repeatRows=1); t_riesgos.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.navy), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'TOP')])); elements.append(t_riesgos)
        else: elements.append(Paragraph("<i>No hay riesgos específicos registrados para este cargo en la Matriz IPER. Se aplicarán los riesgos generales.</i>", s_normal))
        elements.append(Spacer(1, 15))
        elements.append(Paragraph("<b>2. RIESGOS GENERALES Y MEDIDAS (TODOS LOS CARGOS)</b>", s_title))
        gral_txt = """<b>Caídas a mismo nivel:</b> Mantener orden y aseo, no correr, usar calzado adecuado.<br/><b>Incendio:</b> Conocer ubicación de extintores y vías de evacuación. No fumar en áreas prohibidas.<br/><b>Exposición UV:</b> Uso de bloqueador solar, gorro legionario y ropa manga larga.<br/><b>Manejo Manual de Cargas:</b> No levantar más de 25kg (hombres) o 20kg (mujeres/menores). Usar técnica de levantamiento con piernas flectadas."""; elements.append(Paragraph(gral_txt, s_normal)); elements.append(Spacer(1, 30))
        elements.append(Paragraph("Declaro haber recibido, leído y comprendido la información sobre los riesgos de mi trabajo.", s_normal)); elements.append(Spacer(1, 40))
        t_firmas = Table([["__________________________", "__________________________"], [f"{nombre}\nFIRMA TRABAJADOR", "ALAN GARCIA VIDAL\nEXPERTO EN PREVENCIÓN"]], colWidths=[250, 250]); t_firmas.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP')])); elements.append(t_firmas)
        doc.build(elements); buffer.seek(0); return buffer
    except Exception as e: return None
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
    st.divider(); 
    
    st.markdown("### ⚙️ Configuración")
    uploaded_logo = st.file_uploader("Cargar Logo Empresa (PDF)", type=['png', 'jpg'], key="logo_uploader")
    if uploaded_logo:
        with open(LOGO_FILE, "wb") as f:
            f.write(uploaded_logo.getbuffer())
        st.success("Logo cargado.")
    
    opciones_menu = ["📊 Dashboard BI", "👥 Nómina & Personal", "📱 App Móvil", "🎓 Gestión Capacitación", "🦺 Registro EPP", "📘 Entrega RIOHS", "📄 Generador IRL", "⚠️ Matriz IPER"]; 
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
        sel_month = col_m.selectbox("Mes de Corte", months_avail, index=len(months_avail)-1 if months_avail else 0); row_mes = df_year[df_year['Mes'] == sel_month].iloc[0]; idx_corte = MESES_ORDEN.index(sel_month); df_acum = df_year[df_year['Mes_Idx'] <= idx_corte]; sum_acc = df_acum['Accidentes CTP'].sum(); sum_fatales = df_acum['Accidentes Fatales'].sum(); sum_ep = df_acum['Enf. Profesionales'].sum(); sum_dias_acc = df_acum['Días Perdidos'].sum(); sum_dias_ep = df_acum['Días Perdidos EP'].sum(); sum_pensionados = df_acum['Pensionados'].sum(); sum_indemnizados = df_acum['Indemnizados'].sum(); sum_hht = df_acum['HHT'].sum(); df_masa_ok = df_acum[df_acum['Masa Laboral'] > 0]; avg_masa = df_masa_ok['Masa Laboral'].mean() if not df_masa_ok.empty else 0; ta_acum = (sum_acc / avg_masa * 100) if avg_masa > 0 else 0; ts_acum = (sum_dias_acc / avg_masa * 100) if avg_masa > 0 else 0; if_acum = (sum_acc * 1000000 / sum_hht) if sum_hht > 0 else 0; sum_dias_cargo = df_acum['Días Cargo'].sum(); ig_acum = ((sum_dias_acc + sum_dias_cargo) * 1000000 / sum_hht) if sum_hht > 0 else 0;
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
    tab_lista, tab_agregar, tab_editar, tab_excel = st.tabs(["📋 Lista Completa", "➕ Ingresar Nuevo", "✏️ Modificar / Editar", "📂 Carga Masiva"])
    conn = sqlite3.connect('sgsst_v47_final_pro.db')
    with tab_lista:
        df = pd.read_sql("SELECT nombre, rut, cargo, centro_costo as 'Lugar', estado FROM personal", conn); st.dataframe(df, use_container_width=True, hide_index=True); st.markdown("---"); st.subheader("🗑️ Dar de Baja / Eliminar"); col_del, col_btn = st.columns([3, 1]); rut_a_borrar = col_del.selectbox("Seleccione Trabajador a Eliminar:", df['rut'] + " - " + df['nombre'])
        if col_btn.button("Eliminar Trabajador"): rut_clean = rut_a_borrar.split(" - ")[0]; c = conn.cursor(); c.execute("DELETE FROM personal WHERE rut=?", (rut_clean,)); conn.commit(); st.success(f"Trabajador {rut_clean} eliminado."); st.rerun()
    with tab_agregar:
        st.subheader("Ingresar Nuevo Trabajador")
        with st.form("add_worker_manual"):
            c1, c2 = st.columns(2); n_rut_raw = c1.text_input("RUT (Ej: 12345678-9)"); n_nom = c2.text_input("Nombre Completo"); n_cargo = c1.selectbox("Cargo", LISTA_CARGOS); n_lugar = c2.selectbox("Lugar", ["ASERRADERO", "FAENA", "OFICINA", "TALLER"])
            if st.form_submit_button("Guardar en Base de Datos"):
                if n_rut_raw and n_nom:
                    n_rut_fmt = formatear_rut_chile(n_rut_raw) # AUTO-FORMATO
                    c = conn.cursor()
                    try: c.execute("INSERT INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (n_rut_fmt, n_nom, n_cargo, n_lugar, date.today(), "ACTIVO")); conn.commit(); st.success(f"Trabajador guardado: {n_rut_fmt} - {n_nom}"); st.rerun()
                    except sqlite3.IntegrityError: st.error("Error: El RUT ya existe en el sistema.")
                else: st.warning("Complete RUT y Nombre.")
    with tab_editar:
        st.subheader("Modificar Trabajador Existente")
        df_edit = pd.read_sql("SELECT rut, nombre, cargo, centro_costo FROM personal", conn)
        if not df_edit.empty:
            sel_trab_edit = st.selectbox("Buscar Trabajador:", df_edit['rut'] + " - " + df_edit['nombre'])
            rut_target = sel_trab_edit.split(" - ")[0]
            curr_data = df_edit[df_edit['rut'] == rut_target].iloc[0]
            new_nom_edit = st.text_input("Nombre:", value=curr_data['nombre'])
            idx_cargo = 0
            if curr_data['cargo'] in LISTA_CARGOS: idx_cargo = LISTA_CARGOS.index(curr_data['cargo'])
            new_cargo_edit = st.selectbox("Cargo:", LISTA_CARGOS, index=idx_cargo, key="edit_cargo")
            idx_lugar = ["ASERRADERO", "FAENA", "OFICINA", "TALLER"].index(curr_data['centro_costo']) if curr_data['centro_costo'] in ["ASERRADERO", "FAENA", "OFICINA", "TALLER"] else 0
            new_lugar_edit = st.selectbox("Lugar:", ["ASERRADERO", "FAENA", "OFICINA", "TALLER"], index=idx_lugar, key="edit_lugar")
            if st.button("💾 Actualizar Datos"):
                c = conn.cursor()
                c.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=? WHERE rut=?", (new_nom_edit, new_cargo_edit, new_lugar_edit, rut_target))
                conn.commit()
                st.success("Datos actualizados correctamente.")
                st.rerun()
        else: st.info("No hay trabajadores para editar.")
    with tab_excel:
        col_plantilla, col_upload = st.columns([1, 2])
        with col_plantilla:
            st.info("¿Necesitas el formato?")
            def generar_plantilla_excel_detallada():
                output = io.BytesIO(); data = {'NOMBRE': ['JUAN PEREZ (EJEMPLO)', 'MARIA SOTO (EJEMPLO)'], 'RUT': ['11.222.333-K', '12.345.678-9'], 'CARGO': ['OPERADOR ASERRADERO', 'AYUDANTE'], 'FECHA DE CONTRATO': ['2025-01-01', '2024-03-01']}; df_template = pd.DataFrame(data)
                with pd.ExcelWriter(output, engine='openpyxl') as writer: df_template.to_excel(writer, index=False, sheet_name='Plantilla')
                return output.getvalue()
            plantilla_data = generar_plantilla_excel_detallada(); st.download_button(label="📥 Bajar Plantilla Simple", data=plantilla_data, file_name="plantilla_carga_simple.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        uploaded_file = st.file_uploader("📂 Carga Masiva (Excel)", type=['xlsx', 'csv'])
        st.warning("⚠️ **INSTRUCCIONES IMPORTANTES DE CARGA:**\n1. Respete el orden de las columnas: **NOMBRE, RUT, CARGO, FECHA**.\n2. **NO deje celdas en blanco**; si falta un dato, rellene con un '0' o guion para evitar errores de lectura.\n3. El sistema omitirá filas vacías automáticamente, pero datos parciales pueden causar fallos.")
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'): df_new = pd.read_csv(uploaded_file)
                else: df_new = pd.read_excel(uploaded_file) 
                df_new.columns = df_new.columns.str.strip().str.upper()
                col_map = {}
                for col in df_new.columns:
                    if "RUT" in col: col_map['RUT'] = col
                    elif "NOMBRE" in col: col_map['NOMBRE'] = col
                    elif "CARGO" in col: col_map['CARGO'] = col
                    elif "FECHA" in col: col_map['FECHA'] = col
                if 'RUT' in col_map and 'NOMBRE' in col_map:
                    c = conn.cursor(); count = 0
                    for index, row in df_new.iterrows():
                        rut_raw = str(row[col_map['RUT']]).strip()
                        if not rut_raw or rut_raw.lower() == 'nan': continue
                        rut_fmt = formatear_rut_chile(rut_raw) 
                        nombre = str(row[col_map['NOMBRE']]).strip()
                        cargo = str(row.get(col_map.get('CARGO'), 'SIN CARGO')).strip()
                        try: f_cont = pd.to_datetime(row.get(col_map.get('FECHA'), date.today())).date()
                        except: f_cont = date.today()
                        lugar = "FAENA" 
                        if len(rut_fmt) > 5 and nombre.lower() != "nan": 
                            try: c.execute("INSERT OR REPLACE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (rut_fmt, nombre, cargo, lugar, f_cont, "ACTIVO")); count += 1
                            except: pass
                    conn.commit(); st.success(f"✅ Éxito: {count} trabajadores procesados."); st.rerun()
                else: st.error("Error: El archivo debe tener columnas NOMBRE y RUT.")
            except Exception as e: st.error(f"Error técnico al leer archivo: {e}")
    conn.close()

elif menu == "📱 App Móvil":
    st.title("Conexión App Móvil (Operarios)")
    st.markdown("### 📲 Panel de Registro en Terreno")
    conn = sqlite3.connect('sgsst_v47_final_pro.db')
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
    st.title("Plan de Capacitación y Entrenamiento"); st.markdown("**Formato Oficial: RG-GD-02**"); tab_prog, tab_firma, tab_hist = st.tabs(["📅 Crear Nueva", "✍️ Asignar/Enviar a Móvil", "🗂️ Historial y PDF"]); conn = sqlite3.connect('sgsst_v47_final_pro.db')
    with tab_prog:
        st.subheader("Nueva Capacitación")
        # FORMULARIO V47: AUTO-TIME + CAMARA
        with st.form("new_cap"):
            now = datetime.now()
            c1, c2 = st.columns(2)
            fecha = c1.date_input("Fecha Ejecución")
            # Hora actual por defecto
            h_inicio = c2.time_input("Hora Inicio", value=now.time())
            
            c3, c4 = st.columns(2)
            # Hora termino + 1h por defecto
            h_termino = c3.time_input("Hora Término", value=(now + timedelta(hours=1)).time())
            lugar = c4.text_input("Lugar", "Sala de Capacitación Faena")
            
            c5, c6 = st.columns(2)
            resp = c5.text_input("Responsable Capacitación", value="Alan García")
            cargo = c6.text_input("Cargo Responsable", value="APR")
            
            tipos = ["Inducción a personal nuevo", "Identificación de peligros y evaluación de riesgos", "Procedimientos", "Programas", "Protocolos", "Difusión"]
            tipo_charla = st.selectbox("Tipo de Actividad (RG-GD-02)", tipos)
            tema = st.text_area("Tema a Tratar")
            
            # CAMARA EVIDENCIA (TOGGLE)
            use_camera = st.checkbox("📸 Activar Cámara para Evidencia")
            foto_evidencia = None
            if use_camera:
                foto_evidencia = st.camera_input("Tomar foto de la actividad")

            if st.form_submit_button("Programar Capacitación"):
                # Calculo Duracion
                t1 = datetime.strptime(str(h_inicio), '%H:%M:%S')
                t2 = datetime.strptime(str(h_termino), '%H:%M:%S')
                
                if t2 < t1:
                    st.error("La hora de término no puede ser anterior a la de inicio.")
                else:
                    delta = t2 - t1
                    total_seconds = delta.total_seconds()
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    duracion_str = f"{hours:02d}:{minutes:02d} horas"

                    # Procesar Foto
                    img_str = None
                    if foto_evidencia:
                        try:
                            img = PILImage.fromarray(np.array(PILImage.open(foto_evidencia)))
                            buffered = io.BytesIO()
                            img.save(buffered, format="JPEG")
                            img_str = base64.b64encode(buffered.getvalue()).decode()
                        except: pass

                    c = conn.cursor()
                    c.execute("""INSERT INTO capacitaciones 
                                 (fecha, responsable, cargo_responsable, lugar, hora_inicio, hora_termino, duracion, tipo_charla, tema, estado, evidencia_foto_b64) 
                                 VALUES (?,?,?,?,?,?,?,?,?,?,?)""", 
                              (fecha, resp, cargo, lugar, str(h_inicio), str(h_termino), duracion_str, tipo_charla, tema, "PROGRAMADA", img_str))
                    conn.commit()
                    st.success(f"Capacitación creada. Duración calculada: {duracion_str}")
                    st.rerun()

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
                c_cb = sqlite3.connect('sgsst_v47_final_pro.db'); cursor_cb = c_cb.cursor(); selection = st.session_state.selector_asistentes
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
            st.dataframe(historial, use_container_width=True); opciones_hist = [f"ID {r['id']} - {r['tema']}" for i, r in historial.iterrows()]; sel_pdf = st.selectbox("Gestionar Capacitación (Firmar/PDF):", opciones_hist); id_pdf = int(sel_pdf.split(" - ")[0].replace("ID ", "")); st.markdown("#### ✍️ Firma del Difusor (Instructor)")
            
            # --- CONSULTA INSTANTANEA V40 ---
            conn_sig = sqlite3.connect('sgsst_v47_final_pro.db')
            firmado_db = pd.read_sql("SELECT firma_instructor_b64 FROM capacitaciones WHERE id=?", conn_sig, params=(id_pdf,))
            conn_sig.close()
            
            ya_firmado = False
            if not firmado_db.empty:
                val = firmado_db.iloc[0,0]
                if val and len(str(val)) > 200:
                    ya_firmado = True

            if ya_firmado:
                st.success("✅ Firma guardada con éxito.")
                if st.button("🗑️ Borrar Firma y Volver a Firmar"):
                    c = conn.cursor(); c.execute("UPDATE capacitaciones SET firma_instructor_b64=NULL WHERE id=?", (id_pdf,)); conn.commit(); st.rerun()
            else:
                st.info("Firme en el cuadro grande abajo:")
                # UNIQUE KEY FOR CANVAS TO FORCE RENDER
                key_canv = f"canvas_inst_{id_pdf}" 
                canvas_inst = st_canvas(stroke_width=3, stroke_color="#00008B", background_color="#ffffff", height=300, width=600, drawing_mode="freedraw", key=key_canv)
                
                if st.button("Guardar Firma Difusor"):
                    if canvas_inst.image_data is not None:
                        img = PILImage.fromarray(canvas_inst.image_data.astype('uint8'), 'RGBA'); buffered = io.BytesIO(); img.save(buffered, format="PNG"); img_str = base64.b64encode(buffered.getvalue()).decode()
                        c = conn.cursor(); c.execute("UPDATE capacitaciones SET firma_instructor_b64=? WHERE id=?", (img_str, id_pdf)); conn.commit(); 
                        st.rerun() # Refresh to hide canvas
            
            st.markdown("---")
            if st.button("📥 Generar PDF (Solo Firmados)"):
                pdf_bytes = generar_pdf_asistencia_rggd02(id_pdf)
                if pdf_bytes: st.download_button(label="Guardar Documento", data=pdf_bytes, file_name=f"RG-GD-02_{id_pdf}.pdf", mime="application/pdf")
                # Error is handled inside function now
        else: st.info("No hay registros.")
    conn.close()

elif menu == "🦺 Registro EPP":
    st.title("Control de Entrega de EPP")
    st.markdown("### Seleccione Trabajador e Items a Entregar")
    
    if 'epp_cart' not in st.session_state:
        st.session_state.epp_cart = []
        
    conn = sqlite3.connect('sgsst_v47_final_pro.db')
    trabajadores = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    opciones_trab = [f"{r['rut']} - {r['nombre']}" for i, r in trabajadores.iterrows()]
    
    sel_trab = st.selectbox("Trabajador:", opciones_trab)
    
    # Cart Interface
    c1, c2, c3 = st.columns(3)
    prod = c1.selectbox("Elemento EPP:", ["Casco de Seguridad", "Lentes de Seguridad", "Guantes de Cabritilla", "Guantes de Nitrilo", "Zapatos de Seguridad", "Chaleco Reflectante", "Protector Auditivo", "Bloqueador Solar", "Ropa de Trabajo"])
    cant = c2.number_input("Cantidad:", 1, 10, 1)
    talla = c3.text_input("Talla (Opcional):", placeholder="Ej: L, 42, Única")
    motivo = st.selectbox("Motivo:", ["Entrega Inicial", "Reposición por Deterioro", "Pérdida"])
    
    if st.button("➕ Agregar a la Lista"):
        st.session_state.epp_cart.append({
            "Producto": prod, "Cantidad": cant, "Talla": talla, "Motivo": motivo
        })
        st.success("Item agregado.")
        
    # Show Cart
    if st.session_state.epp_cart:
        st.markdown("### 🛒 Lista de Entrega")
        st.table(pd.DataFrame(st.session_state.epp_cart))
        
        if st.button("🗑️ Limpiar Lista"):
            st.session_state.epp_cart = []
            st.rerun()

        st.markdown("---")
        st.markdown("#### ✍️ Firma del Trabajador (App Móvil)")
        st.info("Firme en el recuadro para confirmar recepción:")
        
        # KEY DINAMICA PARA EL CANVAS EPP
        key_canvas = f"canvas_epp_{sel_trab}"
        canvas_epp = st_canvas(stroke_width=2, stroke_color="#00008B", background_color="#ffffff", height=250, width=600, drawing_mode="freedraw", key=key_canvas)
        
        if st.button("💾 Registrar Entrega y Guardar"):
            if canvas_epp.image_data is not None:
                rut_t = sel_trab.split(" - ")[0]
                # Obtener Cargo Automaticamente
                cargo_t = trabajadores[trabajadores['rut'] == rut_t]['cargo'].values[0]
                nombre_t = sel_trab.split(" - ")[1]
                fecha_hoy = date.today()
                grupo_id = str(uuid.uuid4())
                
                # Procesar Firma
                img = PILImage.fromarray(canvas_epp.image_data.astype('uint8'), 'RGBA')
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                c = conn.cursor()
                for item in st.session_state.epp_cart:
                    c.execute("""
                        INSERT INTO registro_epp 
                        (grupo_id, rut_trabajador, nombre_trabajador, cargo_trabajador, producto, cantidad, talla, motivo, fecha_entrega, firma_trabajador_b64) 
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (grupo_id, rut_t, nombre_t, cargo_t, item['Producto'], item['Cantidad'], item['Talla'], item['Motivo'], fecha_hoy, img_str))
                
                conn.commit()
                st.session_state.epp_cart = [] 
                st.success("Entrega registrada exitosamente!")
                st.rerun()
            else:
                st.warning("Debe firmar antes de guardar.")
    
    st.markdown("---")
    st.subheader("Historial de Entregas (Grupos)")
    hist_epp = pd.read_sql("SELECT grupo_id, fecha_entrega, nombre_trabajador, cargo_trabajador, count(*) as items FROM registro_epp GROUP BY grupo_id ORDER BY id DESC", conn)
    
    if not hist_epp.empty:
        st.dataframe(hist_epp, use_container_width=True)
        opciones_descarga = [f"{r['fecha_entrega']} | {r['nombre_trabajador']} | ID: {r['grupo_id']}" for i, r in hist_epp.iterrows()]
        sel_descarga = st.selectbox("Seleccione Entrega para PDF:", opciones_descarga)
        
        if st.button("📥 Descargar Comprobante EPP"):
            grp_id = sel_descarga.split("ID: ")[1]
            pdf_bytes = generar_pdf_epp_grupo(grp_id)
            if pdf_bytes:
                st.download_button("Guardar PDF", pdf_bytes, f"EPP_{grp_id}.pdf", "application/pdf")
            else:
                st.error("Error generando PDF.")
    else:
        st.info("No hay registros aún.")
        
    conn.close()

elif menu == "📘 Entrega RIOHS":
    st.title("Entrega Reglamento Interno (RIOHS)")
    conn = sqlite3.connect('sgsst_v47_final_pro.db')
    trabajadores = pd.read_sql("SELECT rut, nombre FROM personal", conn)
    opciones_trab = [f"{r['rut']} - {r['nombre']}" for i, r in trabajadores.iterrows()]
    
    sel_trab = st.selectbox("Trabajador:", opciones_trab)
    c1, c2 = st.columns(2)
    tipo_copia = c1.selectbox("Formato de Entrega:", ["Copia Física (Papel)", "Copia Digital (PDF/Email)"])
    
    # Campo Condicional para Correo
    correo_input = ""
    if "Digital" in tipo_copia:
        correo_input = c2.text_input("Correo Electrónico del Trabajador:")
    else:
        c2.text_input("Correo (No aplica para físico):", disabled=True)
    
    fecha_riohs = st.date_input("Fecha de Recepción:", value=date.today())
    
    st.markdown("---")
    st.markdown("#### ✍️ Firma de Recepción")
    canvas_riohs = st_canvas(stroke_width=2, stroke_color="#00008B", background_color="#ffffff", height=200, width=600, drawing_mode="freedraw", key="canvas_riohs_sign")
    
    if st.button("Registrar Entrega RIOHS"):
        if canvas_riohs.image_data is not None:
            rut_t = sel_trab.split(" - ")[0]
            nombre_t = sel_trab.split(" - ")[1]
            
            # Guardar Firma
            img = PILImage.fromarray(canvas_riohs.image_data.astype('uint8'), 'RGBA')
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            c = conn.cursor()
            c.execute("""
                INSERT INTO entrega_riohs (rut_trabajador, nombre_trabajador, tipo_entrega, correo_trabajador, fecha_entrega, firma_trabajador_b64) 
                VALUES (?,?,?,?,?,?)
            """, (rut_t, nombre_t, tipo_copia, correo_input, fecha_riohs, img_str))
            
            conn.commit()
            st.success("Entrega de reglamento registrada correctamente.")
            st.rerun()
        else:
            st.warning("Debe firmar para registrar.")

    st.markdown("---")
    st.subheader("Control de Entrega RIOHS")
    hist_riohs = pd.read_sql("SELECT * FROM entrega_riohs ORDER BY id DESC", conn)
    
    if not hist_riohs.empty:
        st.dataframe(hist_riohs, use_container_width=True)
        opciones_riohs = [f"ID {r['id']} | {r['fecha_entrega']} | {r['nombre_trabajador']}" for i, r in hist_riohs.iterrows()]
        sel_riohs = st.selectbox("Descargar Comprobante RIOHS:", opciones_riohs)
        if st.button("📥 Descargar Comprobante RIOHS"):
            id_riohs = int(sel_riohs.split(" | ")[0].replace("ID ", ""))
            pdf_riohs = generar_pdf_riohs(id_riohs)
            if pdf_riohs: st.download_button("Guardar PDF", pdf_riohs, f"RIOHS_{id_riohs}.pdf", "application/pdf")
            else: st.error("Error al generar.")
    else: st.info("No hay registros.")
    conn.close()

elif menu == "📄 Generador IRL":
    st.title("Generador de IRL Automático"); conn = sqlite3.connect('sgsst_v47_final_pro.db'); users = pd.read_sql("SELECT nombre, cargo FROM personal", conn); sel = st.selectbox("Trabajador:", users['nombre']); st.write(f"Generando documento para cargo: **{users[users['nombre']==sel]['cargo'].values[0]}**"); st.button("Generar IRL (Simulación)"); conn.close()

elif menu == "⚠️ Matriz IPER":
    st.title("Matriz de Riesgos"); conn = sqlite3.connect('sgsst_v47_final_pro.db'); df_iper = pd.read_sql("SELECT * FROM matriz_iper", conn); st.dataframe(df_iper); conn.close()

elif menu == "🔐 Gestión Usuarios" and st.session_state['user_role'] == "ADMINISTRADOR":
    st.title("Administración de Usuarios del Sistema"); conn = sqlite3.connect('sgsst_v47_final_pro.db')
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
