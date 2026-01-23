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
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import legal, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from streamlit_drawable_canvas import st_canvas

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 0. CONFIGURACIÓN GLOBAL
# ==============================================================================
# CAMBIAMOS EL NOMBRE DE LA DB PARA ELIMINAR EL ARCHIVO CORRUPTO/BLOQUEADO
DB_NAME = 'sgsst_v72_clean.db'
CSV_FILE = "base_datos_galvez.csv"
LOGO_FILE = os.path.abspath("logo_empresa.png")
FECHA_DOCUMENTOS = "05/01/2026"
G_CORP = HexColor('#5A2F1B')
G_WHITE = colors.white

# ==============================================================================
# 1. CAPA DE DATOS E INICIALIZACIÓN
# ==============================================================================
# Datos de Riesgos para Carga Inicial
INITIAL_MIPER_DATA = [
    ("GERENTE GENERAL", "Administración", "Desorden en oficina", "Caída mismo nivel", "Contusión, Esguince", "Orden y aseo, cables ordenados", "Transitar por vías despejadas", "MODERADO"),
    ("GERENTE GENERAL", "Terreno", "Tránsito en faena", "Atropello", "Muerte, Fracturas", "Chaleco reflectante, estar atento", "Contacto visual con operadores", "IMPORTANTE"),
    ("PREVENCIONISTA DE RIESGOS", "Gestión", "Conducción vehículo", "Choque/Colisión", "Politraumatismo", "Manejo a la defensiva, Licencia al día", "Respetar leyes tránsito", "IMPORTANTE"),
    ("PREVENCIONISTA DE RIESGOS", "Terreno", "Radiación UV", "Insolación", "Quemaduras", "Bloqueador, Gorro legionario", "Reaplicar bloqueador 2hrs", "MODERADO"),
    ("JEFE DE PATIO", "Logística", "Tránsito maquinaria", "Atropello", "Muerte", "Chaleco Alta Visibilidad, Vías segregadas", "No usar celular al caminar", "CRITICO"),
    ("JEFE DE PATIO", "Supervisión", "Caída altura (Manitou)", "Fracturas", "Trauma", "No subir a horquillas, uso arnés si aplica", "3 puntos de apoyo", "IMPORTANTE"),
    ("OPERADOR DE ASERRADERO", "Producción", "Ruido", "Hipoacusia", "Sordera", "Fonos/Tapones certificados", "Uso permanente", "IMPORTANTE"),
    ("OPERADOR DE ASERRADERO", "Corte", "Contacto elementos cortantes", "Cortes/Amputación", "Herida grave", "Guardas de seguridad, No intervenir en movimiento", "Uso de empujadores", "CRITICO"),
    ("AYUDANTE DE ASERRADERO", "Producción", "Proyección partículas", "Impacto ocular", "Lesión ocular", "Lentes seguridad, Biombos", "No exponerse a línea fuego", "IMPORTANTE"),
    ("AYUDANTE DE ASERRADERO", "Limpieza", "Polvo madera", "Problemas respiratorios", "Neumoconiosis", "Mascarilla, Ventilación", "Aseo constante", "MODERADO"),
    ("OPERADOR DE MAQUINARIA", "Cosecha", "Pendiente abrupta", "Volcamiento", "Muerte, Aplastamiento", "Cabina ROPS/FOPS, Cinturón", "Operar en pendientes autorizadas", "CRITICO"),
    ("OPERADOR DE MAQUINARIA", "Operación", "Falla hidráulica", "Proyección fluido", "Quemadura, Golpe", "Mantención preventiva, Inspección visual", "Despresurizar antes de intervenir", "IMPORTANTE"),
    ("MOTOSIERRISTA", "Tala", "Cadena en movimiento", "Corte/Amputación", "Hemorragia", "Pantalón anticorte, Botín, Guantes", "Freno cadena al caminar", "CRITICO"),
    ("MOTOSIERRISTA", "Tala", "Caída árbol/rama", "Golpe", "Muerte", "Planificación caída, Vía escape 45°", "Distancia seguridad 2 alturas", "CRITICO"),
    ("ESTROBERO", "Madereo", "Cable tenso", "Latigazo", "Amputación, Muerte", "Distancia seguridad, No exponerse a línea tensión", "Esperar cable distendido", "CRITICO"),
    ("ESTROBERO", "Terreno", "Suelo irregular", "Caída", "Esguince", "Calzado caña alta, Vías despejadas", "Tránsito atento", "MODERADO"),
    ("MECANICO LIDER", "Mantención", "Energía residual", "Atrapamiento", "Amputación", "Bloqueo LOTO, Disipación energía", "Verificar energía cero", "CRITICO"),
    ("AYUDANTE MECANICO", "Mantención", "Herramientas manuales", "Golpe/Corte", "Herida leve", "Herramientas en buen estado", "Uso correcto herramienta", "MODERADO")
]

