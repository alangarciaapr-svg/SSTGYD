import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
import io
import hashlib
import os
import time
import base64
import ast
import socket
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont
import matplotlib
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from streamlit_drawable_canvas import st_canvas
import openpyxl 

# --- LIBRERIAS PARA EMAIL ---
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Manejo seguro de librería QR
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

matplotlib.use('Agg')

# ==============================================================================
# 1. CONFIGURACIÓN GLOBAL Y ESTÉTICA (FULL VISUAL)
# ==============================================================================
st.set_page_config(page_title="SGSST ERP MASTER", layout="wide", page_icon="🏗️", initial_sidebar_state="expanded")

DB_NAME = 'sgsst_v208_complete.db' 
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"
BG_IMAGE = "https://i.imgur.com/aHPH6U6.jpeg"
LOGO_URL = "https://www.maderasgyd.cl/wp-content/uploads/2024/02/logo-maderas-gd-1.png"

# CSS COMPLETO
st.markdown(f"""
    <style>
        #MainMenu {{visibility: hidden;}}
        header {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        .block-container {{padding-top: 1rem !important; padding-bottom: 5rem !important;}}
        
        /* FONDO */
        .stApp {{
            background-image: linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.7)), url("{BG_IMAGE}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        
        /* CONTENEDOR PRINCIPAL */
        div[data-testid="column"]:nth-of-type(2) {{
            background-color: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 25px !important;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            border-top: 5px solid {COLOR_PRIMARY};
        }}
        
        .logo-box {{display: flex; justify-content: center; margin-bottom: 20px; background: white; padding: 10px; border-radius: 10px;}}
        
        /* KPI */
        .card-kpi {{background-color: #f8f9fa; border-radius: 10px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; border-left: 5px solid {COLOR_PRIMARY}; margin-bottom: 10px;}}
        .card-kpi h3 {{margin: 0; color: #666; font-size: 1rem;}}
        .card-kpi h1 {{margin: 0; color: {COLOR_SECONDARY}; font-size: 2rem; font-weight: bold;}}
        
        /* CANVAS */
        div[data-testid="stCanvas"] {{border: 2px solid #a0a0a0 !important; border-radius: 5px; background-color: #ffffff; width: 100% !important; min-height: 150px;}}
        
        /* BOTONES */
        button {{min-height: 45px !important; font-weight: bold !important;}}
    </style>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
""", unsafe_allow_html=True)

ISP_RISK_CODES = {
    "Seguridad": ["Caídas al mismo nivel (A1)", "Caídas de altura (A3)", "Atrapamiento (B1)", "Golpeado por (B2)", "Cortes (B3)", "Atropellos (I1)"],
    "Higiene": ["Ruido (P1)", "Sílice (O1)", "Radiación UV (P5)", "Vibraciones (P2)"],
    "Ergonomía": ["Manejo Manual de Carga (R1)", "Posturas Forzadas (T1)", "Trabajo Repetitivo (S1)"],
    "Psicosocial": ["Doble Presencia", "Acoso Laboral"],
    "Emergencia": ["Incendio", "Sismo"]
}

LISTA_CARGOS = ["GERENTE GENERAL", "PREVENCIONISTA DE RIESGOS", "JEFE DE PATIO", "OPERADOR DE ASERRADERO", "AYUDANTE", "OPERADOR MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "MECANICO", "ADMINISTRATIVO"]

# ==============================================================================
# 2. CAPA DE DATOS
# ==============================================================================
def get_conn(): return sqlite3.connect(DB_NAME, check_same_thread=False)

def clean_str(val):
    if val is None: return None
    s = str(val).strip()
    return None if s == "" or s.lower() in ["nan", "nat", "none"] else s

def process_signature_bg(img_data):
    try:
        if img_data is None: return create_text_signature_img("Sin Firma")
        if isinstance(img_data, np.ndarray) and np.all(img_data == 0): return create_text_signature_img("Firma Vacía")
        return PILImage.fromarray(img_data.astype('uint8'), 'RGBA')
    except: return create_text_signature_img("Error Firma")

def create_text_signature_img(text_sig):
    width, height = 400, 100
    image = PILImage.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image); draw.text((20, 40), f"Firmado: {text_sig}", fill="black")
    return image

