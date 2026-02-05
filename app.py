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
# 1. CONFIGURACIÓN GLOBAL
# ==============================================================================
st.set_page_config(page_title="SGSST ERP MASTER", layout="wide", page_icon="🏗️", initial_sidebar_state="collapsed")

DB_NAME = 'sgsst_v204_restored.db' 
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {padding-top: 1rem !important; padding-bottom: 5rem !important;}
        .card-kpi {background-color: #f8f9fa; border-radius: 10px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; border-left: 5px solid #8B0000;}
        .card-kpi h3 {margin: 0; color: #666; font-size: 1rem;}
        .card-kpi h1 {margin: 0; color: #2C3E50; font-size: 2.5rem; font-weight: bold;}
        div[data-testid="stCanvas"] {border: 2px solid #a0a0a0 !important; border-radius: 5px; background-color: #ffffff; width: 100% !important;}
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CAPA DE DATOS Y UTILITARIOS
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
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT, email_copia TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, descripcion TEXT, nombre_afectado TEXT, dias_perdidos INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventario_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT, stock_actual INTEGER, stock_minimo INTEGER, precio INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, relator TEXT, lugar TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, trabajador_rut TEXT, nombre_trabajador TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extintores (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, tipo TEXT, vencimiento DATE, ubicacion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS programa_anual (id INTEGER PRIMARY KEY AUTOINCREMENT, actividad TEXT, responsable TEXT, fecha DATE, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS contratistas (id INTEGER PRIMARY KEY AUTOINCREMENT, empresa TEXT, rut_empresa TEXT, contacto TEXT)''')

    # Columnas críticas
    check_and_add_column(c, "personal", "contacto_emergencia", "TEXT")
    check_and_add_column(c, "personal", "fono_emergencia", "TEXT")
    
    if c.execute("SELECT count(*) FROM usuarios").fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
    conn.commit(); conn.close()

# ==============================================================================
# 3. MOTOR DOCUMENTAL LEGAL
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO(); self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=30, leftMargin=30, rightMargin=30); self.elements = []
        self.styles = getSampleStyleSheet(); self.titulo = titulo_doc; self.codigo = codigo_doc; self.logo_url = "https://www.maderasgyd.cl/wp-content/uploads/2024/02/logo-maderas-gd-1.png"
        self.styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY, fontSize=10, leading=12))

    def _header(self):
        try: logo = RLImage(self.logo_url, width=110, height=45)
        except: logo = Paragraph("<b>MADERAS G&D</b>", self.styles['Normal'])
        data = [[logo, "SISTEMA DE GESTIÓN DE SEGURIDAD Y SALUD EN EL TRABAJO", f"CÓDIGO: {self.codigo}\nFECHA: 05/01/2026"], ["", Paragraph(f"<b>{self.titulo}</b>", ParagraphStyle('B', alignment=TA_CENTER, fontSize=11, fontName='Helvetica-Bold')), "PÁGINA: 1 DE 1"]]
        t = Table(data, colWidths=[140, 280, 120]); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('SPAN', (0,0), (0,1))]))
        self.elements.append(t); self.elements.append(Spacer(1, 15))

    def generar_irl_master(self, data, riesgos):
        self._header()
        st_h = ParagraphStyle('H', fontSize=10, fontName='Helvetica-Bold', backColor=colors.lightgrey, borderPadding=3)
        self.elements.append(Paragraph("1. IDENTIFICACIÓN GENERAL", st_h))
        self.elements.append(Table([[f"Nombre: {data['nombre']}", f"RUT: {data['rut']}"], [f"Cargo: {data['cargo']}", f"Fecha: {data['fecha']}"], [f"Mutual: {data['mutual']}", "Empresa: MADERAS G&D"]], colWidths=[270, 270]))
        self.elements.append(Spacer(1, 10))
        self.elements.append(Paragraph("2. DESCRIPCIÓN DEL PUESTO Y ENTORNO (DS 44)", st_h))
        self.elements.append(Paragraph(data['entorno'], self.styles['Justify']))
        self.elements.append(Spacer(1, 10))
        self.elements.append(Paragraph("3. MATRIZ DE RIESGOS, EFECTOS Y MEDIDAS", st_h))
        r_data = [["PELIGRO", "EFECTO SALUD", "MEDIDA PREVENTIVA"]]
        for r in riesgos: r_data.append([Paragraph(str(r[0]), self.styles['Normal']), Paragraph(str(r[1]), self.styles['Normal']), Paragraph(str(r[2]), self.styles['Normal'])])
        self.elements.append(Table(r_data, colWidths=[130, 130, 280], style=TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke)])))
        self.elements.append(Spacer(1, 20)); self.elements.append(Paragraph("VERIFICACIÓN DE COMPRENSIÓN: ________________________________________________", self.styles['Normal']))
        self.elements.append(Spacer(1, 30)); self.elements.append(Table([["__________________________", "__________________________"], ["FIRMA TRABAJADOR", "FIRMA EMPLEADOR"]], colWidths=[270, 270]))
        self.doc.build(self.elements); return self.buffer

    def generar_riohs_legal(self, data):
        self._header()
        txt = """Se deja expresa constancia, de acuerdo a lo establecido en el artículo 156 del Código del Trabajo y DS 44 de la Ley 16.744 que, he recibido en forma gratuita un ejemplar del Reglamento Interno de Orden, Higiene y Seguridad de SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA.<br/><br/>
        Declaro bajo mi firma haber recibido, leído y comprendido el presente Reglamento Interno... decisión de entrega: """ + data['tipo'] + """ al correo """ + str(data['email']).upper()
        self.elements.append(Paragraph(txt, self.styles['Justify']))
        if data.get('firma'): self.elements.append(Spacer(1, 20)); self.elements.append(RLImage(io.BytesIO(base64.b64decode(data['firma'])), width=150, height=60))
        self.doc.build(self.elements); return self.buffer

# ==============================================================================
# 4. INTERFAZ Y NAVEGACIÓN
# ==============================================================================
init_db()
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align: center;'>INICIAR SESIÓN</h2>", unsafe_allow_html=True)
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("INGRESAR", use_container_width=True):
            conn = get_conn(); user = pd.read_sql("SELECT * FROM usuarios WHERE username=? AND password=?", conn, params=(u, hashlib.sha256(p.encode()).hexdigest()))
            if not user.empty: st.session_state['logged_in'] = True; st.rerun()
            else: st.error("🚫 Error")
    st.stop()

with st.sidebar:
    st.title("MADERAS G&D")
    menu = st.radio("MENÚ", ["📊 Dashboard", "👥 Gestión Personas", "🛡️ Matriz Riesgos", "⚖️ Gestor Documental", "🦺 Logística EPP", "🎓 Capacitaciones", "🚨 Incidentes", "📅 Plan Anual", "🧯 Extintores", "🏗️ Contratistas", "🔐 Gestión Usuarios"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Dashboard de Gestión</div>", unsafe_allow_html=True)
    conn = get_conn(); k1, k2, k3 = st.columns(3)
    t = pd.read_sql("SELECT count(*) FROM personal WHERE estado='ACTIVO'", conn).iloc[0,0]
    a = pd.read_sql("SELECT count(*) FROM incidentes", conn).iloc[0,0]
    k1.markdown(f"<div class='card-kpi'><h3>Dotación</h3><h1>👷 {t}</h1></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='card-kpi'><h3>Incidentes</h3><h1>🚑 {a}</h1></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='card-kpi'><h3>Estado</h3><h1>✅ OK</h1></div>", unsafe_allow_html=True)
    st.divider(); st.subheader("Inventario Crítico EPP")
    st.dataframe(pd.read_sql("SELECT producto, stock_actual FROM inventario_epp WHERE stock_actual < stock_minimo", conn))
    conn.close()

# --- 2. GESTIÓN PERSONAS ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Personal</div>", unsafe_allow_html=True)
    conn = get_conn(); t1, t2 = st.tabs(["📋 Nómina", "➕ Nuevo Ingreso"])
    with t1:
        df = pd.read_sql("SELECT * FROM personal", conn)
        ed = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Guardar Cambios"):
            for i, r in ed.iterrows():
                conn.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=?, estado=?, contacto_emergencia=?, fono_emergencia=?, obs_medica=? WHERE rut=?", 
                          (r['nombre'], r['cargo'], r['centro_costo'], r['estado'], r['contacto_emergencia'], r['fono_emergencia'], r['obs_medica'], r['rut']))
            conn.commit(); st.success("Ok")
    with t2:
        with st.form("n_p"):
            r = st.text_input("RUT"); n = st.text_input("Nombre"); c = st.selectbox("Cargo", LISTA_CARGOS)
            if st.form_submit_button("Registrar"):
                conn.execute("INSERT INTO personal (rut, nombre, cargo, estado) VALUES (?,?,?,?)", (r, n, c, "ACTIVO"))
                conn.commit(); st.success("Ok")
    conn.close()

# --- 3. MATRIZ RIESGOS ---
elif menu == "🛡️ Matriz Riesgos":
    st.markdown("<div class='main-header'>Matriz de Riesgos IPER</div>", unsafe_allow_html=True)
    conn = get_conn(); tab1, tab2, tab3 = st.tabs(["👁️ Ver Matriz", "📂 Carga Masiva", "➕ Nuevo Riesgo"])
    with tab1: st.dataframe(pd.read_sql("SELECT * FROM matriz_iper", conn))
    with tab2:
        up = st.file_uploader("Subir Excel", type=['xlsx'])
        if up:
            df = pd.read_excel(up); df.to_sql("matriz_iper", conn, if_exists="append", index=False)
            st.success("Cargado")
    with tab3:
        with st.form("new_r"):
            pu = st.selectbox("Cargo", LISTA_CARGOS); pe = st.text_input("Peligro"); ri = st.text_input("Riesgo"); me = st.text_area("Medida")
            if st.form_submit_button("Guardar"):
                conn.execute("INSERT INTO matriz_iper (puesto_trabajo, peligro_factor, riesgo_asociado, medida_control) VALUES (?,?,?,?)", (pu, pe, ri, me))
                conn.commit(); st.success("Guardado")
    conn.close()

# --- 4. GESTOR DOCUMENTAL (IRL DS 44 RESTAURADO) ---
elif menu == "⚖️ Gestor Documental":
    st.markdown("<div class='main-header'>Gestor Documental</div>", unsafe_allow_html=True)
    conn = get_conn(); t1, t2 = st.tabs(["📝 IRL DS 44", "📜 RIOHS"])
    with t1:
        trabs = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
        if not trabs.empty:
            sel = st.selectbox("Trabajador:", trabs['rut'] + " - " + trabs['nombre'])
            rut = sel.split(" - ")[0]; cargo = trabs[trabs['rut']==rut]['cargo'].values[0]
            entorno = st.text_area("Descripción Entorno", "Oficina y Terreno Forestal")
            if st.button("Generar IRL Profesional"):
                riesgos = pd.read_sql("SELECT peligro_factor, riesgo_asociado, medida_control FROM matriz_iper WHERE puesto_trabajo=?", conn, params=(cargo,)).values.tolist()
                pdf = DocumentosLegalesPDF("IRL DS 44", "RG-IRL-01").generar_irl_master({'nombre':sel, 'rut':rut, 'cargo':cargo, 'fecha':str(date.today()), 'mutual':'ACHS', 'entorno':entorno, 'centro_urgencia':'Clínica Alemana', 'centro_direccion':'Osorno', 'p1':'Distancia de seguridad?', 'p2':'Accidente de trayecto?'}, riesgos)
                st.download_button("Descargar IRL", pdf.getvalue(), "IRL.pdf")
    with t2:
        st.info("Firma de acta RIOHS legalizada")
        s_r = st.selectbox("Personal:", trabs['rut'] + " | " + trabs['nombre'], key="riohs_sel")
        canvas = st_canvas(height=150, width=400, key="riohs_sig")
        if st.button("Generar Acta RIOHS"):
            img = process_signature_bg(canvas.image_data); b = io.BytesIO(); img.save(b, format='PNG'); str_sig = base64.b64encode(b.getvalue()).decode()
            pdf = DocumentosLegalesPDF("ACTA RIOHS", "RG-RI-01").generar_riohs_legal({'firma': str_sig, 'tipo':'Digital', 'email':'correo@ejemplo.com'})
            st.download_button("Descargar Acta", pdf.getvalue(), "Acta_RIOHS.pdf")
    conn.close()

# --- 5. OTROS MÓDULOS (RESTAURADOS) ---
elif menu == "🦺 Logística EPP":
    st.markdown("<div class='main-header'>Inventario y Entrega EPP</div>", unsafe_allow_html=True)
    conn = get_conn(); t1, t2 = st.tabs(["📦 Stock", "🤝 Entrega"])
    with t1: st.dataframe(pd.read_sql("SELECT * FROM inventario_epp", conn))
    conn.close()

elif menu == "🎓 Capacitaciones":
    st.markdown("<div class='main-header'>Registro Asistencia</div>", unsafe_allow_html=True)
    conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM capacitaciones", conn))
    conn.close()

elif menu == "🚨 Incidentes":
    st.markdown("<div class='main-header'>Investigación Accidentes</div>", unsafe_allow_html=True)
    conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM incidentes", conn))
    conn.close()

elif menu == "📅 Plan Anual":
    st.markdown("<div class='main-header'>Programa de Actividades</div>", unsafe_allow_html=True)
    conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM programa_anual", conn))
    conn.close()

elif menu == "🧯 Extintores":
    st.markdown("<div class='main-header'>Control de Equipos</div>", unsafe_allow_html=True)
    conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM extintores", conn))
    conn.close()

elif menu == "🏗️ Contratistas":
    st.markdown("<div class='main-header'>Gestión Terceros</div>", unsafe_allow_html=True)
    conn = get_conn(); st.dataframe(pd.read_sql("SELECT * FROM contratistas", conn))
    conn.close()

elif menu == "🔐 Gestión Usuarios":
    st.markdown("<div class='main-header'>Administración de Usuarios</div>", unsafe_allow_html=True)
    conn = get_conn(); st.dataframe(pd.read_sql("SELECT username, rol FROM usuarios", conn))
    conn.close()