def init_erp_db():
    conn = sqlite3.connect(DB_NAME) 
    c = conn.cursor()
    
    # --- CREACIÓN DE TABLAS ---
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    
    # Solución robusta para usuario admin
    try:
        c.execute("INSERT OR IGNORE INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
    except:
        pass # Si falla, ya existe o hay bloqueo, continuamos

    c.execute('''CREATE TABLE IF NOT EXISTS personal (
                    rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, 
                    centro_costo TEXT, fecha_contrato DATE, estado TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    fecha DATE, responsable TEXT, cargo_responsable TEXT, lugar TEXT, 
                    hora_inicio TEXT, hora_termino TEXT, duracion TEXT, tipo_charla TEXT, 
                    tema TEXT, estado TEXT, firma_instructor_b64 TEXT, evidencia_foto_b64 TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, id_capacitacion INTEGER, 
                    rut_trabajador TEXT, hora_firma DATETIME, firma_digital_hash TEXT, 
                    firma_imagen_b64 TEXT, estado TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, cargo_asociado TEXT, proceso TEXT, 
                    peligro TEXT, riesgo TEXT, consecuencia TEXT, medida_control TEXT, 
                    metodo_correcto TEXT, criticidad TEXT)''')
    
    # Carga inicial de matriz si está vacía
    c.execute("SELECT count(*) FROM matriz_iper")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO matriz_iper (cargo_asociado, proceso, peligro, riesgo, consecuencia, medida_control, metodo_correcto, criticidad) VALUES (?,?,?,?,?,?,?,?,?)", INITIAL_MIPER_DATA)

    c.execute('''CREATE TABLE IF NOT EXISTS inspecciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, rut_responsable TEXT, fecha DATETIME, 
                    tipo_inspeccion TEXT, hallazgos TEXT, estado TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, grupo_id TEXT, rut_trabajador TEXT, 
                    nombre_trabajador TEXT, cargo_trabajador TEXT, producto TEXT, cantidad INTEGER, 
                    talla TEXT, motivo TEXT, fecha_entrega DATE, firma_trabajador_b64 TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS entrega_riohs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, rut_trabajador TEXT, nombre_trabajador TEXT, 
                    tipo_entrega TEXT, correo_trabajador TEXT, fecha_entrega DATE, firma_trabajador_b64 TEXT)''')

    # Personal Default si está vacío
    c.execute("SELECT count(*) FROM personal")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT OR IGNORE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", [
            ("16.781.002-0", "ALAN FABIAN GARCIA VIDAL", "PREVENCIONISTA DE RIESGOS", "OFICINA", "2025-10-21", "ACTIVO"),
            ("10.518.096-9", "OSCAR EDUARDO TRIVIÑO SALAZAR", "OPERADOR DE MAQUINARIA", "FAENA", "2024-01-01", "ACTIVO")
        ])

    conn.commit()
    conn.close()

# ==============================================================================
# 2. SOPORTE Y LISTAS
# ==============================================================================
MESES_ORDEN = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
COLOR_PRIMARY = (183, 28, 28)
COLOR_SECONDARY = (50, 50, 50)

LISTA_CARGOS = [
    "GERENTE GENERAL", "GERENTE FINANZAS", "PREVENCIONISTA DE RIESGOS", "ADMINISTRATIVO", "JEFE DE PATIO", 
    "OPERADOR DE ASERRADERO", "ASISTENTE DE ASERRADERO", "MECANICO LIDER", "AYUDANTE MECANICO", 
    "OPERADOR DE MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "CALIBRADOR", "PAÑOLERO", 
    "OPERADOR FORWARDER", "OPERADOR SKIDDER"
]

LISTA_EPP = [
    "ZAPATOS DE SEGURIDAD", "GUANTES MULTIFLEX", "PROTECTOR SOLAR", "OVEROL", "LENTES DE SEGURIDAD", 
    "GORRO LEGIONARIO", "CASCO", "TRAJE DE AGUA", "GUANTE CABRITILLA", "ARNES", "CABO DE VIDA", 
    "PROTECTOR FACIAL", "CHALECO REFLECTANTE", "PANTALON ANTICORTE", "MASCARILLAS DESECHABLES", 
    "ALCOHOL GEL", "CHAQUETA ANTICORTE", "FONO AUDITIVO", "FONO PARA CASCO", "BOTA FORESTAL", "ROPA ALTA VISIBILIDAD"
]