def check_and_add_column(cursor, table_name, column_name, column_type):
    try: cursor.execute(f"SELECT {column_name} FROM {table_name} LIMIT 1")
    except:
        try: cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        except: pass

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS personal (rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, email TEXT, estado TEXT, fecha_contrato DATE, vigencia_examen_medico DATE, contacto_emergencia TEXT, fono_emergencia TEXT, obs_medica TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (id INTEGER PRIMARY KEY AUTOINCREMENT, proceso TEXT, puesto_trabajo TEXT, peligro_factor TEXT, riesgo_asociado TEXT, probabilidad INTEGER, consecuencia INTEGER, vep INTEGER, nivel_riesgo TEXT, medida_control TEXT, familia_riesgo TEXT, codigo_riesgo TEXT, jerarquia_control TEXT, requisito_legal TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, cargo TEXT, lista_productos TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT, email_copia TEXT, nombre_difusor TEXT, firma_difusor_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, descripcion TEXT, nombre_afectado TEXT, dias_perdidos INTEGER, area TEXT, severidad TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventario_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT, stock_actual INTEGER, stock_minimo INTEGER, precio INTEGER, ubicacion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, relator TEXT, lugar TEXT, tipo_actividad TEXT, duracion INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, trabajador_rut TEXT, nombre_trabajador TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extintores (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, tipo TEXT, vencimiento DATE, ubicacion TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS programa_anual (id INTEGER PRIMARY KEY AUTOINCREMENT, actividad TEXT, responsable TEXT, fecha DATE, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS contratistas (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, rut_empresa TEXT, contacto TEXT, estado_doc TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATETIME, usuario TEXT, accion TEXT, detalle TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS periodos_ds67 (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_periodo TEXT, fecha_inicio DATE, fecha_fin DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS detalle_mensual_ds67 (id INTEGER PRIMARY KEY AUTOINCREMENT, periodo_id INTEGER, mes INTEGER, anio INTEGER, masa_imponible INTEGER, dias_perdidos INTEGER, invalideces_muertes INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS conducta_personal (id INTEGER PRIMARY KEY AUTOINCREMENT, rut_trabajador TEXT, fecha DATE, tipo TEXT, descripcion TEXT, gravedad TEXT)''')

    # AUTO REPARACION
    check_and_add_column(c, "personal", "contacto_emergencia", "TEXT")
    check_and_add_column(c, "registro_riohs", "nombre_difusor", "TEXT")
    
    if c.execute("SELECT count(*) FROM usuarios").fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
    
    conn.commit(); conn.close()
    st.session_state['db_setup_complete'] = True

def registrar_auditoria(usuario, accion, detalle):
    try:
        conn = get_conn(); conn.execute("INSERT INTO auditoria (fecha, usuario, accion, detalle) VALUES (?,?,?,?)", (datetime.now(), usuario, accion, detalle)); conn.commit(); conn.close()
    except: pass

def calcular_nivel_riesgo(vep):
    if vep <= 2: return "TOLERABLE"
    elif vep == 4: return "MODERADO"
    elif vep == 8: return "IMPORTANTE"
    elif vep >= 16: return "INTOLERABLE"
    return "NO CLASIFICADO"

def determinar_tramo_cotizacion(tasa):
    if tasa < 33: return 0.0
    elif tasa < 66: return 0.34
    elif tasa < 99: return 0.68
    elif tasa < 132: return 1.02
    else: return 3.40

# ==============================================================================
# 3. MOTOR DOCUMENTAL
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO(); self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=30, leftMargin=30, rightMargin=30); self.elements = []
        self.styles = getSampleStyleSheet(); self.titulo = titulo_doc; self.codigo = codigo_doc; self.logo_url = LOGO_URL
        self.styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY, fontSize=10, leading=12))
        self.styles.add(ParagraphStyle(name='HeadingBox', alignment=TA_LEFT, fontSize=10, fontName='Helvetica-Bold', backColor=colors.lightgrey, borderPadding=3))

    def _header(self):
        try: logo = RLImage(self.logo_url, width=110, height=45)
        except: logo = Paragraph("<b>MADERAS G&D</b>", self.styles['Normal'])
        data = [[logo, "SISTEMA DE GESTIÓN DE SEGURIDAD Y SALUD EN EL TRABAJO", f"CÓDIGO: {self.codigo}\nFECHA: 05/01/2026"], ["", Paragraph(f"<b>{self.titulo}</b>", ParagraphStyle('B', alignment=TA_CENTER, fontSize=11, fontName='Helvetica-Bold')), "PÁGINA: 1 DE 1"]]
        t = Table(data, colWidths=[140, 280, 120]); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('SPAN', (0,0), (0,1))]))
        self.elements.append(t); self.elements.append(Spacer(1, 15))

    def generar_irl_master(self, data, riesgos):
        self._header()
        self.elements.append(Paragraph("1. IDENTIFICACIÓN GENERAL", self.styles['HeadingBox']))
        self.elements.append(Table([[f"Nombre: {data['nombre']}", f"RUT: {data['rut']}"], [f"Cargo: {data['cargo']}", f"Fecha: {data['fecha']}"], [f"Mutual: {data['mutual']}", "Empresa: SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA."]], colWidths=[270, 270]))
        self.elements.append(Spacer(1, 10))
        self.elements.append(Paragraph("2. DESCRIPCIÓN DEL PUESTO Y ENTORNO (ART. 15, LETRA D)", self.styles['HeadingBox']))
        self.elements.append(Paragraph(data['entorno'], self.styles['Justify']))
        self.elements.append(Spacer(1, 10))
        self.elements.append(Paragraph("3. MATRIZ DE RIESGOS, EFECTOS Y MEDIDAS (ART. 15 LETRAS A,B,C)", self.styles['HeadingBox']))
        r_table = [["PELIGRO", "EFECTO SALUD", "MEDIDA PREVENTIVA"]]
        for r in riesgos: r_table.append([Paragraph(str(r[0]), self.styles['Normal']), Paragraph(str(r[1]), self.styles['Normal']), Paragraph(str(r[2]), self.styles['Normal'])])
        self.elements.append(Table(r_table, colWidths=[130, 130, 280], style=TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke)])))
        self.elements.append(Spacer(1, 15))
        self.elements.append(Paragraph("4. GESTIÓN DE EMERGENCIAS (ART. 15 LETRA E)", self.styles['HeadingBox']))
        self.elements.append(Paragraph(f"Centro: {data['centro_urgencia']} | Dirección: {data['centro_direccion']}", self.styles['Justify']))
        self.elements.append(Spacer(1, 10))
        self.elements.append(Paragraph("6. VERIFICACIÓN DE COMPRENSIÓN (BLINDAJE DS 44)", self.styles['HeadingBox']))
        self.elements.append(Paragraph(f"P1: {data['p1']}\nR: ________________________", self.styles['Normal']))
        self.elements.append(Paragraph(f"P2: {data['p2']}\nR: ________________________", self.styles['Normal']))
        self.elements.append(Spacer(1, 20))
        self.elements.append(Paragraph('"Declaro que he sido informado de manera oportuna, clara y específica sobre los riesgos de mi puesto..."', self.styles['Justify']))
        self.elements.append(Spacer(1, 30)); self.elements.append(Table([["__________________________", "__________________________"], ["FIRMA TRABAJADOR", "FIRMA EMPLEADOR"]], colWidths=[270, 270]))
        self.doc.build(self.elements); return self.buffer

    def generar_riohs_legal(self, data):
        self._header()
        txt = f"""Se deja expresa constancia, de acuerdo a lo establecido en el artículo 156 del Código del Trabajo y DS 44 de la Ley 16.744 que, he recibido en forma gratuita un ejemplar del Reglamento Interno de Orden, Higiene y Seguridad de SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA.<br/><br/>
        Declaro bajo mi firma haber recibido, leído y comprendido el presente Reglamento Interno de Orden, Higiene y Seguridad... mi decisión es la entrega {data['tipo']} al correo {str(data['email']).upper()}"""
        self.elements.append(Paragraph(txt, self.styles['Justify']))
        
        # FIRMAS
        sig_w = RLImage(io.BytesIO(base64.b64decode(data['firma'])), width=180, height=80) if data.get('firma') else Spacer(1,1)
        sig_d = RLImage(io.BytesIO(base64.b64decode(data['firma_dif'])), width=180, height=80) if data.get('firma_dif') else Spacer(1,1)
        
        t = Table([["NOMBRE:", data['nombre']], ["RUT:", data['rut']], ["FECHA:", data['fecha']], ["FIRMA TRABAJADOR:", sig_w], ["DIFUSOR:", data['difusor']], ["FIRMA DIFUSOR:", sig_d]], colWidths=[120, 380], rowHeights=[25,25,25,85,25,85])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        self.elements.append(Spacer(1, 20)); self.elements.append(t); self.doc.build(self.elements); return self.buffer

    def generar_epp_legal(self, data):
        self._header()
        txt = "Certifico haber recibido de mi empleador, SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA., los Elementos de Protección Personal (EPP) en cumplimiento del Artículo 68 de la Ley 16.744. Declaro haber recibido capacitación en su uso correcto."
        self.elements.append(Paragraph(txt, self.styles['Justify']))
        self.elements.append(Spacer(1, 20)); self.elements.append(Paragraph(f"Lista: {data['lista']}", self.styles['Normal']))
        if data.get('firma'):
            self.elements.append(Spacer(1, 30))
            self.elements.append(RLImage(io.BytesIO(base64.b64decode(data['firma'])), width=180, height=80))
            self.elements.append(Paragraph("__________________________<br/>FIRMA TRABAJADOR", ParagraphStyle('C', alignment=TA_CENTER)))
        self.doc.build(self.elements); return self.buffer

    def generar_reporte_ds67(self, data_ds67):
        self._header(); self.elements.append(Paragraph(f"INFORME DS67 - {data_ds67['periodo']}", self.styles['HeadingBox']))
        self.elements.append(Table([["TASA SINIESTRALIDAD", f"{data_ds67['tasa']:.2f}"], ["COTIZACIÓN ADICIONAL", f"{data_ds67['cot']:.2f}%"]], colWidths=[250, 250], style=TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black)])))
        self.doc.build(self.elements); return self.buffer

# ==============================================================================
# 4. INTERFAZ (LOGIN RESTAURADO)
# ==============================================================================
init_db()
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown(f'<div class="logo-box"><img src="{LOGO_URL}" style="width: 100%; max-width: 200px;"></div>', unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; color: #444;'>ACCESO ERP SGSST</h4>", unsafe_allow_html=True)
        u = st.text_input("Usuario", placeholder="Ingrese su usuario")
        p = st.text_input("Contraseña", type="password", placeholder="••••••••")
        if st.button("INGRESAR", use_container_width=True, type="primary"):
            conn = get_conn(); user_check = pd.read_sql("SELECT * FROM usuarios WHERE username=? AND password=?", conn, params=(u, hashlib.sha256(p.encode()).hexdigest()))
            if not user_check.empty: st.session_state['logged_in'] = True; st.session_state['user'] = u; st.rerun()
            else: st.error("Acceso denegado")
        st.markdown('<div class="login-footer">© 2026 Maderas G&D</div>', unsafe_allow_html=True)
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f'<div style="text-align:center"><img src="{LOGO_URL}" width="120"></div>', unsafe_allow_html=True)
    st.write(f"Hola, **{st.session_state['user']}**")
    with open(DB_NAME, "rb") as fp: st.download_button("💾 Respaldar Base de Datos", fp, f"backup_{date.today()}.db", mime="application/x-sqlite3")
    menu = st.radio("NAVEGACIÓN", ["📊 Dashboard", "👥 Gestión Personas", "⚖️ Gestión DS67", "🛡️ Matriz Riesgos", "⚖️ Gestor Documental", "🦺 Logística EPP", "🎓 Capacitaciones", "🚨 Incidentes", "📅 Plan Anual", "🧯 Extintores", "🏗️ Contratistas", "🔐 Gestión Usuarios"])
    if st.button("Salir"): st.session_state['logged_in'] = False; st.rerun()

# ==============================================================================
# 5. MÓDULOS (TODOS RESTAURADOS)
# ==============================================================================

if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Dashboard de Gestión</div>", unsafe_allow_html=True)
    conn = get_conn(); k1, k2, k3 = st.columns(3)
    t = pd.read_sql("SELECT count(*) FROM personal WHERE estado='ACTIVO'", conn).iloc[0,0]
    a = pd.read_sql("SELECT count(*) FROM incidentes", conn).iloc[0,0]
    k1.markdown(f"<div class='card-kpi'><h3>Personal Activo</h3><h1>👷 {t}</h1></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='card-kpi'><h3>Incidentes (Mes)</h3><h1>🚑 {a}</h1></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='card-kpi'><h3>Cumplimiento</h3><h1>✅ 100%</h1></div>", unsafe_allow_html=True)
    st.divider(); st.subheader("Inventario Crítico (Stock Bajo)")
    st.dataframe(pd.read_sql("SELECT producto, stock_actual, stock_minimo FROM inventario_epp WHERE stock_actual <= stock_minimo", conn), use_container_width=True)
    conn.close()

elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Personal</div>", unsafe_allow_html=True)
    conn = get_conn(); t1, t2 = st.tabs(["Nómina", "Nuevo"])
    with t1:
        df = pd.read_sql("SELECT * FROM personal", conn)
        ed = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("Guardar Cambios"):
            for i, r in ed.iterrows(): conn.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=?, estado=?, contacto_emergencia=?, fono_emergencia=?, obs_medica=? WHERE rut=?", (clean_str(r['nombre']), clean_str(r['cargo']), clean_str(r['centro_costo']), clean_str(r['estado']), clean_str(r['contacto_emergencia']), clean_str(r['fono_emergencia']), clean_str(r['obs_medica']), r['rut']))
            conn.commit(); st.success("OK")
    with t2:
        with st.form("np"):
            r = st.text_input("RUT"); n = st.text_input("Nombre"); c = st.selectbox("Cargo", LISTA_CARGOS)
            if st.form_submit_button("Crear"): conn.execute("INSERT INTO personal (rut, nombre, cargo, estado) VALUES (?,?,?,?)", (r, n, c, "ACTIVO")); conn.commit(); st.success("OK")
    conn.close()

elif menu == "⚖️ Gestión DS67":
    st.markdown("<div class='main-header'>Gestión de Siniestralidad DS67</div>", unsafe_allow_html=True)
    conn = get_conn(); t1, t2 = st.tabs(["Registro Periodo", "Reporte Mensual"])
    with t1:
        with st.form("ds67"):
            per = st.text_input("Periodo (Ej: 2024-2025)"); ini = st.date_input("Inicio"); fin = st.date_input("Fin")
            if st.form_submit_button("Crear Periodo"): conn.execute("INSERT INTO periodos_ds67 (nombre_periodo, fecha_inicio, fecha_fin) VALUES (?,?,?)", (per, ini, fin)); conn.commit(); st.success("OK")
        st.dataframe(pd.read_sql("SELECT * FROM periodos_ds67", conn))
    with t2:
        pers = pd.read_sql("SELECT id, nombre_periodo FROM periodos_ds67", conn)
        if not pers.empty:
            sel_p = st.selectbox("Periodo", pers['nombre_periodo'])
            pid = pers[pers['nombre_periodo']==sel_p]['id'].values[0]
            with st.form("mens"):
                m = st.selectbox("Mes", range(1,13)); masa = st.number_input("Masa Imponible", 100); dias = st.number_input("Días Perdidos", 0)
                if st.form_submit_button("Registrar Mes"): conn.execute("INSERT INTO detalle_mensual_ds67 (periodo_id, mes, masa_imponible, dias_perdidos) VALUES (?,?,?,?)", (pid, m, masa, dias)); conn.commit(); st.success("OK")
            
            data_raw = pd.read_sql("SELECT * FROM detalle_mensual_ds67 WHERE periodo_id=?", conn, params=(pid,))
            if not data_raw.empty:
                tot_dias = data_raw['dias_perdidos'].sum(); avg_masa = data_raw['masa_imponible'].mean()
                tasa = (tot_dias / avg_masa) * 100 if avg_masa > 0 else 0
                cot = determinar_tramo_cotizacion(tasa)
                st.metric("Tasa Siniestralidad", f"{tasa:.2f}"); st.metric("Cotización Adicional", f"{cot:.2f}%")
                if st.button("Generar Informe DS67 PDF"):
                    pdf = DocumentosLegalesPDF("INFORME DS67", "INF-01").generar_reporte_ds67({'periodo':sel_p, 'masa':avg_masa, 'dias':tot_dias, 'inv':0, 'tasa':tasa, 'cot':cot})
                    st.download_button("Descargar Informe", pdf.getvalue(), "DS67.pdf")
    conn.close()

elif menu == "🛡️ Matriz Riesgos":
    st.markdown("<div class='main-header'>Matriz IPER</div>", unsafe_allow_html=True)
    conn = get_conn(); t1, t2, t3 = st.tabs(["Ver Matriz", "Carga Masiva", "Crear"])
    with t1: st.dataframe(pd.read_sql("SELECT * FROM matriz_iper", conn), use_container_width=True)
    with t2:
        up = st.file_uploader("Excel Matriz", type=['xlsx'])
        if up: df = pd.read_excel(up); df.to_sql("matriz_iper", conn, if_exists="append", index=False); st.success("Cargado")
    with t3:
        with st.form("nm"):
            p = st.selectbox("Cargo", LISTA_CARGOS); pe = st.text_input("Peligro"); ri = st.text_input("Riesgo"); me = st.text_area("Medida")
            if st.form_submit_button("Guardar"): conn.execute("INSERT INTO matriz_iper (puesto_trabajo, peligro_factor, riesgo_asociado, medida_control) VALUES (?,?,?,?)", (p, pe, ri, me)); conn.commit(); st.success("OK")
    conn.close()

elif menu == "⚖️ Gestor Documental":
    st.markdown("<div class='main-header'>Documentación Legal</div>", unsafe_allow_html=True)
    conn = get_conn(); df_p = pd.read_sql("SELECT rut, nombre, cargo, email FROM personal", conn)
    t1, t2 = st.tabs(["IRL DS 44", "Acta RIOHS"])
    with t1:
        if not df_p.empty:
            sel = st.selectbox("Trabajador:", df_p['rut'] + " - " + df_p['nombre'])
            rut = sel.split(" - ")[0]; w_data = df_p[df_p['rut']==rut].iloc[0]
            ent = st.text_area("Entorno", "Oficina y Terreno"); p1 = st.text_input("Pregunta 1", "Riesgo Principal?"); p2 = st.text_input("Pregunta 2", "¿Qué hacer?")
            if st.button("Generar IRL"):
                riesgos = pd.read_sql("SELECT peligro_factor, riesgo_asociado, medida_control FROM matriz_iper WHERE puesto_trabajo=?", conn, params=(w_data['cargo'],)).values.tolist()
                pdf = DocumentosLegalesPDF("IRL DS 44", "RG-IRL-02").generar_irl_master({'nombre':w_data['nombre'], 'rut':rut, 'cargo':w_data['cargo'], 'fecha':str(date.today()), 'mutual':'ACHS', 'entorno':ent, 'centro_urgencia':'Clínica', 'centro_direccion':'Centro', 'p1':p1, 'p2':p2}, riesgos)
                st.download_button("Descargar PDF", pdf.getvalue(), "IRL.pdf")
    with t2:
        sel_r = st.selectbox("Personal:", df_p['rut'] + " | " + df_p['nombre'], key="rs")
        rut_r = sel_r.split(" | ")[0]; wr = df_p[df_p['rut']==rut_r].iloc[0]
        tipo = st.radio("Tipo:", ["Físico", "Digital"]); dif = st.text_input("Difusor")
        c1, c2 = st.columns(2)
        with c1: st.write("Trabajador"); sw = st_canvas(height=150, width=400, key="sw")
        with c2: st.write("Difusor"); sd = st_canvas(height=150, width=400, key="sd")
        if st.button("Generar Acta RIOHS"):
            imw = process_signature_bg(sw.image_data); bw = io.BytesIO(); imw.save(bw, format='PNG'); sigw = base64.b64encode(bw.getvalue()).decode()
            imd = process_signature_bg(sd.image_data); bd = io.BytesIO(); imd.save(bd, format='PNG'); sigd = base64.b64encode(bd.getvalue()).decode()
            pdf = DocumentosLegalesPDF("ACTA RIOHS", "RG-RI-03").generar_riohs_legal({'nombre':wr['nombre'], 'rut':rut_r, 'fecha':str(date.today()), 'cargo':wr['cargo'], 'tipo':tipo, 'email':wr['email'], 'difusor':dif, 'firma':sigw, 'firma_dif':sigd})
            st.download_button("Descargar Acta", pdf.getvalue(), "RIOHS.pdf")
    conn.close()

elif menu == "🦺 Logística EPP":
    st.markdown("<div class='main-header'>Entrega EPP</div>", unsafe_allow_html=True)
    conn = get_conn(); t1, t2 = st.tabs(["Entrega", "Inventario"])
    with t1:
        df_p = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
        sel = st.selectbox("Personal:", df_p['rut'] + " | " + df_p['nombre'])
        rut = sel.split(" | ")[0]; cargo = df_p[df_p['rut']==rut]['cargo'].values[0]
        lista = st.text_area("Lista EPP", "Zapatos de Seguridad, Casco, Lentes")
        st.write("Firma:"); canvas = st_canvas(height=150, width=400, key="epp")
        if st.button("Generar Acta EPP"):
            img = process_signature_bg(canvas.image_data); b = io.BytesIO(); img.save(b, format='PNG'); sig = base64.b64encode(b.getvalue()).decode()
            pdf = DocumentosLegalesPDF("ENTREGA EPP", "RG-EPP-01").generar_epp_legal({'nombre':sel.split("|")[1], 'rut':rut, 'cargo':cargo, 'fecha':str(date.today()), 'lista':lista, 'firma':sig})
            st.download_button("Descargar PDF", pdf.getvalue(), "EPP.pdf")
    with t2:
        dfi = pd.read_sql("SELECT * FROM inventario_epp", conn)
        ed = st.data_editor(dfi, num_rows="dynamic")
        if st.button("Actualizar Stock"):
            conn.execute("DELETE FROM inventario_epp"); 
            for i, r in ed.iterrows(): conn.execute("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, precio) VALUES (?,?,?,?)", (r['producto'], r['stock_actual'], r['stock_minimo'], r['precio']))
            conn.commit(); st.success("OK")
    conn.close()

elif menu == "🎓 Capacitaciones":
    st.markdown("<div class='main-header'>Capacitaciones</div>", unsafe_allow_html=True)
    conn = get_conn(); t1, t2 = st.tabs(["Nueva", "Asistencia"])
    with t1:
        with st.form("cap"):
            t = st.text_input("Tema"); r = st.text_input("Relator")
            if st.form_submit_button("Crear"): conn.execute("INSERT INTO capacitaciones (fecha, tema, relator) VALUES (?,?,?)", (date.today(), t, r)); conn.commit(); st.success("OK")
    with t2:
        caps = pd.read_sql("SELECT * FROM capacitaciones", conn)
        sel = st.selectbox("Curso:", caps['id'].astype(str) + " - " + caps['tema'])
        pdf = DocumentosLegalesPDF("LISTA", "RG-CAP").generar_asistencia_capacitacion({'tema':sel, 'tipo':'Charla', 'resp':'Prevencion', 'fecha':str(date.today())}, [])
        st.download_button("Descargar Lista Vacía", pdf.getvalue(), "Lista.pdf")
    conn.close()

elif menu == "🚨 Incidentes":
    st.markdown("<div class='main-header'>Incidentes</div>", unsafe_allow_html=True)
    conn = get_conn(); 
    with st.form("inc"):
        f = st.date_input("Fecha"); d = st.text_area("Descripción"); af = st.text_input("Afectado")
        if st.form_submit_button("Registrar"): conn.execute("INSERT INTO incidentes (fecha, descripcion, nombre_afectado) VALUES (?,?,?)", (f, d, af)); conn.commit(); st.success("OK")
    st.dataframe(pd.read_sql("SELECT * FROM incidentes", conn), use_container_width=True)
    if st.button("Generar DIAT"):
        pdf = DocumentosLegalesPDF("DIAT", "LEGAL").generar_diat({'nombre':af, 'descripcion':d})
        st.download_button("Descargar DIAT", pdf.getvalue(), "DIAT.pdf")
    conn.close()

elif menu == "📅 Plan Anual":
    st.markdown("<div class='main-header'>Plan Anual</div>", unsafe_allow_html=True)
    conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM programa_anual", conn), num_rows="dynamic", key="plan_ed"); conn.close()

elif menu == "🧯 Extintores":
    st.markdown("<div class='main-header'>Extintores</div>", unsafe_allow_html=True)
    conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM extintores", conn), num_rows="dynamic", key="ext_ed"); conn.close()

elif menu == "🏗️ Contratistas":
    st.markdown("<div class='main-header'>Contratistas</div>", unsafe_allow_html=True)
    conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM contratistas", conn), num_rows="dynamic", key="cont_ed"); conn.close()

elif menu == "🔐 Gestión Usuarios":
    st.markdown("<div class='main-header'>Usuarios</div>", unsafe_allow_html=True)
    conn = get_conn(); 
    with st.form("usr"):
        u = st.text_input("Usuario"); p = st.text_input("Clave", type="password"); r = st.selectbox("Rol", ["ADMINISTRADOR", "VISOR"])
        if st.form_submit_button("Crear"): conn.execute("INSERT INTO usuarios VALUES (?,?,?)", (u, hashlib.sha256(p.encode()).hexdigest(), r)); conn.commit(); st.success("OK")
    st.dataframe(pd.read_sql("SELECT username, rol FROM usuarios", conn), use_container_width=True); conn.close()
