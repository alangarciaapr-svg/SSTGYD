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
import matplotlib
import matplotlib.pyplot as plt
import plotly.express as px
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from streamlit_drawable_canvas import st_canvas
import openpyxl 

# Manejo seguro de librería QR
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CONFIGURACIÓN GLOBAL
# ==============================================================================
st.set_page_config(page_title="SGSST ERP MASTER", layout="wide", page_icon="🏗️")

DB_NAME = 'sgsst_v141_login_final.db' # Mismo nombre para mantener datos
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"

# --- MODO KIOSCO (FIRMA MÓVIL) ---
query_params = st.query_params
if "mobile_sign" in query_params and query_params["mobile_sign"] == "true":
    cap_id_mobile = query_params.get("cap_id", None)
    st.markdown(f"<h2 style='text-align: center; color: {COLOR_PRIMARY}'>✍️ Firma de Asistencia</h2>", unsafe_allow_html=True)
    
    if cap_id_mobile:
        conn = sqlite3.connect(DB_NAME)
        try:
            cap_data = pd.read_sql("SELECT tema, fecha FROM capacitaciones WHERE id=?", conn, params=(cap_id_mobile,))
            if not cap_data.empty:
                st.info(f"Actividad: {cap_data.iloc[0]['tema']} ({cap_data.iloc[0]['fecha']})")
                with st.form("mobile_sign_form"):
                    rut_input = st.text_input("Ingresa tu RUT (con guión)", placeholder="12345678-9")
                    st.write("Firma aquí:")
                    canvas_mobile = st_canvas(stroke_width=2, stroke_color="black", background_color="#eee", height=200, width=300, key="mobile_c")
                    
                    if st.form_submit_button("ENVIAR FIRMA"):
                        if rut_input and canvas_mobile.image_data is not None:
                            check = pd.read_sql("SELECT id FROM asistencia_capacitacion WHERE capacitacion_id=? AND trabajador_rut=?", conn, params=(cap_id_mobile, rut_input))
                            if not check.empty:
                                img = PILImage.fromarray(canvas_mobile.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
                                conn.execute("UPDATE asistencia_capacitacion SET estado='FIRMADO', firma_b64=? WHERE capacitacion_id=? AND trabajador_rut=?", (img_str, cap_id_mobile, rut_input))
                                conn.commit()
                                st.success("✅ Firma registrada. Gracias.")
                            else: st.error("❌ RUT no inscrito en esta capacitación.")
                        else: st.warning("⚠️ Faltan datos.")
            else: st.error("Capacitación no encontrada.")
        except: st.error("Error de conexión con DB Móvil.")
        conn.close()
    st.stop() 

# --- ESTILOS CSS GENERALES (APP INTERNA) ---
st.markdown(f"""
    <style>
    .main-header {{font-size: 2.2rem; font-weight: 800; color: {COLOR_SECONDARY}; margin-bottom: 0px;}}
    .sub-header {{font-size: 1.1rem; color: #666; margin-bottom: 20px;}}
    .card-kpi {{background-color: #f8f9fa; border-radius: 10px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; border-left: 5px solid {COLOR_PRIMARY};}}
    .card-kpi h3 {{margin: 0; color: #666; font-size: 1rem;}}
    .card-kpi h1 {{margin: 0; color: {COLOR_SECONDARY}; font-size: 2.5rem; font-weight: bold;}}
    .alert-box {{padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd; display: flex; align-items: center;}}
    .alert-icon {{font-size: 1.5rem; margin-right: 15px;}}
    .alert-high {{background-color: #fff5f5; border-left: 5px solid #c53030; color: #c53030;}}
    </style>
""", unsafe_allow_html=True)

LISTA_CARGOS = ["GERENTE GENERAL", "PREVENCIONISTA DE RIESGOS", "JEFE DE PATIO", "OPERADOR DE ASERRADERO", "OPERADOR DE MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "MECANICO", "ADMINISTRATIVO"]

# ==============================================================================
# 2. CAPA DE DATOS (SQL)
# ==============================================================================
def get_conn(): return sqlite3.connect(DB_NAME, check_same_thread=False)

def check_and_add_column(cursor, table_name, column_name, column_type):
    try: cursor.execute(f"SELECT {column_name} FROM {table_name} LIMIT 1")
    except sqlite3.OperationalError:
        try: cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        except: pass

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS personal (rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, fecha_contrato DATE, estado TEXT, vigencia_examen_medico DATE, email TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS conducta_personal (id INTEGER PRIMARY KEY AUTOINCREMENT, rut_trabajador TEXT, fecha DATE, tipo TEXT, descripcion TEXT, gravedad TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (id INTEGER PRIMARY KEY AUTOINCREMENT, proceso TEXT, tipo_proceso TEXT, puesto_trabajo TEXT, tarea TEXT, es_rutinaria TEXT, peligro_factor TEXT, riesgo_asociado TEXT, tipo_riesgo TEXT, probabilidad INTEGER, consecuencia INTEGER, vep INTEGER, nivel_riesgo TEXT, medida_control TEXT, genero_obs TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, tipo_actividad TEXT, responsable_rut TEXT, estado TEXT, duracion INTEGER, lugar TEXT, metodologia TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, trabajador_rut TEXT, nombre_trabajador TEXT, cargo_trabajador TEXT, estado TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, cargo TEXT, lista_productos TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, descripcion TEXT, area TEXT, severidad TEXT, rut_afectado TEXT, nombre_afectado TEXT, parte_cuerpo TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventario_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT, stock_actual INTEGER, stock_minimo INTEGER, ubicacion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extintores (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, tipo TEXT, capacidad TEXT, ubicacion TEXT, fecha_vencimiento DATE, estado_inspeccion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS programa_anual (id INTEGER PRIMARY KEY AUTOINCREMENT, actividad TEXT, responsable TEXT, fecha_programada DATE, estado TEXT, fecha_ejecucion DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS contratistas (id INTEGER PRIMARY KEY AUTOINCREMENT, rut_empresa TEXT, razon_social TEXT, estado_documental TEXT, fecha_vencimiento_f30 DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATETIME, usuario TEXT, accion TEXT, detalle TEXT)''')

    check_and_add_column(c, "personal", "contacto_emergencia", "TEXT")
    check_and_add_column(c, "personal", "fono_emergencia", "TEXT")
    check_and_add_column(c, "personal", "obs_medica", "TEXT")
    check_and_add_column(c, "personal", "vigencia_examen_medico", "DATE")

    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
        c.executemany("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion) VALUES (?,?,?,?)", [("Casco", 50, 5, "Bodega"), ("Lentes", 100, 10, "Bodega")])
        
        c.execute("SELECT count(*) FROM matriz_iper")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO matriz_iper (proceso, tipo_proceso, puesto_trabajo, tarea, es_rutinaria, peligro_factor, riesgo_asociado, tipo_riesgo, probabilidad, consecuencia, vep, nivel_riesgo, medida_control, genero_obs) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 ("Cosecha", "Operativo", "Operador", "Tala", "SI", "Pendiente", "Volcamiento", "Seguridad", 2, 4, 8, "IMPORTANTE", "Cabina ROPS", "Sin Obs"))
    conn.commit(); conn.close()

def registrar_auditoria(usuario, accion, detalle):
    try: conn = get_conn(); conn.execute("INSERT INTO auditoria (fecha, usuario, accion, detalle) VALUES (?,?,?,?)", (datetime.now(), usuario, accion, detalle)); conn.commit(); conn.close()
    except: pass

def calcular_nivel_riesgo(vep):
    if vep <= 2: return "TOLERABLE"
    elif vep == 4: return "MODERADO"
    elif vep == 8: return "IMPORTANTE"
    elif vep >= 16: return "INTOLERABLE"
    return "NO CLASIFICADO"

def get_alertas():
    conn = get_conn(); alertas = []; hoy = date.today()
    try:
        trabs = pd.read_sql("SELECT rut, nombre, vigencia_examen_medico FROM personal WHERE estado='ACTIVO'", conn)
        for i, t in trabs.iterrows():
            if t['vigencia_examen_medico']:
                try:
                    fv = datetime.strptime(t['vigencia_examen_medico'], '%Y-%m-%d').date()
                    if fv < hoy: alertas.append(f"🔴 {t['nombre']}: Examen Vencido")
                    elif fv < hoy + timedelta(days=30): alertas.append(f"🟡 {t['nombre']}: Examen vence pronto")
                except: pass
    except: pass
    try:
        stock = pd.read_sql("SELECT producto FROM inventario_epp WHERE stock_actual <= stock_minimo", conn)
        for i, s in stock.iterrows(): alertas.append(f"📦 Stock Bajo: {s['producto']}")
    except: pass
    conn.close(); return alertas

def get_incidentes_mes():
    conn = get_conn(); 
    try: mes = datetime.now().strftime('%m'); res = pd.read_sql(f"SELECT count(*) FROM incidentes WHERE strftime('%m', fecha)='{mes}'", conn).iloc[0,0]
    except: res = 0
    conn.close(); return res

# ==============================================================================
# 3. MOTOR DOCUMENTAL
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO(); self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=40); self.elements = []
        self.styles = getSampleStyleSheet(); self.titulo = titulo_doc; self.codigo = codigo_doc; self.logo_path = "logo_empresa.png"

    def _header(self):
        logo = Paragraph("<b>LOGO</b>", self.styles['Normal'])
        if os.path.exists(self.logo_path):
            try: logo = RLImage(self.logo_path, width=80, height=35)
            except: pass
        data = [[logo, Paragraph(f"SISTEMA DE GESTIÓN SST - DS44<br/><b>{self.titulo}</b>", ParagraphStyle('T', alignment=TA_CENTER, fontSize=11, fontName='Helvetica-Bold')), Paragraph(f"CÓDIGO: {self.codigo}<br/>VER: 08<br/>FECHA: {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle('C', alignment=TA_CENTER, fontSize=7))]]
        t = Table(data, colWidths=[90, 340, 90]); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t); self.elements.append(Spacer(1, 20))

    def _signature_block(self, firma_b64, label="FIRMA TRABAJADOR"):
        sig_img = Paragraph("", self.styles['Normal'])
        if firma_b64:
            try: sig_img = RLImage(io.BytesIO(base64.b64decode(firma_b64)), width=120, height=50)
            except: pass
        data = [[sig_img, "HUELLA\nDACTILAR"], [label, ""]]; t = Table(data, colWidths=[200, 60], rowHeights=[60, 20])
        t.setStyle(TableStyle([('ALIGN', (0,0), (0,0), 'CENTER'), ('VALIGN', (0,0), (0,0), 'BOTTOM'), ('LINEABOVE', (0,1), (0,1), 1, colors.black), ('GRID', (1,0), (1,1), 0.5, colors.grey), ('VALIGN', (1,0), (1,0), 'MIDDLE'), ('ALIGN', (1,0), (1,0), 'CENTER'), ('FONTSIZE', (1,0), (1,0), 6)]))
        main = Table([[t]], colWidths=[500]); main.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')])); self.elements.append(Spacer(1, 20)); self.elements.append(main)

    def generar_epp(self, data):
        self._header(); self.elements.append(Paragraph("I. ANTECEDENTES", self.styles['Heading3']))
        t_info = Table([[f"NOMBRE: {data['nombre']}", f"RUT: {data['rut']}"], [f"CARGO: {data['cargo']}", f"FECHA: {data['fecha']}"]], colWidths=[260, 260]); t_info.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)]))
        self.elements.append(t_info); self.elements.append(Spacer(1, 15))
        try: items = ast.literal_eval(data['lista'])
        except: items = []
        t_data = [["CANT", "ELEMENTO", "MOTIVO"]]; 
        for i in items: t_data.append([str(i.get('cant','1')), i.get('prod','EPP'), i.get('mot','-')])
        t_prod = Table(t_data, colWidths=[40, 280, 200]); t_prod.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(t_prod); self.elements.append(Spacer(1, 25)); self.elements.append(Paragraph("Declaro recibir conforme (DS594).", self.styles['Normal'])); self.elements.append(Spacer(1, 30))
        self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_riohs(self, data):
        self._header(); self.elements.append(Paragraph(f"ENTREGA RIOHS: {data['nombre']}", self.styles['Heading3']))
        self.elements.append(Spacer(1, 20)); self.elements.append(Paragraph("Certifico recepción RIOHS (Art 156 CT).", self.styles['Normal']))
        self.elements.append(Spacer(1, 40)); self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_irl(self, data, riesgos):
        self._header(); self.elements.append(Paragraph(f"IRL: {data['nombre']}", self.styles['Heading3']))
        r_data = [["PELIGRO", "RIESGO", "MEDIDA"]]; 
        for r in riesgos: r_data.append([Paragraph(r[0], ParagraphStyle('s', fontSize=8)), Paragraph(r[1], ParagraphStyle('s', fontSize=8)), Paragraph(r[2], ParagraphStyle('s', fontSize=8))])
        t = Table(r_data, colWidths=[130, 130, 250]); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
        self.elements.append(t); self.elements.append(Spacer(1, 30)); self.elements.append(Paragraph("Recibí información (DS44).", self.styles['Normal'])); self.elements.append(Spacer(1, 30)); self._signature_block(None); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_asistencia_capacitacion(self, data, asis):
        self._header(); self.elements.append(Paragraph("I. ANTECEDENTES", self.styles['Heading3']))
        tc = Table([[f"TEMA: {data['tema']}", f"TIPO: {data['tipo']}"], [f"RELATOR: {data['resp']}", f"FECHA: {data['fecha']}"]], colWidths=[260, 260]); tc.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(tc); self.elements.append(Spacer(1, 15)); self.elements.append(Paragraph("II. ASISTENCIA", self.styles['Heading3']))
        a_data = [["NOMBRE", "RUT", "FIRMA"]]; row_h = [20]
        for a in asis: 
            f_img = ""
            if a.get('firma_b64'):
                try: f_img = RLImage(io.BytesIO(base64.b64decode(a['firma_b64'])), width=100, height=30)
                except: pass
            a_data.append([a['nombre'], a['rut'], f_img]); row_h.append(40)
        t = Table(a_data, colWidths=[200, 100, 150], rowHeights=row_h, repeatRows=1)
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        self.elements.append(t); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_diat(self, data):
        self._header(); self.elements.append(Paragraph("DIAT", self.styles['Title'])); self.elements.append(Paragraph(f"AFECTADO: {data['nombre']}", self.styles['Heading3']))
        self.elements.append(Spacer(1, 20)); self.elements.append(Paragraph(data['descripcion'], self.styles['Normal'])); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

# ==============================================================================
# 4. FRONTEND (LOGIN V143 - MASTER)
# ==============================================================================
init_db()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user' not in st.session_state: st.session_state['user'] = "Invitado"

if not st.session_state['logged_in']:
    BG_IMAGE = "https://i.imgur.com/aHPH6U6.jpeg"
    LOGO_URL = "https://www.maderasgyd.cl/wp-content/uploads/2024/02/logo-maderas-gd-1.png"
    
    # CSS AVANZADO: Bloqueo de Scroll + Tarjeta Global
    st.markdown(f"""
        <style>
            /* 1. SCROLL LOCK */
            html, body, [data-testid="stAppViewContainer"] {{
                overflow: hidden !important;
                height: 100vh !important;
                margin: 0;
            }}
            
            [data-testid="stSidebar"], [data-testid="stHeader"] {{display: none !important;}}
            
            /* 2. BACKGROUND */
            .stApp {{
                background-image: linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.7)), url("{BG_IMAGE}");
                background-size: cover;
                background-position: center;
                background-attachment: fixed;
            }}
            
            /* 3. CARD CONTAINER (Columna Central) */
            /* Apuntamos al div que contiene los inputs y botones */
            div[data-testid="column"]:nth-of-type(2) {{
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 40px !important;
                box-shadow: 0 15px 40px rgba(0,0,0,0.6);
                border-top: 8px solid {COLOR_PRIMARY};
                backdrop-filter: blur(5px);
            }}
            
            /* 4. LOGO BOX (Para contraste) */
            .logo-box {{
                background-color: #ffffff;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 25px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                display: flex;
                justify-content: center;
            }}
            
            .login-footer {{
                text-align: center;
                color: #888;
                font-size: 0.8rem;
                margin-top: 30px;
                font-weight: bold;
                border-top: 1px solid #ddd;
                padding-top: 15px;
            }}
            
            /* Inputs */
            div[data-testid="stTextInput"] input {{
                background-color: #f8f9fa;
                border: 1px solid #ccc;
                border-radius: 8px;
                padding: 10px;
            }}
        </style>
    """, unsafe_allow_html=True)

    # LAYOUT 3 COLUMNAS
    c1, c2, c3 = st.columns([1, 1.2, 1])
    
    with c2:
        # LOGO CON FONDO (HTML/CSS)
        st.markdown(f"""
            <div class="logo-box">
                <img src="{LOGO_URL}" style="width: 100%; max-width: 220px;">
            </div>
            <h4 style='text-align: center; color: #444; margin-bottom: 20px; font-weight:600;'>INICIAR SESIÓN</h4>
        """, unsafe_allow_html=True)
        
        # INPUTS (Quedan dentro de la tarjeta automáticamente por el CSS)
        u = st.text_input("Usuario", placeholder="Ingrese usuario", label_visibility="collapsed")
        p = st.text_input("Contraseña", type="password", placeholder="Ingrese contraseña", label_visibility="collapsed")
        
        st.write("") # Espacio
        
        if st.button("INGRESAR", type="primary", use_container_width=True):
            if u == "admin" and p == "1234": 
                st.session_state['logged_in'] = True; st.session_state['user'] = u; registrar_auditoria(u, "LOGIN", "OK"); st.rerun()
            else: st.error("🚫 Credenciales incorrectas")
            
        st.markdown('<div class="login-footer">© 2026 SEGAV<br>Seguridad & Gestión Avanzada</div>', unsafe_allow_html=True)

    st.stop()

with st.sidebar:
    st.title("MADERAS GÁLVEZ")
    st.caption("V143 - MASTER FINAL")
    with open(DB_NAME, "rb") as fp: st.download_button(label="💾 Respaldar BD", data=fp, file_name=f"backup_{date.today()}.db")
    menu = st.radio("MENÚ", ["📊 Dashboard", "🛡️ Matriz IPER (ISP)", "👥 Gestión Personas", "⚖️ Gestor Documental", "🦺 Logística EPP", "🎓 Capacitaciones", "🚨 Incidentes & DIAT", "📅 Plan Anual", "🧯 Extintores", "🏗️ Contratistas"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown(f"""<div style="background-color: {COLOR_SECONDARY}; padding: 20px; border-radius: 10px; margin-bottom: 20px; color: white;"><h2 style="margin:0; color:white;">Bienvenido, {st.session_state['user'].capitalize()}</h2><p style="margin:0;">Sistema de Gestión SST | {date.today().strftime('%d-%m-%Y')}</p></div>""", unsafe_allow_html=True)
    conn = get_conn()
    k1, k2, k3, k4 = st.columns(4)
    try:
        acc = pd.read_sql("SELECT count(*) FROM incidentes", conn).iloc[0,0]
        cap = pd.read_sql("SELECT count(*) FROM capacitaciones", conn).iloc[0,0]
        trabs = pd.read_sql("SELECT count(*) FROM personal WHERE estado='ACTIVO'", conn).iloc[0,0]
        alertas = get_alertas()
    except: acc=0; cap=0; trabs=0; alertas=[]
    def card(t, v, i): return f"<div class='card-kpi'><h3>{t}</h3><h1>{i} {v}</h1></div>"
    k1.markdown(card("Dotación", trabs, "👷"), unsafe_allow_html=True)
    k2.markdown(card("Accidentes", acc, "🚑"), unsafe_allow_html=True)
    k3.markdown(card("Capacitaciones", cap, "🎓"), unsafe_allow_html=True)
    k4.markdown(card("Alertas", len(alertas), "⚠️"), unsafe_allow_html=True)
    st.markdown("---")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("🔔 Alertas")
        if alertas:
            with st.container(height=300):
                for a in alertas: st.markdown(f"<div class='alert-box alert-high'>⚠️ {a}</div>", unsafe_allow_html=True)
        else: st.success("Todo OK")
    with c2:
        st.subheader("📈 Métricas")
        t1, t2 = st.tabs(["Stock EPP", "Personal"])
        with t1:
            df_epp = pd.read_sql("SELECT producto, stock_actual, stock_minimo FROM inventario_epp", conn)
            if not df_epp.empty:
                fig = px.bar(df_epp, x='producto', y='stock_actual', title="Stock EPP", color='stock_actual')
                st.plotly_chart(fig, use_container_width=True)
        with t2:
            df_per = pd.read_sql("SELECT estado, count(*) as count FROM personal GROUP BY estado", conn)
            if not df_per.empty:
                fig2 = px.pie(df_per, values='count', names='estado', title="Dotación", hole=0.4)
                st.plotly_chart(fig2, use_container_width=True)
    conn.close()

# --- 2. MATRIZ IPER ---
elif menu == "🛡️ Matriz IPER (ISP)":
    st.markdown("<div class='main-header'>Matriz de Riesgos (ISP 2024)</div>", unsafe_allow_html=True)
    tab_ver, tab_carga, tab_crear = st.tabs(["👁️ Ver Matriz", "📂 Carga Masiva", "➕ Crear Riesgo"])
    conn = get_conn()
    with tab_ver:
        query = """SELECT id, proceso as 'PROCESO', puesto_trabajo as 'PUESTO', tarea as 'TAREA', es_rutinaria as 'RUTINARIA', peligro_factor as 'PELIGRO (GEMA)', riesgo_asociado as 'RIESGO', probabilidad as 'P', consecuencia as 'C', vep as 'VEP', nivel_riesgo as 'NIVEL', medida_control as 'MEDIDAS DE CONTROL' FROM matriz_iper"""
        df_matriz = pd.read_sql(query, conn)
        edited_df = st.data_editor(df_matriz, use_container_width=True, 
            column_config={
                "P": st.column_config.NumberColumn("P", min_value=1, max_value=4), 
                "C": st.column_config.NumberColumn("C", min_value=1, max_value=4), 
                "VEP": st.column_config.NumberColumn("VEP", disabled=True), 
                "NIVEL": st.column_config.TextColumn("NIVEL", disabled=True)
            }, hide_index=True, key="matriz_ed")
        if st.button("💾 Guardar y Recalcular"):
            c = conn.cursor()
            for i, r in edited_df.iterrows():
                np = int(r['P']); nc = int(r['C']); nvep = np*nc; nniv = calcular_nivel_riesgo(nvep)
                c.execute("UPDATE matriz_iper SET probabilidad=?, consecuencia=?, vep=?, nivel_riesgo=?, medida_control=? WHERE id=?", (np, nc, nvep, nniv, r['MEDIDAS DE CONTROL'], r['id']))
            conn.commit(); st.success("Actualizado"); st.rerun()
        b = io.BytesIO(); 
        with pd.ExcelWriter(b, engine='openpyxl') as w: edited_df.to_excel(w, index=False)
        st.download_button("📥 Excel Matriz", b.getvalue(), "MIPER.xlsx")

    with tab_carga:
        plantilla = {'Proceso':['Cosecha'], 'Puesto':['Operador'], 'Peligro':['Pendiente'], 'Riesgo':['Volcamiento'], 'Probabilidad':[2], 'Consecuencia':[4], 'Medida':['ROPS']}
        b2 = io.BytesIO(); 
        with pd.ExcelWriter(b2, engine='openpyxl') as w: pd.DataFrame(plantilla).to_excel(w, index=False)
        st.download_button("📥 Plantilla Carga", b2.getvalue(), "plantilla_iper.xlsx")
        up = st.file_uploader("Subir Excel", type=['xlsx'])
        if up:
            try:
                df = pd.read_excel(up)
                if st.button("Procesar"):
                    c = conn.cursor()
                    for i, r in df.iterrows():
                        p = int(r.get('Probabilidad',1)); co = int(r.get('Consecuencia',1)); v = p*co; n = calcular_nivel_riesgo(v)
                        c.execute("INSERT INTO matriz_iper (proceso, puesto_trabajo, peligro_factor, riesgo_asociado, probabilidad, consecuencia, vep, nivel_riesgo, medida_control) VALUES (?,?,?,?,?,?,?,?,?)", (r.get('Proceso',''), r.get('Puesto',''), r.get('Peligro',''), r.get('Riesgo',''), p, co, v, n, r.get('Medida','')))
                    conn.commit(); st.success("Cargado")
            except: st.error("Error en archivo")

    with tab_crear:
        with st.form("risk"):
            c1, c2 = st.columns(2); pro = c1.text_input("Proceso"); pue = c2.text_input("Puesto")
            c3, c4 = st.columns(2); pel = c3.text_input("Peligro"); rie = c4.text_input("Riesgo")
            c5, c6 = st.columns(2); pr = c5.selectbox("P", [1,2,4]); co = c6.selectbox("C", [1,2,4])
            med = st.text_area("Medida")
            if st.form_submit_button("Guardar"):
                v = pr*co; ni = calcular_nivel_riesgo(v)
                conn.execute("INSERT INTO matriz_iper (proceso, puesto_trabajo, peligro_factor, riesgo_asociado, probabilidad, consecuencia, vep, nivel_riesgo, medida_control) VALUES (?,?,?,?,?,?,?,?,?)", (pro, pue, pel, rie, pr, co, v, ni, med))
                conn.commit(); st.success("Guardado"); st.rerun()
    conn.close()

# --- 3. GESTION PERSONAS ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Capital Humano</div>", unsafe_allow_html=True)
    conn = get_conn()
    try:
        total = pd.read_sql("SELECT count(*) FROM personal", conn).iloc[0,0]
        activos = pd.read_sql("SELECT count(*) FROM personal WHERE estado='ACTIVO'", conn).iloc[0,0]
    except: total=0; activos=0
    k1, k2, k3 = st.columns(3)
    k1.metric("Dotación Total", total); k2.metric("Activos", activos); k3.metric("Bajas", total-activos)
    
    tab_list, tab_carga, tab_new, tab_dig = st.tabs(["📋 Nómina", "📂 Carga Masiva", "➕ Nuevo", "🗂️ Carpeta Digital (Semáforo)"])
    
    with tab_list:
        df_p = pd.read_sql("SELECT rut, rut as rut_old, nombre, cargo, centro_costo, email, fecha_contrato, vigencia_examen_medico, contacto_emergencia, fono_emergencia, estado FROM personal", conn)
        df_p['fecha_contrato'] = pd.to_datetime(df_p['fecha_contrato'], errors='coerce')
        df_p['vigencia_examen_medico'] = pd.to_datetime(df_p['vigencia_examen_medico'], errors='coerce')
        
        edited = st.data_editor(df_p, key="pers_ed", use_container_width=True, num_rows="dynamic",
            column_config={
                "rut_old": None,
                "rut": st.column_config.TextColumn("RUT (Editable)"),
                "fecha_contrato": st.column_config.DateColumn("Contrato", format="DD/MM/YYYY"),
                "vigencia_examen_medico": st.column_config.DateColumn("Venc. Examen", format="DD/MM/YYYY"),
                "cargo": st.column_config.SelectboxColumn("Cargo", options=LISTA_CARGOS),
                "estado": st.column_config.SelectboxColumn("Estado", options=["ACTIVO", "INACTIVO"]),
                "contacto_emergencia": st.column_config.TextColumn("Contacto Emergencia"),
                "fono_emergencia": st.column_config.TextColumn("Fono Emergencia")
            })
        if st.button("💾 Guardar Cambios"):
            c = conn.cursor()
            for i, r in edited.iterrows():
                fec = r['fecha_contrato']; f_ex = r['vigencia_examen_medico']
                if pd.isna(fec) or str(fec)=='NaT': fec = date.today()
                if pd.isna(f_ex) or str(f_ex)=='NaT': f_ex = None
                
                if r['rut'] != r['rut_old']:
                    c.execute("UPDATE personal SET rut=?, nombre=?, cargo=?, centro_costo=?, email=?, estado=?, fecha_contrato=?, vigencia_examen_medico=?, contacto_emergencia=?, fono_emergencia=? WHERE rut=?", 
                              (r['rut'], r['nombre'], r['cargo'], r['centro_costo'], r['email'], r['estado'], fec, f_ex, r['contacto_emergencia'], r['fono_emergencia'], r['rut_old']))
                    c.execute("UPDATE asistencia_capacitacion SET trabajador_rut=? WHERE trabajador_rut=?", (r['rut'], r['rut_old']))
                    c.execute("UPDATE registro_epp SET rut_trabajador=? WHERE rut_trabajador=?", (r['rut'], r['rut_old']))
                    c.execute("UPDATE registro_riohs SET rut_trabajador=? WHERE rut_trabajador=?", (r['rut'], r['rut_old']))
                else:
                    c.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=?, email=?, estado=?, fecha_contrato=?, vigencia_examen_medico=?, contacto_emergencia=?, fono_emergencia=? WHERE rut=?", 
                              (r['nombre'], r['cargo'], r['centro_costo'], r['email'], r['estado'], fec, f_ex, r['contacto_emergencia'], r['fono_emergencia'], r['rut']))
            conn.commit(); st.success("Guardado"); time.sleep(1); st.rerun()

    with tab_carga:
        template_data = {
            'RUT': ['11.222.333-4'], 'NOMBRE': ['Juan Pérez'], 'CARGO': ['OPERADOR'], 
            'CENTRO_COSTO': ['FAENA'], 'EMAIL': ['juan@empresa.com'], 
            'FECHA DE CONTRATO': ['2024-01-01'], 'VIGENCIA_EXAMEN': ['2025-01-01'],
            'CONTACTO_EMERGENCIA': ['Maria Perez'], 'TELEFONO_EMERGENCIA': ['+56912345678']
        }
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer: pd.DataFrame(template_data).to_excel(writer, index=False)
        st.download_button("📥 Descargar Plantilla", data=buffer.getvalue(), file_name="plantilla_personal_completa.xlsx")
        
        up = st.file_uploader("Subir", type=['xlsx', 'csv'])
        limpiar_db = st.checkbox("⚠️ Borrar TODA la base de datos antes de cargar (Limpia Ejemplo)", value=False)
        if up:
            if st.button("🚀 Procesar"):
                try:
                    df = pd.read_excel(up) if up.name.endswith('xlsx') else pd.read_csv(up)
                    c = conn.cursor()
                    if limpiar_db: c.execute("DELETE FROM personal")
                    for i, r in df.iterrows():
                        rut = str(r.get('RUT', '')).strip()
                        try: f = pd.to_datetime(r.get('FECHA DE CONTRATO'), errors='coerce').date()
                        except: f = date.today()
                        if pd.isna(f): f = date.today()
                        
                        try: f_ex = pd.to_datetime(r.get('VIGENCIA_EXAMEN'), errors='coerce').date()
                        except: f_ex = None
                        if pd.isna(f_ex): f_ex = None

                        if len(rut) > 3:
                            c.execute("""INSERT OR REPLACE INTO personal 
                                (rut, nombre, cargo, centro_costo, email, fecha_contrato, estado, vigencia_examen_medico, contacto_emergencia, fono_emergencia) 
                                VALUES (?,?,?,?,?,?,?,?,?,?)""", 
                                (rut, r.get('NOMBRE'), r.get('CARGO'), r.get('CENTRO_COSTO'), r.get('EMAIL'), f, 'ACTIVO', f_ex, r.get('CONTACTO_EMERGENCIA'), r.get('TELEFONO_EMERGENCIA')))
                    conn.commit(); st.success("Cargado"); time.sleep(1.5); st.rerun()
                except Exception as e: st.error(f"Error: {e}")

    with tab_new:
        with st.form("new_p"):
            c1, c2 = st.columns(2); r = c1.text_input("RUT"); n = c2.text_input("Nombre"); ca = c1.selectbox("Cargo", LISTA_CARGOS); em = c2.text_input("Email"); 
            c3, c4 = st.columns(2); f_ex = c3.date_input("Vencimiento Examen (Opcional)", value=None); c_emer = c4.text_input("Contacto Emergencia")
            f_emer = c3.text_input("Teléfono Emergencia"); obs = c4.text_input("Alergias/Obs Médica")
            if st.form_submit_button("Registrar"):
                try: conn.execute("INSERT INTO personal (rut, nombre, cargo, email, fecha_contrato, estado, vigencia_examen_medico, contacto_emergencia, fono_emergencia, obs_medica) VALUES (?,?,?,?,?,?,?,?,?,?)", (r, n, ca, em, date.today(), 'ACTIVO', f_ex, c_emer, f_emer, obs)); conn.commit(); st.success("Creado")
                except: st.error("Error (RUT duplicado?)")

    with tab_dig:
        df_all = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        if not df_all.empty:
            sel_worker = st.selectbox("Seleccionar Trabajador:", df_all['rut'] + " - " + df_all['nombre'])
            rut_sel = sel_worker.split(" - ")[0]
            
            # --- DATOS EMERGENCIA ---
            datos_p = pd.read_sql("SELECT contacto_emergencia, fono_emergencia, obs_medica, vigencia_examen_medico FROM personal WHERE rut=?", conn, params=(rut_sel,)).iloc[0]
            st.info(f"🚑 Emergencia: {datos_p['contacto_emergencia']} - {datos_p['fono_emergencia']} | ⚕️ Obs: {datos_p['obs_medica']}")
            
            st.subheader("🚦 Estado de Habilitación")
            odi = pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(rut_sel,)).iloc[0,0] > 0
            riohs = pd.read_sql("SELECT count(*) FROM registro_riohs WHERE rut_trabajador=?", conn, params=(rut_sel,)).iloc[0,0] > 0
            epp = pd.read_sql("SELECT count(*) FROM registro_epp WHERE rut_trabajador=?", conn, params=(rut_sel,)).iloc[0,0] > 0
            
            f_examen_raw = datos_p['vigencia_examen_medico']
            examen_ok = False
            if f_examen_raw:
                try: 
                    f_ex_dt = datetime.strptime(f_examen_raw, '%Y-%m-%d').date()
                    if f_ex_dt >= date.today(): examen_ok = True
                except: pass
            habilitado = odi and riohs and epp and (examen_ok if f_examen_raw else True) 
            col_sem1, col_sem2 = st.columns([1,3])
            with col_sem1:
                if habilitado: st.success("### ✅ HABILITADO")
                else: st.error("### 🚫 NO HABILITADO")
            with col_sem2:
                c1, c2, c3, c4 = st.columns(4)
                c1.write(f"{'✅' if odi else '❌'} ODI/IRL")
                c2.write(f"{'✅' if riohs else '❌'} RIOHS")
                c3.write(f"{'✅' if epp else '❌'} EPP")
                c4.write(f"{'✅' if examen_ok else '⚠️'} Examen")
            st.divider()
            st.subheader("⚖️ Historial de Conducta")
            hist = pd.read_sql("SELECT fecha, tipo, descripcion, gravedad FROM conducta_personal WHERE rut_trabajador=?", conn, params=(rut_sel,))
            if not hist.empty: st.dataframe(hist, use_container_width=True)
            else: st.info("Sin registros de conducta.")
            with st.expander("➕ Agregar Registro de Conducta"):
                with st.form("conducta_form"):
                    f_c = st.date_input("Fecha Evento"); t_c = st.selectbox("Tipo", ["Amonestación Verbal", "Amonestación Escrita", "Felicitación", "Incidente"])
                    g_c = st.selectbox("Gravedad", ["Leve", "Grave", "Gravísima", "Positiva"]); d_c = st.text_area("Descripción")
                    if st.form_submit_button("Guardar Registro"):
                        conn.execute("INSERT INTO conducta_personal (rut_trabajador, fecha, tipo, descripcion, gravedad) VALUES (?,?,?,?,?)", (rut_sel, f_c, t_c, d_c, g_c))
                        conn.commit(); st.success("Registrado"); st.rerun()
            if QR_AVAILABLE:
                st.divider(); qr = qrcode.make(f"SGSST|{rut_sel}"); b_qr = io.BytesIO(); qr.save(b_qr, format='PNG')
                st.image(b_qr.getvalue(), width=100, caption="Credencial QR")
    conn.close()

# --- 4. GESTOR DOCUMENTAL (CORREGIDO) ---
elif menu == "⚖️ Gestor Documental":
    st.markdown("<div class='main-header'>Centro Documental</div>", unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["IRL", "RIOHS", "Historial"])
    conn = get_conn(); df_p = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    
    if df_p.empty:
        st.warning("⚠️ No hay trabajadores registrados. Vaya a 'Gestión Personas' para agregar.")
    else:
        with t1:
            sel = st.selectbox("Trabajador:", df_p['rut'] + " - " + df_p['nombre'])
            if st.button("Generar IRL"):
                rut = sel.split(" - ")[0]; cargo = df_p[df_p['rut']==rut]['cargo'].values[0]
                riesgos = pd.read_sql("SELECT peligro_factor, riesgo_asociado, medida_control FROM matriz_iper WHERE puesto_trabajo LIKE ?", conn, params=(f'%{cargo}%',))
                if riesgos.empty: riesgos = pd.read_sql("SELECT peligro_factor, riesgo_asociado, medida_control FROM matriz_iper LIMIT 3", conn)
                pdf = DocumentosLegalesPDF("IRL", "RG-GD-04").generar_irl({'nombre': sel.split(" - ")[1]}, riesgos.values.tolist())
                st.download_button("Descargar IRL", pdf.getvalue(), "IRL.pdf")
        with t2:
            sel_r = st.selectbox("Trabajador RIOHS:", df_p['rut'] + " | " + df_p['nombre'])
            c_riohs = st_canvas(stroke_width=2, height=150, key="riohs")
            if st.button("Registrar Entrega"):
                if c_riohs.image_data is not None:
                    img = PILImage.fromarray(c_riohs.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
                    conn.execute("INSERT INTO registro_riohs (fecha_entrega, rut_trabajador, nombre_trabajador, firma_b64) VALUES (?,?,?,?)", (date.today(), sel_r.split(" | ")[0], sel_r.split(" | ")[1], ib64)); conn.commit()
                    pdf = DocumentosLegalesPDF("RIOHS", "RG-GD-03").generar_riohs({'nombre': sel_r.split(" | ")[1], 'firma_b64': ib64})
                    st.download_button("Descargar", pdf.getvalue(), "RIOHS.pdf")
        with t3:
            st.dataframe(pd.read_sql("SELECT * FROM registro_riohs", conn))
    conn.close()

# --- 5. LOGISTICA EPP ---
elif menu == "🦺 Logística EPP":
    st.markdown("<div class='main-header'>EPP</div>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Entrega", "Inventario"])
    conn = get_conn()
    with t2:
        ed = st.data_editor(pd.read_sql("SELECT * FROM inventario_epp", conn), key="inv", num_rows="dynamic")
        if st.button("Actualizar Stock"):
            conn.execute("DELETE FROM inventario_epp"); 
            for i,r in ed.iterrows(): conn.execute("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion) VALUES (?,?,?,?)", (r['producto'], r['stock_actual'], r['stock_minimo'], r['ubicacion']))
            conn.commit(); st.success("OK"); st.rerun()
    with t1:
        df_workers = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        if df_workers.empty:
            st.warning("No hay trabajadores para asignar EPP.")
        else:
            worker_options = df_workers['rut'] + " | " + df_workers['nombre']
            sel = st.selectbox("Trabajador", worker_options)
            inv = pd.read_sql("SELECT producto FROM inventario_epp WHERE stock_actual > 0", conn)
            if 'cart' not in st.session_state: st.session_state.cart = []
            c1, c2 = st.columns(2); p = c1.selectbox("Prod", inv['producto']); q = c2.number_input("Cant", 1)
            if st.button("Agregar"): st.session_state.cart.append({'prod': p, 'cant': q})
            st.table(st.session_state.cart)
            can = st_canvas(stroke_width=2, height=150, key="epp")
            if st.button("Confirmar"):
                if can.image_data is not None:
                    img = PILImage.fromarray(can.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
                    rut = sel.split(" | ")[0]; nom = sel.split(" | ")[1]
                    conn.execute("INSERT INTO registro_epp (fecha_entrega, rut_trabajador, nombre_trabajador, lista_productos, firma_b64) VALUES (?,?,?,?,?)", (date.today(), rut, nom, str(st.session_state.cart), ib64))
                    for i in st.session_state.cart: conn.execute("UPDATE inventario_epp SET stock_actual = stock_actual - ? WHERE producto=?", (i['cant'], i['prod']))
                    conn.commit()
                    pdf = DocumentosLegalesPDF("EPP", "RG-GD-01").generar_epp({'nombre': nom, 'rut': rut, 'cargo': 'OP', 'fecha': date.today(), 'lista': str(st.session_state.cart), 'firma_b64': ib64})
                    st.download_button("PDF", pdf.getvalue(), "EPP.pdf"); st.session_state.cart = []
    conn.close()

# --- 6. CAPACITACIONES (CON QR FIXED) ---
elif menu == "🎓 Capacitaciones":
    st.markdown("<div class='main-header'>Capacitaciones</div>", unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["Nueva", "QR Firma", "Historial"])
    conn = get_conn()
    with t1:
        with st.form("cap"):
            t = st.text_input("Tema"); tp = st.selectbox("Tipo", ["Inducción", "Charla"]); lug = st.text_input("Lugar"); dur = st.number_input("Horas", 1); rel = st.text_input("Relator")
            df_p = pd.read_sql("SELECT rut, nombre FROM personal", conn)
            asis = st.multiselect("Asistentes", df_p['rut'] + " | " + df_p['nombre'])
            if st.form_submit_button("Guardar"):
                c = conn.cursor(); c.execute("INSERT INTO capacitaciones (fecha, tema, tipo_actividad, responsable_rut, lugar, duracion) VALUES (?,?,?,?,?,?)", (date.today(), t, tp, rel, lug, dur)); cid = c.lastrowid
                for a in asis: c.execute("INSERT INTO asistencia_capacitacion (capacitacion_id, trabajador_rut, nombre_trabajador, estado) VALUES (?,?,?,?)", (cid, a.split(" | ")[0], a.split(" | ")[1], "PENDIENTE"))
                conn.commit(); st.success("OK")
    with t2:
        caps = pd.read_sql("SELECT id, tema FROM capacitaciones ORDER BY id DESC", conn)
        if not caps.empty:
            sel_qr = st.selectbox("Seleccionar:", caps['id'].astype(str) + " - " + caps['tema'])
            cap_id = sel_qr.split(" - ")[0]
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip_local = s.getsockname()[0]; s.close(); default_url = f"http://{ip_local}:8501"
            except: default_url = "https://tu-app.streamlit.app"
            st.warning("⚠️ Si estás en Streamlit Cloud, pega la URL de tu navegador abajo:")
            url_base = st.text_input("URL Base", value=default_url)
            link = f"{url_base}/?mobile_sign=true&cap_id={cap_id}"
            if QR_AVAILABLE:
                qr = qrcode.make(link); b = io.BytesIO(); qr.save(b, format='PNG')
                st.image(b.getvalue(), width=250)
            st.write(f"Link: {link}")
    with t3:
        caps = pd.read_sql("SELECT * FROM capacitaciones", conn); st.dataframe(caps)
        sel_pdf = st.selectbox("PDF:", caps['id'].astype(str) + " - " + caps['tema'])
        if st.button("Generar Lista"):
            cid = int(sel_pdf.split(" - ")[0])
            c_data = pd.read_sql("SELECT * FROM capacitaciones WHERE id=?", conn, params=(cid,)).iloc[0]
            a_data = pd.read_sql("SELECT * FROM asistencia_capacitacion WHERE capacitacion_id=?", conn, params=(cid,)).to_dict('records')
            pdf = DocumentosLegalesPDF("CAPACITACION", "RG-GD-02").generar_asistencia_capacitacion({'tema':c_data['tema'], 'tipo':c_data['tipo_actividad'], 'resp':c_data['responsable_rut'], 'fecha':c_data['fecha'], 'lugar':c_data['lugar'], 'duracion':c_data['duracion']}, a_data)
            st.download_button("PDF", pdf.getvalue(), "Lista.pdf")
    conn.close()

# --- 7. OTROS ---
elif menu == "🚨 Incidentes & DIAT":
    st.title("Incidentes"); conn = get_conn()
    with st.form("inc"):
        f = st.date_input("Fecha"); d = st.text_area("Descripción"); a = st.text_input("Afectado")
        if st.form_submit_button("Guardar"): conn.execute("INSERT INTO incidentes (fecha, descripcion, nombre_afectado) VALUES (?,?,?)", (f, d, a)); conn.commit(); st.success("OK")
    if st.button("Generar DIAT"):
        pdf = DocumentosLegalesPDF("DIAT", "LEGAL").generar_diat({'nombre': 'Ejemplo', 'rut': '1-9', 'fecha': str(date.today()), 'tipo': 'Accidente', 'descripcion': 'Detalle...'})
        st.download_button("DIAT", pdf.getvalue(), "DIAT.pdf")
    conn.close()
elif menu == "📅 Plan Anual":
    st.title("Plan Anual"); conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM programa_anual", conn), key="plan", num_rows="dynamic"); conn.close()
elif menu == "🧯 Extintores":
    st.title("Extintores"); conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM extintores", conn), key="ext", num_rows="dynamic"); conn.close()
elif menu == "🏗️ Contratistas":
    st.title("Contratistas"); conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM contratistas", conn), key="con", num_rows="dynamic"); conn.close()