# --- BASE DE DATOS IRL ---
IRL_DATA_DB = {
    "OPERADOR DE MAQUINARIA": {
        "espacio": "Ubicación: Faena forestal. Dimensiones: Extensas. Acceso: Restringido/Irregular. Pisos: Natural, irregular, riesgo volcamiento.",
        "ambiente": "Iluminación: Variable. Ventilación: Cabina. Ruido: Elevado (Motor). Polvo: En suspensión.",
        "orden": "Herramientas ordenadas en caja. Cabina limpia de residuos.",
        "maquinas": "Cosechadora, Skidder, Forwarder. Herramientas: Llaves, Extintor.",
        "riesgos_txt": "Volcamiento, Atropello, Incendio, Golpes.",
        "medidas_txt": "Cinturón seguridad, Cabina ROPS/FOPS, Extintor PQS, LOTO en mantención.",
        "metodos_txt": "Check list diario, operar en pendientes autorizadas, mantener distancia.",
        "sustancia": "DIESEL"
    },
    "MOTOSIERRISTA": {
        "espacio": "Bosque denso, terreno irregular, tocones y ramas.",
        "ambiente": "Ruido: >85dB. Vibración: Alta. Clima: Extremo.",
        "orden": "Vía de escape despejada. Combustible zona segura.",
        "maquinas": "Motosierra, Cuñas, Hacha.",
        "riesgos_txt": "Cortes graves, Golpe por rama, Vibración, Ruido.",
        "medidas_txt": "EPP Anticorte, Freno cadena, Pausas activas.",
        "metodos_txt": "Técnica tala dirigida, Vía escape 45°.",
        "sustancia": "MEZCLA"
    },
    "ESTROBERO": {
        "espacio": "Canchas madereo, pendientes, suelo resbaladizo.",
        "ambiente": "Polvo, Ruido maquinaria, Clima variable.",
        "orden": "Estrobos ordenados.",
        "maquinas": "Estrobos acero, Ganchos, Radio.",
        "riesgos_txt": "Atropello, Golpes por cables (Latigazo), Caídas.",
        "medidas_txt": "Chaleco Reflectante, Contacto visual, Distancia seguridad.",
        "metodos_txt": "Nunca exponerse a línea tensión. Esperar cable quieto.",
        "sustancia": "N/A"
    },
    "JEFE DE PATIO": {
        "espacio": "Patio aserradero, zonas acopio, alto tránsito.",
        "ambiente": "Ruido constante, Polvo madera.",
        "orden": "Vías despejadas.",
        "maquinas": "Manitou, Camioneta, Radio.",
        "riesgos_txt": "Atropello, Caída altura (Manitou), Golpes carga.",
        "medidas_txt": "Chaleco Alta Visibilidad, Vías peatonales, 3 puntos apoyo.",
        "metodos_txt": "Contacto visual permanente. No transitar bajo carga.",
        "sustancia": "DIESEL"
    },
    "AYUDANTE DE ASERRADERO": {
        "espacio": "Planta industrial fija (Galpón).",
        "ambiente": "Ruido elevado. Polvo suspensión. Iluminación artificial.",
        "orden": "Retiro constante de aserrín/viruta.",
        "maquinas": "Sierras, Cintas, Herramientas manuales.",
        "riesgos_txt": "Cortes, Ruido, Proyección partículas, Incendio.",
        "medidas_txt": "No intervenir movimiento, Fonos, Lentes, Extintores.",
        "metodos_txt": "Uso empujadores. Respetar señalética.",
        "sustancia": "N/A"
    },
    "PREVENCIONISTA DE RIESGOS": {
        "espacio": "Oficina y Terreno.",
        "ambiente": "Oficina (Ergonomía) / Terreno (Clima).",
        "orden": "Escritorio limpio.",
        "maquinas": "Computador, Camioneta.",
        "riesgos_txt": "Caídas, Atropello, UV.",
        "medidas_txt": "Vías despejadas, Chaleco, Bloqueador.",
        "metodos_txt": "Conducción a la defensiva.",
        "sustancia": "N/A"
    },
    "DEFAULT": {
        "espacio": "Instalaciones empresa.",
        "ambiente": "Estándar.",
        "orden": "Mantener orden.",
        "maquinas": "Herramientas manuales.",
        "riesgos_txt": "Caída, Golpe.",
        "medidas_txt": "Uso EPP, Precaución.",
        "metodos_txt": "Seguir procedimientos.",
        "sustancia": "N/A"
    }
}
for c in LISTA_CARGOS:
    if c not in IRL_DATA_DB: 
        if "ASERRADERO" in c: IRL_DATA_DB[c] = IRL_DATA_DB["AYUDANTE DE ASERRADERO"]
        elif "MECANICO" in c: IRL_DATA_DB[c] = IRL_DATA_DB["DEFAULT"]
        else: IRL_DATA_DB[c] = IRL_DATA_DB["DEFAULT"]

def hash_pass(password): return hashlib.sha256(password.encode()).hexdigest()
def login_user(username, password):
    conn = sqlite3.connect(DB_NAME); c = conn.cursor()
    c.execute("SELECT rol FROM usuarios WHERE username=? AND password=?", (username, hash_pass(password)))
    result = c.fetchone(); conn.close()
    return result[0] if result else None
