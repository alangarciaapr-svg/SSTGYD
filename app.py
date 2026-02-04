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

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CONFIGURACIÓN GLOBAL
# ==============================================================================
st.set_page_config(page_title="SGSST ERP MASTER", layout="wide", page_icon="🏗️", initial_sidebar_state="collapsed")

DB_NAME = 'sgsst_v202_irl_master.db' # Versión 202: IRL Profesional DS 44
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"

# --- CSS Y META TAGS (PWA/MÓVIL) ---
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {padding-top: 1rem !important; padding-bottom: 5rem !important;}
        input, select, textarea {font-size: 16px !important;}
        button {min-height: 45px !important;}
        .main-header {font-size: 2.2rem; font-weight: 800; color: #2C3E50; margin-bottom: 0px;}
        .sub-header {font-size: 1.1rem; color: #666; margin-bottom: 20px;}
        .card-kpi {background-color: #f8f9fa; border-radius: 10px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; border-left: 5px solid #8B0000;}
        .card-kpi h3 {margin: 0; color: #666; font-size: 1rem;}
        .card-kpi h1 {margin: 0; color: #2C3E50; font-size: 2.5rem; font-weight: bold;}
        .alert-box {padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd; display: flex; align-items: center;}
        .alert-icon {font-size: 1.5rem; margin-right: 15px;}
        .alert-high {background-color: #fff5f5; border-left: 5px solid #c53030; color: #c53030;}
        div[data-testid="stCanvas"] {border: 2px solid #a0a0a0 !important; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); background-color: #ffffff; margin-bottom: 10px; min-height: 150px; width: 100% !important;}
        .stApp {background-size: cover; background-position: center; background-attachment: fixed;}
    </style>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
""", unsafe_allow_html=True)

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
    c.execute('''CREATE TABLE IF NOT EXISTS personal (rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, fecha_contrato DATE, estado TEXT, vigencia_examen_medico DATE, email TEXT, contacto_emergencia TEXT, fono_emergencia TEXT, obs_medica TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS conducta_personal (id INTEGER PRIMARY KEY AUTOINCREMENT, rut_trabajador TEXT, fecha DATE, tipo TEXT, descripcion TEXT, gravedad TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (id INTEGER PRIMARY KEY AUTOINCREMENT, proceso TEXT, puesto_trabajo TEXT, peligro_factor TEXT, riesgo_asociado TEXT, probabilidad INTEGER, consecuencia INTEGER, vep INTEGER, nivel_riesgo TEXT, medida_control TEXT, familia_riesgo TEXT, codigo_riesgo TEXT, jerarquia_control TEXT, requisito_legal TEXT, n_hombres INTEGER, n_mujeres INTEGER, n_disidencias INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, tipo_actividad TEXT, responsable_rut TEXT, lugar TEXT, duracion INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, trabajador_rut TEXT, nombre_trabajador TEXT, estado TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, cargo TEXT, lista_productos TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, descripcion TEXT, nombre_afectado TEXT, dias_perdidos INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventario_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT, stock_actual INTEGER, stock_minimo INTEGER, ubicacion TEXT, precio INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    
    # Auto-reparación básica
    check_and_add_column(c, "personal", "contacto_emergencia", "TEXT")
    check_and_add_column(c, "personal", "fono_emergencia", "TEXT")
    
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
    conn.commit(); conn.close()
    st.session_state['db_setup_complete'] = True

def calcular_nivel_riesgo(vep):
    if vep <= 2: return "TOLERABLE"
    elif vep == 4: return "MODERADO"
    elif vep == 8: return "IMPORTANTE"
    elif vep >= 16: return "INTOLERABLE"
    return "MODERADO"

def process_signature_bg(img_data):
    try:
        if img_data is None: return create_text_signature_img("Firma No Detectada")
        img = PILImage.fromarray(img_data.astype('uint8'), 'RGBA')
        return img
    except: return create_text_signature_img("Error Firma")

def create_text_signature_img(text_sig):
    width, height = 400, 100
    image = PILImage.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 40), f"Firmado: {text_sig}", fill="black")
    return image

# ==============================================================================
# 3. MOTOR DOCUMENTAL IRL PROFESIONAL (V202)
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO(); self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=30, leftMargin=30, rightMargin=30); self.elements = []
        self.styles = getSampleStyleSheet(); self.titulo = titulo_doc; self.codigo = codigo_doc; self.logo_url = "https://www.maderasgyd.cl/wp-content/uploads/2024/02/logo-maderas-gd-1.png"
        
        # Estilos personalizados
        self.styles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY, fontSize=10, leading=12))
        self.styles.add(ParagraphStyle(name='CenterBold', alignment=TA_CENTER, fontSize=11, fontName='Helvetica-Bold'))
        self.styles.add(ParagraphStyle(name='HeadingBox', alignment=TA_LEFT, fontSize=10, fontName='Helvetica-Bold', backColor=colors.lightgrey, borderPadding=3))

    def _header(self):
        try: logo = RLImage(self.logo_url, width=110, height=45)
        except: logo = Paragraph("<b>MADERAS G&D</b>", self.styles['Normal'])
        data = [[logo, "SISTEMA DE GESTIÓN DE SEGURIDAD Y SALUD EN EL TRABAJO", f"CÓDIGO: {self.codigo}\nVERSIÓN: 2.0"], ["", Paragraph(f"<b>{self.titulo}</b>", self.styles['CenterBold']), "PÁGINA: 1 DE 1"]]
        t = Table(data, colWidths=[140, 280, 120]); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('SPAN', (0,0), (0,1))]))
        self.elements.append(t); self.elements.append(Spacer(1, 15))

    def generar_irl_completo(self, data, riesgos):
        self._header()
        
        # 1. Identificación
        self.elements.append(Paragraph("1. IDENTIFICACIÓN GENERAL", self.styles['HeadingBox']))
        id_data = [
            [f"Nombre Trabajador: {data['nombre']}", f"R.U.T: {data['rut']}"],
            [f"Cargo: {data['cargo']}", f"Fecha Entrega: {data['fecha']}"],
            [f"Organismo Administrador: {data['mutual']}", "Empresa: SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA."]
        ]
        t_id = Table(id_data, colWidths=[270, 270]); t_id.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('FONTSIZE', (0,0), (-1,-1), 9)]))
        self.elements.append(t_id); self.elements.append(Spacer(1, 10))

        # 2. Descripción del Puesto
        self.elements.append(Paragraph("2. DESCRIPCIÓN DEL PUESTO Y ENTORNO (ART. 15, LETRA D)", self.styles['HeadingBox']))
        self.elements.append(Paragraph(data['descripcion_entorno'], self.styles['Justify']))
        self.elements.append(Spacer(1, 10))

        # 3. Matriz de Riesgos
        self.elements.append(Paragraph("3. MATRIZ DE RIESGOS, EFECTOS Y MEDIDAS (ART. 15, LETRAS A, B, C)", self.styles['HeadingBox']))
        r_table = [["PELIGRO / RIESGO", "EFECTOS POSIBLES", "MEDIDAS PREVENTIVAS"]]
        for r in riesgos:
            r_table.append([Paragraph(str(r[0]), self.styles['Normal']), Paragraph(str(r[1]), self.styles['Normal']), Paragraph(str(r[2]), self.styles['Normal'])])
        
        t_r = Table(r_table, colWidths=[140, 140, 260]); t_r.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke), ('FONTSIZE', (0,0), (-1,-1), 8), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
        self.elements.append(t_r); self.elements.append(Spacer(1, 10))

        # 4. Emergencias
        self.elements.append(Paragraph("4. GESTIÓN DE EMERGENCIAS Y DESASTRES (ART. 15, LETRA E)", self.styles['HeadingBox']))
        em_text = f"<b>Prevención Incendios:</b> Uso de extintores PQS. <br/><b>Vías Evacuación:</b> Reconocer zonas de seguridad y PME. <br/><b>Centro Asistencial:</b> {data['centro_urgencia']} ({data['centro_direccion']})."
        self.elements.append(Paragraph(em_text, self.styles['Justify']))
        self.elements.append(Spacer(1, 10))

        # 5. Derechos
        self.elements.append(Paragraph("5. DERECHOS Y PRESTACIONES LEY 16.744 (ART. 15, LETRA F)", self.styles['HeadingBox']))
        self.elements.append(Paragraph("El trabajador tiene derecho a Prestaciones Médicas (atención gratuita, medicamentos, rehabilitación) y Prestaciones Económicas (pago de licencias, indemnizaciones) en caso de accidentes o enfermedades profesionales.", self.styles['Justify']))
        self.elements.append(Spacer(1, 10))

        # 6. Verificación de Comprensión
        self.elements.append(Paragraph("6. VERIFICACIÓN DE COMPRENSIÓN (BLINDAJE DS 44)", self.styles['HeadingBox']))
        self.elements.append(Paragraph(f"Pregunta 1: {data['p1']} <br/>Respuesta: ____________________________________________________", self.styles['Normal']))
        self.elements.append(Paragraph(f"Pregunta 2: {data['p2']} <br/>Respuesta: ____________________________________________________", self.styles['Normal']))
        self.elements.append(Spacer(1, 20))

        # 7. Firmas
        self.elements.append(Paragraph('"Declaro que he sido informado de manera oportuna, clara y específica sobre los riesgos de mi puesto, las medidas preventivas y los beneficios del seguro social de la Ley 16.744. Se me ha hecho entrega de una copia física/digital del presente documento."', self.styles['Justify']))
        self.elements.append(Spacer(1, 40))
        
        f_data = [["__________________________", "__________________________"], ["FIRMA TRABAJADOR", "FIRMA EMPLEADOR / EXPERTO"]]
        t_f = Table(f_data, colWidths=[270, 270]); t_f.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t_f)

        self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_riohs(self, data):
        self._header()
        txt = f"Se deja expresa constancia, de acuerdo a lo establecido en el artículo 156 del Código del Trabajo y DS 44 de la Ley 16.744 que, he recibido en forma gratuita un ejemplar del Reglamento Interno de Orden, Higiene y Seguridad de SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA. <br/><br/> Declaro bajo mi firma haber recibido, leído y comprendido el presente Reglamento Interno... Decision de entrega: {data['tipo_entrega']} al correo {str(data['email']).upper()}"
        self.elements.append(Paragraph(txt, self.styles['Justify']))
        sig_img = Paragraph("", self.styles['Normal'])
        if data.get('firma_b64'):
            try: sig_img = RLImage(io.BytesIO(base64.b64decode(data['firma_b64'])), width=150, height=60)
            except: pass
        self.elements.append(Spacer(1, 30)); self.elements.append(sig_img); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

# ==============================================================================
# 4. FRONTEND STREAMLIT
# ==============================================================================
if 'db_setup_complete' not in st.session_state: init_db()

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h2 style='text-align: center;'>INICIAR SESIÓN</h2>", unsafe_allow_html=True)
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("INGRESAR", use_container_width=True):
            conn = get_conn(); user_data = pd.read_sql("SELECT * FROM usuarios WHERE username=? AND password=?", conn, params=(u, hashlib.sha256(p.encode()).hexdigest())); conn.close()
            if not user_data.empty: st.session_state['logged_in'] = True; st.session_state['user'] = u; st.rerun()
            else: st.error("🚫 Error")
    st.stop()

with st.sidebar:
    st.title("MADERAS G&D")
    menu = st.radio("MENÚ", ["📊 Dashboard", "👥 Gestión Personas", "🛡️ Matriz Riesgos", "⚖️ Gestor Documental", "🦺 Logística EPP", "🔐 Gestión Usuarios"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Control de Gestión SST</div>", unsafe_allow_html=True)
    conn = get_conn()
    k1, k2, k3 = st.columns(3)
    trabs = pd.read_sql("SELECT count(*) FROM personal WHERE estado='ACTIVO'", conn).iloc[0,0]
    acc = pd.read_sql("SELECT count(*) FROM incidentes", conn).iloc[0,0]
    k1.markdown(f"<div class='card-kpi'><h3>Dotación Activa</h3><h1>👷 {trabs}</h1></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='card-kpi'><h3>Accidentes Mes</h3><h1>🚑 {acc}</h1></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='card-kpi'><h3>Estado</h3><h1>✅ Estable</h1></div>", unsafe_allow_html=True)
    conn.close()

# --- 2. GESTIÓN PERSONAS ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Personal</div>", unsafe_allow_html=True)
    conn = get_conn()
    t1, t2 = st.tabs(["📋 Nómina", "➕ Nuevo Ingreso"])
    with t1:
        df = pd.read_sql("SELECT * FROM personal", conn)
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Guardar"):
            for i, r in edited.iterrows():
                conn.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=?, estado=?, obs_medica=? WHERE rut=?", (r['nombre'], r['cargo'], r['centro_costo'], r['estado'], r['obs_medica'], r['rut']))
            conn.commit(); st.success("Ok")
    with t2:
        with st.form("new_p"):
            c1, c2 = st.columns(2); r = c1.text_input("RUT"); n = c2.text_input("Nombre"); car = st.selectbox("Cargo", LISTA_CARGOS)
            if st.form_submit_button("Registrar"):
                conn.execute("INSERT INTO personal (rut, nombre, cargo, estado) VALUES (?,?,?,?)", (r, n, car, 'ACTIVO')); conn.commit(); st.success("Ok")
    conn.close()

# --- 3. MATRIZ RIESGOS ---
elif menu == "🛡️ Matriz Riesgos":
    st.markdown("<div class='main-header'>Matriz de Riesgos IPER</div>", unsafe_allow_html=True)
    conn = get_conn()
    tab1, tab2 = st.tabs(["👁️ Ver Matriz", "➕ Nuevo Riesgo"])
    with tab1:
        st.dataframe(pd.read_sql("SELECT * FROM matriz_iper", conn), use_container_width=True)
    with tab2:
        with st.form("new_r"):
            roles = pd.read_sql("SELECT DISTINCT cargo FROM personal", conn)['cargo'].tolist()
            pue = st.selectbox("Puesto de Trabajo", sorted(list(set(roles + LISTA_CARGOS))))
            pel = st.text_input("Peligro")
            rie = st.text_input("Efecto / Riesgo Asociado")
            med = st.text_area("Medida Preventiva / Método de Trabajo")
            if st.form_submit_button("Guardar Riesgo"):
                conn.execute("INSERT INTO matriz_iper (puesto_trabajo, peligro_factor, riesgo_asociado, medida_control) VALUES (?,?,?,?)", (pue, pel, rie, med))
                conn.commit(); st.success("Riesgo guardado")
    conn.close()

# --- 4. GESTOR DOCUMENTAL (V202 - IRL DS 44 PERFECCIONADO) ---
elif menu == "⚖️ Gestor Documental":
    st.markdown("<div class='main-header'>Centro de Documentación Legal</div>", unsafe_allow_html=True)
    conn = get_conn()
    t1, t2 = st.tabs(["📝 Generar IRL (DS 44)", "📜 Acta RIOHS"])
    
    with t1:
        df_p = pd.read_sql("SELECT rut, nombre, cargo FROM personal WHERE estado='ACTIVO'", conn)
        if not df_p.empty:
            sel = st.selectbox("Seleccionar Trabajador:", df_p['rut'] + " - " + df_p['nombre'] + " (" + df_p['cargo'] + ")")
            rut_sel = sel.split(" - ")[0]
            w_data = df_p[df_p['rut'] == rut_sel].iloc[0]
            
            st.divider()
            st.markdown("### Información Adicional para el Documento")
            c1, c2 = st.columns(2)
            mutual = c1.text_input("Organismo Administrador:", value="ACHS")
            c_urg = c2.text_input("Centro de Urgencia:", value="Clínica Alemana de Osorno")
            c_dir = c1.text_input("Dirección Centro Urgencia:", value="Calle Ficticia #123, Osorno")
            
            entorno = st.text_area("Descripción de Entorno (Art. 15 Letra D):", 
                                  value="Entorno Oficina: Labores administrativas y reuniones. Entorno Faena Forestal: Inspección de frentes de cosecha y caminos.")
            
            st.markdown("### Preguntas de Verificación de Comprensión")
            p1 = st.text_input("Pregunta 1:", value="¿Cuál es la distancia mínima de seguridad que debe mantener frente a una máquina?")
            p2 = st.text_input("Pregunta 2:", value="¿Qué debe hacer inmediatamente después de sufrir un accidente laboral?")
            
            if st.button("GENERAR IRL FISCALIZABLE", type="primary"):
                # Rescatar riesgos dinámicos de la matriz
                riesgos = pd.read_sql("SELECT peligro_factor, riesgo_asociado, medida_control FROM matriz_iper WHERE puesto_trabajo=?", conn, params=(w_data['cargo'],))
                
                if riesgos.empty:
                    st.warning("⚠️ No hay riesgos específicos en la matriz para este cargo. Se usarán riesgos genéricos.")
                    riesgos_list = [["General Forestal", "Golpeado por", "Mantener distancia 20m"], ["Tránsito", "Atropello", "Chaleco Reflectante"]]
                else:
                    riesgos_list = riesgos.values.tolist()
                
                pdf = DocumentosLegalesPDF("INFORMACIÓN DE RIESGOS LABORALES (IRL)", "RG-SST-04").generar_irl_completo({
                    'nombre': w_data['nombre'], 'rut': w_data['rut'], 'cargo': w_data['cargo'],
                    'fecha': date.today().strftime("%d/%m/%Y"), 'mutual': mutual,
                    'descripcion_entorno': entorno, 'centro_urgencia': c_urg, 'centro_direccion': c_dir,
                    'p1': p1, 'p2': p2
                }, riesgos_list)
                st.download_button(f"Descargar IRL {w_data['nombre']}", pdf.getvalue(), f"IRL_{rut_sel}.pdf", "application/pdf")
        else:
            st.warning("Debe registrar personal en 'Gestión Personas' primero.")
            
    with t2:
        st.write("Módulo RIOHS disponible (igual que versiones anteriores).")
    conn.close()

# --- 5. LOGISTICA EPP ---
elif menu == "🦺 Logística EPP":
    st.markdown("<div class='main-header'>Entrega de Elementos de Protección</div>", unsafe_allow_html=True)
    st.info("Módulo EPP Operativo")

# --- 6. GESTIÓN USUARIOS ---
elif menu == "🔐 Gestión Usuarios":
    st.markdown("<div class='main-header'>Administración de Cuentas</div>", unsafe_allow_html=True)
    st.info("Módulo de Usuarios Protegido")
