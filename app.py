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
# 1. CONFIGURACIÓN GLOBAL Y ESTÉTICA (RESTAURACIÓN TOTAL)
# ==============================================================================
st.set_page_config(page_title="SGSST ERP MASTER", layout="wide", page_icon="🏗️", initial_sidebar_state="collapsed")

DB_NAME = 'sgsst_v205_full_restore.db' 
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"
BG_IMAGE = "https://i.imgur.com/aHPH6U6.jpeg"
LOGO_URL = "https://www.maderasgyd.cl/wp-content/uploads/2024/02/logo-maderas-gd-1.png"

st.markdown(f"""
    <style>
        #MainMenu {{visibility: hidden;}}
        header {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        .block-container {{padding-top: 1rem !important; padding-bottom: 5rem !important;}}
        
        /* Estilo para el Login y Fondo */
        .stApp {{
            background-image: linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.7)), url("{BG_IMAGE}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        
        /* Contenedor de Login */
        div[data-testid="column"]:nth-of-type(2) {{
            background-color: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 30px !important;
            box-shadow: 0 15px 40px rgba(0,0,0,0.6);
            border-top: 8px solid {COLOR_PRIMARY};
            backdrop-filter: blur(5px);
        }}
        
        .logo-box {{background-color: #ffffff; border-radius: 10px; padding: 15px; margin-bottom: 25px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); display: flex; justify-content: center;}}
        .card-kpi {{background-color: #f8f9fa; border-radius: 10px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; border-left: 5px solid {COLOR_PRIMARY};}}
        .card-kpi h3 {{margin: 0; color: #666; font-size: 1rem;}}
        .card-kpi h1 {{margin: 0; color: {COLOR_SECONDARY}; font-size: 2.5rem; font-weight: bold;}}
        div[data-testid="stCanvas"] {{border: 2px solid #a0a0a0 !important; border-radius: 5px; background-color: #ffffff; width: 100% !important;}}
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
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATETIME, usuario TEXT, accion TEXT, detalle TEXT)''')
    
    check_and_add_column(c, "personal", "contacto_emergencia", "TEXT")
    check_and_add_column(c, "personal", "fono_emergencia", "TEXT")
    
    if c.execute("SELECT count(*) FROM usuarios").fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
    conn.commit(); conn.close()

# ==============================================================================
# 3. MOTOR DOCUMENTAL (RESTAURACIÓN LEGAL V205)
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO(); self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=30, leftMargin=30, rightMargin=30); self.elements = []
        self.styles = getSampleStyleSheet(); self.titulo = titulo_doc; self.codigo = codigo_doc; self.logo_url = LOGO_URL
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
        self.elements.append(Table([[f"Nombre: {data['nombre']}", f"RUT: {data['rut']}"], [f"Cargo: {data['cargo']}", f"Fecha: {data['fecha']}"], [f"Mutual: {data['mutual']}", "Empresa: SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA."]], colWidths=[270, 270]))
        self.elements.append(Spacer(1, 10))
        self.elements.append(Paragraph("2. DESCRIPCIÓN DEL PUESTO Y ENTORNO (DS 44)", st_h))
        self.elements.append(Paragraph(data['entorno'], self.styles['Justify']))
        self.elements.append(Spacer(1, 10))
        self.elements.append(Paragraph("3. MATRIZ DE RIESGOS, EFECTOS Y MEDIDAS", st_h))
        r_table = [["PELIGRO", "EFECTO SALUD", "MEDIDA PREVENTIVA"]]
        for r in riesgos: r_table.append([Paragraph(str(r[0]), self.styles['Normal']), Paragraph(str(r[1]), self.styles['Normal']), Paragraph(str(r[2]), self.styles['Normal'])])
        self.elements.append(Table(r_table, colWidths=[130, 130, 280], style=TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke)])))
        self.elements.append(Spacer(1, 15))
        self.elements.append(Paragraph("6. VERIFICACIÓN DE COMPRENSIÓN (BLINDAJE DS 44)", st_h))
        self.elements.append(Paragraph(f"P1: {data['p1']}\nR: ________________________", self.styles['Normal']))
        self.elements.append(Paragraph(f"P2: {data['p2']}\nR: ________________________", self.styles['Normal']))
        self.elements.append(Spacer(1, 20))
        self.elements.append(Paragraph('"Declaro que he sido informado de manera oportuna, clara y específica sobre los riesgos de mi puesto..."', self.styles['Normal']))
        self.elements.append(Spacer(1, 30)); self.elements.append(Table([["__________________________", "__________________________"], ["FIRMA TRABAJADOR", "FIRMA EMPLEADOR"]], colWidths=[270, 270]))
        self.doc.build(self.elements); return self.buffer

    def generar_riohs_legal(self, data):
        self._header()
        txt = f"""Se deja expresa constancia, de acuerdo a lo establecido en el artículo 156 del Código del Trabajo y DS 44 de la Ley 16.744 que, he recibido en forma gratuita un ejemplar del Reglamento Interno de Orden, Higiene y Seguridad de SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA.<br/><br/>
        Declaro bajo mi firma haber recibido, leído y comprendido el presente Reglamento Interno de Orden, Higiene y Seguridad... mi decisión es la entrega {data['tipo']} al correo {str(data['email']).upper()}"""
        self.elements.append(Paragraph(txt, self.styles['Justify']))
        if data.get('firma'): 
            self.elements.append(Spacer(1, 30))
            self.elements.append(RLImage(io.BytesIO(base64.b64decode(data['firma'])), width=180, height=80))
        self.doc.build(self.elements); return self.buffer

    def generar_epp_legal(self, data):
        self._header()
        txt = "Certifico haber recibido de mi empleador, SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA., los Elementos de Protección Personal (EPP) en cumplimiento del Artículo 68 de la Ley 16.744. Declaro haber recibido capacitación en su uso correcto."
        self.elements.append(Paragraph(txt, self.styles['Justify']))
        self.elements.append(Spacer(1, 20)); self.elements.append(Paragraph(f"Lista: {data['lista']}", self.styles['Normal']))
        if data.get('firma'):
            self.elements.append(Spacer(1, 30))
            self.elements.append(RLImage(io.BytesIO(base64.b64decode(data['firma'])), width=180, height=80))
        self.doc.build(self.elements); return self.buffer

# ==============================================================================
# 4. INTERFAZ (LOGIN CON ESTÉTICA RESTAURADA)
# ==============================================================================
init_db()
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown(f'<div class="logo-box"><img src="{LOGO_URL}" style="width: 100%; max-width: 200px;"></div>', unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; color: #444;'>SISTEMA DE GESTIÓN SST</h4>", unsafe_allow_html=True)
        u = st.text_input("Usuario", placeholder="Ingrese su usuario")
        p = st.text_input("Contraseña", type="password", placeholder="••••••••")
        if st.button("INGRESAR AL SISTEMA", use_container_width=True, type="primary"):
            conn = get_conn(); user_check = pd.read_sql("SELECT * FROM usuarios WHERE username=? AND password=?", conn, params=(u, hashlib.sha256(p.encode()).hexdigest()))
            if not user_check.empty: st.session_state['logged_in'] = True; st.rerun()
            else: st.error("🚫 Credenciales incorrectas")
        st.markdown('<div class="login-footer">© 2026 Maderas G&D<br>Seguridad & Gestión</div>', unsafe_allow_html=True)
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f'<img src="{LOGO_URL}" width="150">', unsafe_allow_html=True)
    st.title("MENÚ PRINCIPAL")
    menu = st.radio("Secciones", ["📊 Dashboard", "👥 Gestión Personas", "🛡️ Matriz Riesgos", "⚖️ Gestor Documental", "🦺 Logística EPP", "🎓 Capacitaciones", "🚨 Incidentes", "📅 Plan Anual", "🧯 Extintores", "🏗️ Contratistas", "🔐 Gestión Usuarios"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# ==============================================================================
# 5. MÓDULOS (RESTAURACIÓN TOTAL)
# ==============================================================================

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Control de Gestión SST</div>", unsafe_allow_html=True)
    conn = get_conn(); k1, k2, k3 = st.columns(3)
    t = pd.read_sql("SELECT count(*) FROM personal WHERE estado='ACTIVO'", conn).iloc[0,0]
    a = pd.read_sql("SELECT count(*) FROM incidentes", conn).iloc[0,0]
    k1.markdown(f"<div class='card-kpi'><h3>Dotación Activa</h3><h1>👷 {t}</h1></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='card-kpi'><h3>Incidentes Mes</h3><h1>🚑 {a}</h1></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='card-kpi'><h3>Estado General</h3><h1>✅ Estable</h1></div>", unsafe_allow_html=True)
    st.divider(); st.subheader("Inventario Crítico EPP")
    st.dataframe(pd.read_sql("SELECT producto, stock_actual, stock_minimo FROM inventario_epp WHERE stock_actual < stock_minimo", conn), use_container_width=True)
    conn.close()

# --- GESTIÓN PERSONAS ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Capital Humano</div>", unsafe_allow_html=True)
    conn = get_conn(); t1, t2 = st.tabs(["📋 Nómina", "➕ Nuevo Registro"])
    with t1:
        df = pd.read_sql("SELECT * FROM personal", conn)
        ed = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Guardar Cambios"):
            for i, r in ed.iterrows():
                conn.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=?, estado=?, contacto_emergencia=?, fono_emergencia=?, obs_medica=? WHERE rut=?", 
                             (clean_str(r['nombre']), clean_str(r['cargo']), clean_str(r['centro_costo']), clean_str(r['estado']), clean_str(r['contacto_emergencia']), clean_str(r['fono_emergencia']), clean_str(r['obs_medica']), r['rut']))
            conn.commit(); st.success("Base de datos actualizada")
    with t2:
        with st.form("n_p"):
            c1, c2 = st.columns(2); r = c1.text_input("RUT"); n = c2.text_input("Nombre"); car = st.selectbox("Cargo", LISTA_CARGOS)
            if st.form_submit_button("Registrar Trabajador"):
                conn.execute("INSERT INTO personal (rut, nombre, cargo, estado) VALUES (?,?,?,?)", (r, n, car, 'ACTIVO')); conn.commit(); st.success("Registrado correctamente")
    conn.close()

# --- MATRIZ RIESGOS ---
elif menu == "🛡️ Matriz Riesgos":
    st.markdown("<div class='main-header'>Matriz IPER (Norma ISP)</div>", unsafe_allow_html=True)
    conn = get_conn(); tab1, tab2, tab3 = st.tabs(["👁️ Ver Matriz", "📂 Carga Masiva", "➕ Nuevo Riesgo"])
    with tab1: st.dataframe(pd.read_sql("SELECT * FROM matriz_iper", conn), use_container_width=True)
    with tab2:
        up = st.file_uploader("Subir Plantilla Excel", type=['xlsx'])
        if up:
            df = pd.read_excel(up); df.to_sql("matriz_iper", conn, if_exists="append", index=False)
            st.success("Carga masiva finalizada")
    with tab3:
        with st.form("n_r"):
            pu = st.selectbox("Cargo Asociado", LISTA_CARGOS); pe = st.text_input("Peligro"); ri = st.text_input("Riesgo"); me = st.text_area("Medida Control")
            if st.form_submit_button("Guardar"):
                conn.execute("INSERT INTO matriz_iper (puesto_trabajo, peligro_factor, riesgo_asociado, medida_control) VALUES (?,?,?,?)", (pu, pe, ri, me)); conn.commit(); st.success("Riesgo guardado")
    conn.close()

# --- GESTOR DOCUMENTAL (V205 - FULL SYNC) ---
elif menu == "⚖️ Gestor Documental":
    st.markdown("<div class='main-header'>Centro Documental Legal</div>", unsafe_allow_html=True)
    conn = get_conn(); df_p = pd.read_sql("SELECT rut, nombre, cargo, email FROM personal", conn)
    t1, t2 = st.tabs(["📝 IRL (DS 44)", "📜 Acta RIOHS"])
    with t1:
        if not df_p.empty:
            sel = st.selectbox("Trabajador:", df_p['rut'] + " - " + df_p['nombre'])
            rut_sel = sel.split(" - ")[0]; w_data = df_p[df_p['rut']==rut_sel].iloc[0]
            entorno = st.text_area("Descripción de Entorno", "Oficina administrativa y terreno forestal.")
            p1 = st.text_input("Pregunta Comprensión 1", "¿Qué EPP es obligatorio en faena?"); p2 = st.text_input("Pregunta Comprensión 2", "¿A quién avisar en caso de accidente?")
            if st.button("Generar IRL Fiscalizable"):
                riesgos = pd.read_sql("SELECT peligro_factor, riesgo_asociado, medida_control FROM matriz_iper WHERE puesto_trabajo=?", conn, params=(w_data['cargo'],)).values.tolist()
                pdf = DocumentosLegalesPDF("IRL DS 44", "RG-IRL-02").generar_irl_master({'nombre':w_data['nombre'], 'rut':rut_sel, 'cargo':w_data['cargo'], 'fecha':str(date.today()), 'mutual':'ACHS', 'entorno':entorno, 'centro_urgencia':'Clínica Alemana', 'centro_direccion':'Osorno', 'p1':p1, 'p2':p2}, riesgos)
                st.download_button("Descargar IRL", pdf.getvalue(), f"IRL_{rut_sel}.pdf")
    with t2:
        sel_r = st.selectbox("Personal para RIOHS:", df_p['rut'] + " | " + df_p['nombre'], key="riohs_sel")
        rut_w = sel_r.split(" | ")[0]; w_data = df_p[df_p['rut']==rut_w].iloc[0]
        tipo = st.radio("Tipo Entrega:", ["Físico", "Digital"])
        st.write("Firma Digital:"); canvas = st_canvas(height=150, width=400, key="sw_riohs")
        if st.button("Generar Acta RIOHS"):
            img_w = process_signature_bg(canvas.image_data); b_w = io.BytesIO(); img_w.save(b_w, format='PNG'); str_sig = base64.b64encode(b_w.getvalue()).decode()
            pdf = DocumentosLegalesPDF("ACTA RIOHS", "RG-RI-03").generar_riohs_legal({'firma': str_sig, 'tipo':tipo, 'email':w_data['email']})
            st.download_button("Descargar Acta", pdf.getvalue(), "Acta_RIOHS.pdf")
    conn.close()

# --- OTROS MÓDULOS RESTAURADOS ---
elif menu == "🦺 Logística EPP":
    st.markdown("<div class='main-header'>Logística EPP</div>", unsafe_allow_html=True)
    conn = get_conn(); df_p = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    sel = st.selectbox("Personal:", df_p['rut'] + " | " + df_p['nombre'])
    items = st.text_area("EPP entregado (Lista)", "1 Zapatos, 1 Casco, 2 Guantes")
    canvas = st_canvas(height=150, width=400, key="se_epp")
    if st.button("Generar Acta EPP"):
        rut_w = sel.split(" | ")[0]; w_data = df_p[df_p['rut']==rut_w].iloc[0]
        img = process_signature_bg(canvas.image_data); b = io.BytesIO(); img.save(b, format='PNG'); sig = base64.b64encode(b.getvalue()).decode()
        pdf = DocumentosLegalesPDF("ENTREGA EPP", "RG-EPP-01").generar_epp_legal({'nombre':w_data['nombre'], 'lista':items, 'firma':sig})
        st.download_button("Descargar EPP", pdf.getvalue(), "EPP.pdf")
    conn.close()

elif menu == "🎓 Capacitaciones":
    st.markdown("<div class='main-header'>Capacitaciones</div>", unsafe_allow_html=True)
    st.dataframe(pd.read_sql("SELECT * FROM capacitaciones", get_conn()), use_container_width=True)

elif menu == "🚨 Incidentes":
    st.markdown("<div class='main-header'>Investigación de Incidentes</div>", unsafe_allow_html=True)
    st.dataframe(pd.read_sql("SELECT * FROM incidentes", get_conn()), use_container_width=True)

elif menu == "📅 Plan Anual":
    st.markdown("<div class='main-header'>Programa Anual de Actividades</div>", unsafe_allow_html=True)
    st.dataframe(pd.read_sql("SELECT * FROM programa_anual", get_conn()), use_container_width=True)

elif menu == "🧯 Extintores":
    st.markdown("<div class='main-header'>Control de Extintores</div>", unsafe_allow_html=True)
    st.dataframe(pd.read_sql("SELECT * FROM extintores", get_conn()), use_container_width=True)

elif menu == "🏗️ Contratistas":
    st.markdown("<div class='main-header'>Gestión de Contratistas</div>", unsafe_allow_html=True)
    st.dataframe(pd.read_sql("SELECT * FROM contratistas", get_conn()), use_container_width=True)

elif menu == "🔐 Gestión Usuarios":
    st.markdown("<div class='main-header'>Administración de Usuarios</div>", unsafe_allow_html=True)
    st.dataframe(pd.read_sql("SELECT username, rol FROM usuarios", get_conn()), use_container_width=True)