def clean(val): return str(val).strip() if val is not None else " "
def get_scaled_logo_obj(path, max_w, max_h):
    if not os.path.exists(path): return Paragraph("<b>MADERAS G&D</b>", ParagraphStyle(name='NoLogo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER))
    try:
        pil_img = PILImage.open(path); orig_w, orig_h = pil_img.size; ratio = min(max_w/orig_w, max_h/orig_h)
        return Image(path, width=orig_w*ratio, height=orig_h*ratio, hAlign='CENTER')
    except: return Paragraph("<b>MADERAS G&D</b>", ParagraphStyle(name='NoLogo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER))

def get_header_table(title_doc, codigo):
    logo_obj = get_scaled_logo_obj(LOGO_FILE, 90, 50)
    center_text = Paragraph(f"SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA<br/>SISTEMA DE GESTION SST DS44<br/><br/><b>{title_doc}</b>", ParagraphStyle(name='HC', fontSize=10, alignment=TA_CENTER))
    control_data = [[Paragraph(f"CODIGO: {codigo}", ParagraphStyle('t', fontSize=7, alignment=TA_CENTER))], [Paragraph("VERSION: 01", ParagraphStyle('t', fontSize=7, alignment=TA_CENTER))], [Paragraph(f"FECHA: {FECHA_DOCUMENTOS}", ParagraphStyle('t', fontSize=7, alignment=TA_CENTER))], [Paragraph("PAGINA: 1", ParagraphStyle('t', fontSize=7, alignment=TA_CENTER))]]
    t_control = Table(control_data, colWidths=[120]); t_control.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.white), ('TEXTCOLOR', (0,0), (-1,-1), colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    t_head = Table([[logo_obj, center_text, t_control]], colWidths=[100, 320, 120]); t_head.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    return t_head

# Funciones de BI y Datos
def procesar_datos(df, factor_base=210):
    for col in df.columns:
        if col not in ['Año', 'Mes', 'Observaciones']: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['HHT'] = (df['Masa Laboral'] * factor_base) + df['Horas Extras'] - df['Horas Ausentismo']
    def calc_row(row):
        masa = row['Masa Laboral']; hht = row['HHT']
        if masa <= 0 or hht <= 0: return 0, 0, 0, 0
        return (row['Accidentes CTP']/masa)*100, (row['Días Perdidos']/masa)*100, (row['Accidentes CTP']*1000000)/hht, ((row['Días Perdidos']+row['Días Cargo'])*1000000)/hht
    res = df.apply(calc_row, axis=1, result_type='expand')
    df['Tasa Acc.'], df['Tasa Sin.'], df['Indice Frec.'], df['Indice Grav.'] = res[0], res[1], res[2], res[3]
    return df
def load_data():
    if os.path.exists(CSV_FILE):
        try: return procesar_datos(pd.read_csv(CSV_FILE), 210)
        except: pass
    return get_structure_for_year(2026)
def save_data(df, factor_base):
    df_calc = procesar_datos(df, factor_base); df_calc.to_csv(CSV_FILE, index=False); return df_calc
def formatear_rut_chile(rut_raw):
    if not rut_raw: return ""
    rut_clean = str(rut_raw).upper().replace(".", "").replace("-", "").replace(" ", "").strip()
    if len(rut_clean) < 2: return rut_raw
    try: return f"{int(rut_clean[:-1]):,}".replace(",", ".") + "-" + rut_clean[-1]
    except: return rut_raw

def inicializar_db_completa():
    df_24 = get_structure_for_year(2024); df_25 = get_structure_for_year(2025); df_26 = get_structure_for_year(2026)
    return pd.concat([df_24, df_25, df_26], ignore_index=True)

def get_structure_for_year(year):
    data = []
    for m in MESES_ORDEN:
        data.append({
            'Año': int(year), 'Mes': m, 'Masa Laboral': 0.0, 'Horas Extras': 0.0, 'Horas Ausentismo': 0.0,
            'Accidentes CTP': 0.0, 'Accidentes Fatales': 0.0, 'Días Perdidos': 0.0, 'Días Cargo': 0.0,
            'Enf. Profesionales': 0.0, 'Días Perdidos EP': 0.0, 'Pensionados': 0.0, 'Indemnizados': 0.0,
            'Insp. Programadas': 0.0, 'Insp. Ejecutadas': 0.0, 'Cap. Programadas': 0.0, 'Cap. Ejecutadas': 0.0,
            'Medidas Abiertas': 0.0, 'Medidas Cerradas': 0.0, 'Expuestos Silice/Ruido': 0.0, 'Vig. Salud Vigente': 0.0,
            'Observaciones': "", 'HHT': 0.0, 'Tasa Acc.': 0.0, 'Tasa Sin.': 0.0, 'Indice Frec.': 0.0, 'Indice Grav.': 0.0
        })
    return pd.DataFrame(data)

def generar_insight_automatico(row_mes, ta_acum, metas):
    return "Análisis Automático Disponible"

# ==============================================================================
# 3. GENERADORES PDF
# ==============================================================================
def generar_pdf_asistencia_rggd02(id_cap):
    conn = sqlite3.connect(DB_NAME)
    try:
        cap = conn.execute("SELECT * FROM capacitaciones WHERE id=?", (id_cap,)).fetchone()
        if not cap: return None
        asistentes = conn.execute("SELECT p.nombre, p.rut, p.cargo, a.firma_digital_hash, a.firma_imagen_b64 FROM asistencia_capacitacion a JOIN personal p ON a.rut_trabajador = p.rut WHERE a.id_capacitacion = ? AND a.estado = 'FIRMADO'", (id_cap,)).fetchall()
        buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=legal, topMargin=15, bottomMargin=15, leftMargin=30, rightMargin=30); elements = []
        styles = getSampleStyleSheet(); style_center = ParagraphStyle(name='Center', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10); style_cell_header = ParagraphStyle(name='CellHeader', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8, textColor=colors.white, fontName='Helvetica-Bold')
        elements.append(get_header_table("REGISTRO DE CAPACITACIÓN", "RG-GD-02")); elements.append(Spacer(1, 10))
        c_tipo, c_tema, c_resp, c_lug, c_fec = clean(cap[8]), clean(cap[9]), clean(cap[2]), clean(cap[4]), clean(cap[1])
        c_carg, c_dur = clean(cap[3]), (clean(cap[7]) if cap[7] else "00:00")
        t_row1 = Table([[Paragraph("ACTIVIDAD", style_cell_header), Paragraph("RELATOR", style_cell_header), Paragraph("LUGAR", style_cell_header), Paragraph("FECHA", style_cell_header)], [Paragraph(c_tipo, style_center), Paragraph(c_resp, style_center), Paragraph(c_lug, style_center), Paragraph(c_fec, style_center)]], colWidths=[190, 130, 120, 100]); t_row1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), G_CORP), ('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')])); elements.append(t_row1)
        t_row2 = Table([[f"CARGO: {c_carg}", f"DURACIÓN: {c_dur}"]], colWidths=[340, 200]); t_row2.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('FONTSIZE', (0,0), (-1,-1), 8), ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold')])); elements.append(t_row2); elements.append(Spacer(1, 5))
        t_tem = Table([[Paragraph("TEMARIO", style_cell_header)], [Paragraph(c_tema, ParagraphStyle('s', fontSize=8))]], colWidths=[540], rowHeights=[None, 60]); t_tem.setStyle(TableStyle([('BACKGROUND', (0,0), (0,0), G_CORP), ('GRID', (0,0), (-1,-1), 1, colors.black)])); elements.append(t_tem); elements.append(Spacer(1, 10))
        header_asis = [Paragraph("NOMBRE", style_cell_header), Paragraph("RUT", style_cell_header), Paragraph("CARGO", style_cell_header), Paragraph("FIRMA", style_cell_header)]; data_asis = [header_asis]
        for idx, (nom, rut, car, fh, fb64) in enumerate(asistentes, 1):
            row = [Paragraph(clean(nom), style_center), Paragraph(clean(rut), style_center), Paragraph(clean(car), style_center)]; img_inserted = False
            if fb64:
                try: img = Image(io.BytesIO(base64.b64decode(fb64)), width=100, height=35); row.append(img); img_inserted = True 
                except: pass
            if not img_inserted: row.append(Paragraph("Firma Digital", style_center))
            data_asis.append(row)
        if len(data_asis) > 1:
            t_asis = Table(data_asis, colWidths=[200, 90, 130, 120]); t_asis.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), G_CORP), ('GRID', (0,0), (-1,-1), 1, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')])); elements.append(t_asis); elements.append(Spacer(1, 20))
        img_instructor = Paragraph("", style_center)
        if cap[11]: 
            try: img_instructor = Image(io.BytesIO(base64.b64decode(cap[11])), width=200, height=80)
            except: pass
        img_evidencia = Paragraph("(Sin Foto)", style_center)
        if cap[12]:
            try: tf = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg"); tf.write(base64.b64decode(cap[12])); tf.close(); img_evidencia = Image(tf.name, width=270, height=160)
            except: pass
        t_footer = Table([[Paragraph("EVIDENCIA", style_center), "", Paragraph("INSTRUCTOR", style_center)], [img_evidencia, "", img_instructor]], colWidths=[270, 20, 250])
        t_footer.setStyle(TableStyle([('GRID', (0,0), (0,1), 1, colors.black), ('GRID', (2,0), (2,1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')])); elements.append(t_footer)
        doc.build(elements); buffer.seek(0); conn.close(); return buffer
    except Exception as e: return None
    finally: conn.close()

def generar_pdf_epp_grupo(grupo_id):
    conn = sqlite3.connect(DB_NAME)
    try:
        regs = conn.execute("SELECT * FROM registro_epp WHERE grupo_id=?", (grupo_id,)).fetchall()
        if not regs: return None
        rut_t = clean(regs[0][2]); nom_t = clean(regs[0][3]); cargo_t = clean(regs[0][4]); fecha_t = clean(regs[0][9]); firma_b64 = regs[0][10]
        buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=legal, topMargin=20, bottomMargin=20, leftMargin=30, rightMargin=30); elements = []; styles = getSampleStyleSheet()
        style_c = ParagraphStyle('C', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10); style_h = ParagraphStyle('H', parent=styles['Normal'], textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER, fontSize=9)
        elements.append(get_header_table("REGISTRO DE EPP", "RG-GD-01")); elements.append(Spacer(1, 20))
        t_per = Table([[Paragraph(f"<b>NOMBRE:</b> {nom_t}", style_c), Paragraph(f"<b>RUT:</b> {rut_t}", style_c)], [Paragraph(f"<b>CARGO:</b> {cargo_t}", style_c), Paragraph(f"<b>FECHA:</b> {fecha_t}", style_c)]], colWidths=[270, 270]); t_per.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)])); elements.append(t_per); elements.append(Spacer(1, 20))
        data_epp = [[Paragraph("ELEMENTO", style_h), Paragraph("CANT.", style_h), Paragraph("TALLA", style_h), Paragraph("MOTIVO", style_h)]]
        for r in regs: data_epp.append([Paragraph(clean(r[5]), style_c), Paragraph(str(r[6]), style_c), Paragraph(clean(r[7]), style_c), Paragraph(clean(r[8]), style_c)])
        t_epp = Table(data_epp, colWidths=[240, 60, 60, 180]); t_epp.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), G_CORP), ('GRID', (0,0), (-1,-1), 1, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER')])); elements.append(t_epp); elements.append(Spacer(1, 30))
        elements.append(Paragraph("<b>DECLARACIÓN:</b> Declaro haber recibido los EPP detallados, de forma gratuita (Art. 53 DS 594).", ParagraphStyle('L', parent=styles['Normal'], fontSize=10, alignment=TA_JUSTIFY))); elements.append(Spacer(1, 50))
        img = Paragraph("Sin Firma", style_c)
        if firma_b64:
             try: img = Image(io.BytesIO(base64.b64decode(firma_b64)), width=250, height=100)
             except: pass
        t_s = Table([[img], [Paragraph("FIRMA TRABAJADOR", style_c)]], colWidths=[300]); t_s.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('LINEABOVE', (0,1), (0,1), 1, colors.black)])); elements.append(t_s)
        doc.build(elements); buffer.seek(0); conn.close(); return buffer
    except: return None
    finally: conn.close()

def generar_pdf_riohs(id_reg):
    conn = sqlite3.connect(DB_NAME)
    try:
        r = conn.execute("SELECT * FROM entrega_riohs WHERE id=?", (id_reg,)).fetchone()
        if not r: return None
        rut, nom, tipo, mail, fec, fb64 = clean(r[1]), clean(r[2]), clean(r[3]), clean(r[4]), clean(r[5]), r[6]
        buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=legal, topMargin=20, bottomMargin=20, leftMargin=30, rightMargin=30); elements = []; styles = getSampleStyleSheet(); style_c = ParagraphStyle(name='C', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10)
        elements.append(get_header_table("ENTREGA RIOHS", "RG-GD-03")); elements.append(Spacer(1, 40))
        elements.append(Paragraph("En cumplimiento del Art. 156 del Código del Trabajo, Ley 16.744 y DS 44, se entrega el RIOHS.", ParagraphStyle('J', parent=styles['Normal'], alignment=TA_JUSTIFY, fontSize=11))); elements.append(Spacer(1, 40))
        t_d = Table([["FECHA:", fec], ["FORMATO:", tipo], ["CORREO:", mail]], colWidths=[150, 300]); t_d.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke)])); elements.append(t_d); elements.append(Spacer(1, 60))
        img = Paragraph("Sin Firma", style_c)
        if fb64:
             try: img = Image(io.BytesIO(base64.b64decode(fb64)), width=250, height=100)
             except: pass
        t_s = Table([[img], [Paragraph("FIRMA TRABAJADOR", style_c)]], colWidths=[300]); t_s.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('LINEABOVE', (0,1), (0,1), 1, colors.black)])); elements.append(t_s)
        doc.build(elements); buffer.seek(0); conn.close(); return buffer
    except: return None
    finally: conn.close()

def generar_pdf_irl(data):
    conn = sqlite3.connect(DB_NAME)
    try:
        buffer = io.BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=legal, topMargin=15, bottomMargin=15, leftMargin=30, rightMargin=30); elements = []; styles = getSampleStyleSheet()
        s_title = ParagraphStyle(name='Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=11, fontName='Helvetica-Bold')
        s_h = ParagraphStyle(name='H', parent=styles['Normal'], fontSize=8, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER)
        s_c = ParagraphStyle(name='C', parent=styles['Normal'], fontSize=7, alignment=TA_LEFT)
        
        elements.append(get_header_table("INFORMACIÓN DE RIESGOS LABORALES (IRL) - DS 44", "RG-GD-04")); elements.append(Spacer(1, 10))
        elements.append(Paragraph("<b>1. IDENTIFICACIÓN</b>", s_title))
        data_id = [["EMPRESA:", "SOCIEDAD MADERERA GALVEZ Y DI GÉNOVA LTDA", "RUT:", "77.110.060-0"], ["DIRECCIÓN:", "RUTA INT. 215 KM12, OSORNO", "REP. LEGAL:", "PAOLA DI GÉNOVA"], ["TRABAJADOR:", data['nombre_trabajador'], "RUT:", data['rut_trabajador']], ["CARGO:", data['cargo_trabajador'], "FECHA:", datetime.now().strftime("%d/%m/%Y")], ["ÁREA:", data['espacio'][:40], "ESTATUS:", data['estatus']]]
        t_id = Table(data_id, colWidths=[50, 250, 40, 150]); t_id.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black), ('FONTSIZE', (0,0), (-1,-1), 7), ('BACKGROUND', (0,0), (1,-1), colors.whitesmoke)])); elements.append(t_id); elements.append(Spacer(1, 15))

        elements.append(Paragraph("<b>2. RIESGOS Y MEDIDAS (DS 44)</b>", s_title)); elements.append(Spacer(1, 5))
        # Buscar riesgos especificos en DB
        riesgos = conn.execute("SELECT peligro, riesgo, consecuencia, medida_control, metodo_correcto FROM matriz_iper WHERE cargo_asociado=?", (data['cargo_trabajador'],)).fetchall()
        if not riesgos: 
             # Fallback
             riesgos = conn.execute("SELECT peligro, riesgo, consecuencia, medida_control, metodo_correcto FROM matriz_iper WHERE cargo_asociado='OPERADOR DE MAQUINARIA'").fetchall()

        if riesgos:
            h_r = [Paragraph("RIESGO", s_h), Paragraph("CONSECUENCIA", s_h), Paragraph("MEDIDA", s_h), Paragraph("MÉTODO", s_h)]
            d_r = [h_r]
            for r in riesgos:
                d_r.append([Paragraph(f"<b>{r[0]}</b><br/>{r[1]}", s_c), Paragraph(r[2], s_c), Paragraph(r[3], s_c), Paragraph(r[4], s_c)])
            t_r = Table(d_r, colWidths=[120, 90, 150, 180], repeatRows=1)
            t_r.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), G_CORP), ('TEXTCOLOR', (0,0), (-1,0), G_WHITE), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
            elements.append(t_r)
        
        elements.append(Spacer(1, 15))
        elements.append(Paragraph("<b>3. CARACTERÍSTICAS DEL LUGAR</b>", s_title))
        elements.append(Paragraph(f"Espacio: {data['espacio']} | Ambiente: {data['ambiente']} | Maquinaria: {data['maquinas']}", s_c))
        
        elements.append(Spacer(1, 30))
        t_f = Table([["__________________________", "__________________________"], ["FIRMA RELATOR", "FIRMA TRABAJADOR"]], colWidths=[250, 250]); t_f.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')])); elements.append(t_f)
        doc.build(elements); buffer.seek(0); conn.close(); return buffer
    except: return None
    finally: conn.close()


# ==============================================================================
# 4. FRONTEND
# ==============================================================================
st.set_page_config(page_title="ERP SGSST - G&D", layout="wide")
init_erp_db()

if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'user_role': None, 'username': None})

if not st.session_state['logged_in']:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("<h1 style='text-align: center;'>🔐 Acceso Corporativo</h1>", unsafe_allow_html=True); user = st.text_input("Usuario"); pwd = st.text_input("Contraseña", type="password")
        if st.button("Iniciar Sesión", use_container_width=True):
            role = login_user(user, pwd)
            if role: st.session_state.update({'logged_in': True, 'user_role': role, 'username': user}); st.rerun()
            else: st.error("Credenciales incorrectas")
    st.stop()

with st.sidebar:
    st.title("MADERAS G&D"); st.success(f"Usuario: {st.session_state['username']}")
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()
    st.divider()
    up_logo = st.file_uploader("Logo Empresa", type=['png', 'jpg'])
    if up_logo: 
        with open("logo_empresa.png", "wb") as f: f.write(up_logo.getbuffer())
        st.success("Logo guardado.")
    menu = st.radio("MÓDULOS:", ["📊 Dashboard BI", "👥 Nómina & Personal", "📱 App Móvil", "🎓 Gestión Capacitación", "🦺 Registro EPP", "📘 Entrega RIOHS", "📄 Generador IRL", "⚠️ Matriz IPER"])
    if st.session_state['user_role'] == "ADMINISTRADOR": menu = st.radio("ADMIN:", ["🔐 Gestión Usuarios"]) if menu == "🔐 Gestión Usuarios" else menu

if menu == "👥 Nómina & Personal":
    st.title("Base de Datos Maestra de Personal")
    tab1, tab2, tab3 = st.tabs(["📋 Lista", "➕ Nuevo", "📂 Carga Masiva"])
    conn = sqlite3.connect(DB_NAME)
    with tab1: st.dataframe(pd.read_sql("SELECT * FROM personal", conn))
    with tab2:
        with st.form("new_p"):
            r = st.text_input("RUT"); n = st.text_input("Nombre"); c = st.selectbox("Cargo", LISTA_CARGOS)
            if st.form_submit_button("Guardar"):
                conn.execute("INSERT OR REPLACE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (r, n, c, "FAENA", date.today(), "ACTIVO")); conn.commit(); st.success("Guardado")
    with tab3:
        st.info("Carga Masiva Excel"); up = st.file_uploader("Excel", type=['xlsx'])
        if up: st.success("Procesado (Simulado)") 
    conn.close()

elif menu == "🎓 Gestión Capacitación":
    st.title("Gestión Capacitación"); tab1, tab2, tab3 = st.tabs(["📅 Nueva", "✍️ Firmar", "🗂️ Historial"])
    conn = sqlite3.connect(DB_NAME)
    if 'cam_open' not in st.session_state: st.session_state.cam_open = False
    if 'img_cache' not in st.session_state: st.session_state.img_cache = None

    with tab1:
        c1, c2 = st.columns(2); fec = c1.date_input("Fecha"); hi = c2.time_input("Inicio", value=datetime.now().time())
        ht = c1.time_input("Término", value=(datetime.now()+timedelta(hours=1)).time()); tem = st.text_area("Tema"); rel = st.text_input("Relator")
        if st.button("📸 ACTIVAR CÁMARA"): st.session_state.cam_open = True; st.rerun()
        if st.session_state.cam_open:
            img = st.camera_input("Foto")
            if img: st.session_state.img_cache = img; st.session_state.cam_open = False; st.rerun()
        if st.session_state.img_cache: st.success("IMAGEN TOMADA CON EXITO")
        if st.button("💾 PROGRAMAR"):
            istr = base64.b64encode(st.session_state.img_cache.getvalue()).decode() if st.session_state.img_cache else None
            conn.execute("INSERT INTO capacitaciones (fecha, responsable, hora_inicio, hora_termino, tema, estado, evidencia_foto_b64) VALUES (?,?,?,?,?,?,?)", (fec, rel, str(hi), str(ht), tem, "PROGRAMADA", istr)); conn.commit(); st.success("CAPACITACION PROGRAMADA CON EXITO"); st.session_state.img_cache = None
    with tab3:
        df = pd.read_sql("SELECT * FROM capacitaciones", conn); st.dataframe(df)
        sid = st.selectbox("ID PDF", df['id'].tolist() if not df.empty else [])
        if st.button("Generar PDF"):
            pdf = generar_pdf_asistencia_rggd02(sid)
            if pdf: st.download_button("Descargar", pdf, "cap.pdf")
    conn.close()

elif menu == "📄 Generador IRL":
    st.title("Generador IRL (DS 44)")
    conn = sqlite3.connect(DB_NAME); trab = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    sel = st.selectbox("Trabajador", trab['rut'] + " - " + trab['nombre'])
    
    if sel:
        rut = sel.split(" - ")[0]; row = trab[trab['rut']==rut].iloc[0]
        base = IRL_DATA_DB.get(row['cargo'], IRL_DATA_DB["DEFAULT"])
        
        with st.form("irl"):
            c1, c2 = st.columns(2); fi = c1.date_input("Inicio"); ft = c2.date_input("Fin"); dur = c1.text_input("Duración", "1h"); rel = c2.text_input("Relator"); mod = c1.selectbox("Modalidad", ["Presencial", "Online"])
            st.markdown("### Contenidos"); esp = st.text_area("Espacio", base['espacio']); amb = st.text_area("Ambiente", base['ambiente']); ord = st.text_area("Orden", base['orden']); maq = st.text_area("Maquinas", base['maquinas'])
            st_user = st.selectbox("Estatus", ["Nuevo", "Reinduccion"]); sub = st.form_submit_button("Generar")
        
        if sub:
            data = {'rut_trabajador': rut, 'nombre_trabajador': row['nombre'], 'cargo_trabajador': row['cargo'],
                    'fecha_inicio': fi, 'fecha_termino': ft, 'duracion': dur, 'relator': rel, 'cargo_relator': "APR",
                    'modalidad': mod, 'espacio': esp, 'ambiente': amb, 'orden': ord, 'maquinas': maq,
                    'estatus': st_user, 'material': False, 'material_nombre': ''}
            pdf = generar_pdf_irl(data)
            if pdf: st.download_button("Descargar IRL", pdf, f"IRL_{rut}.pdf", "application/pdf")
    conn.close()

elif menu == "⚠️ Matriz IPER":
    st.title("Matriz de Riesgos"); conn = sqlite3.connect(DB_NAME)
    c_filter = st.multiselect("Filtrar Cargo:", LISTA_CARGOS)
    q = "SELECT * FROM matriz_iper"
    if c_filter: q += f" WHERE cargo_asociado IN ({','.join(['?']*len(c_filter))})"
    df = pd.read_sql(q, conn, params=c_filter) if c_filter else pd.read_sql(q, conn)
    
    edited = st.data_editor(df, num_rows="dynamic", key="miper_edit")
    if st.button("💾 Guardar Cambios"):
        edited.to_sql("matriz_iper", conn, if_exists="replace", index=False); st.success("Guardado")
    conn.close()

elif menu == "🦺 Registro EPP":
    st.title("Entrega EPP"); conn = sqlite3.connect(DB_NAME); users = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    u = st.selectbox("Trabajador", users['nombre'])
    if 'epp_list' not in st.session_state: st.session_state.epp_list = []
    c1, c2 = st.columns(2); p = c1.selectbox("Producto", LISTA_EPP); c = c2.number_input("Cant", 1)
    if st.button("Agregar"): st.session_state.epp_list.append([p, c])
    st.table(st.session_state.epp_list); sig = st_canvas(stroke_width=2, height=150, key="epp_sig")
    if st.button("Guardar"):
        if sig.image_data is not None:
            gid = str(uuid.uuid4()); rut = users[users['nombre']==u]['rut'].values[0]; car = users[users['nombre']==u]['cargo'].values[0]; img = Image.fromarray(sig.image_data.astype('uint8')); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
            for i in st.session_state.epp_list: conn.execute("INSERT INTO registro_epp (grupo_id, rut_trabajador, nombre_trabajador, cargo_trabajador, producto, quantity, fecha_entrega, firma_trabajador_b64) VALUES (?,?,?,?,?,?,?,?)", (gid, rut, u, car, i[0], i[1], date.today(), ib64))
            conn.commit(); st.success("Guardado"); st.session_state.epp_list = []
    conn.close()

elif menu == "📘 Entrega RIOHS":
    st.title("Entrega RIOHS"); conn = sqlite3.connect(DB_NAME); users = pd.read_sql("SELECT rut, nombre FROM personal", conn); sel = st.selectbox("Trabajador", users['nombre'])
    sig = st_canvas(stroke_width=2, height=150, key="riohs_sig")
    if st.button("Registrar"):
        if sig.image_data is not None:
            rut = users[users['nombre']==sel]['rut'].values[0]; img = Image.fromarray(sig.image_data.astype('uint8')); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
            conn.execute("INSERT INTO entrega_riohs (rut_trabajador, nombre_trabajador, fecha_entrega, firma_trabajador_b64) VALUES (?,?,?,?)", (rut, sel, date.today(), ib64)); conn.commit(); st.success("Registrado")
    conn.close()
    
elif menu == "📊 Dashboard BI":
    if 'df_main' not in st.session_state: st.session_state['df_main'] = load_data()
    st.title("Dashboard BI"); st.dataframe(st.session_state['df_main'].head())
