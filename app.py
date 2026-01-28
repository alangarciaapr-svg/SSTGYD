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
from PIL import Image as PILImage
import matplotlib
import matplotlib.pyplot as plt
import plotly.express as px
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter, legal
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from streamlit_drawable_canvas import st_canvas

# Manejo seguro de librería QR
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CONFIGURACIÓN DEL SISTEMA GLOBAL
# ==============================================================================
st.set_page_config(page_title="SGSST ERP MASTER", layout="wide", page_icon="🏗️")

DB_NAME = 'sgsst_v114_full_master.db'
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"
MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

# Estilos CSS Profesionales
st.markdown("""
    <style>
    .main-header {font-size: 2.0rem; font-weight: 700; color: #2C3E50; border-bottom: 3px solid #8B0000; margin-bottom: 15px;}
    .alert-box {padding: 10px; border-radius: 5px; margin-bottom: 5px; font-size: 0.9rem; font-weight: 500;}
    .alert-high {background-color: #ffebee; color: #b71c1c; border-left: 5px solid #d32f2f;}
    .alert-med {background-color: #fff3e0; color: #ef6c00; border-left: 5px solid #ff9800;}
    .alert-ok {background-color: #e8f5e9; color: #2e7d32; border-left: 5px solid #388e3c;}
    </style>
""", unsafe_allow_html=True)

LISTA_CARGOS = ["GERENTE GENERAL", "PREVENCIONISTA DE RIESGOS", "JEFE DE PATIO", "OPERADOR DE ASERRADERO", "OPERADOR DE MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "MECANICO", "ADMINISTRATIVO"]
LISTA_PROBABILIDAD = [1, 2, 4]
LISTA_CONSECUENCIA = [1, 2, 4]

# ==============================================================================
# 2. CAPA DE DATOS (SQL) - ESTRUCTURA COMPLETA
# ==============================================================================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # Base y RRHH
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATETIME, usuario TEXT, accion TEXT, detalle TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS personal (rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, fecha_contrato DATE, estado TEXT, vigencia_examen_medico DATE)''')
    
    # Prevención y Riesgos (MATRIZ ACTUALIZADA ISP 2024)
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proceso TEXT,
        tipo_proceso TEXT,
        puesto_trabajo TEXT,
        tarea TEXT,
        es_rutinaria TEXT,
        peligro_factor TEXT,
        riesgo_asociado TEXT,
        tipo_riesgo TEXT,
        probabilidad INTEGER,
        consecuencia INTEGER,
        vep INTEGER,
        nivel_riesgo TEXT,
        medida_control TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, descripcion TEXT, area TEXT, severidad TEXT, rut_afectado TEXT, nombre_afectado TEXT, parte_cuerpo TEXT, estado TEXT)''')
    
    # Documental y Operativo
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, tipo_actividad TEXT, responsable_rut TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, trabajador_rut TEXT, nombre_trabajador TEXT, cargo_trabajador TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, cargo TEXT, lista_productos TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT)''')
    
    # Logística y Activos
    c.execute('''CREATE TABLE IF NOT EXISTS inventario_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, producto TEXT, stock_actual INTEGER, stock_minimo INTEGER, ubicacion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extintores (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, tipo TEXT, capacidad TEXT, ubicacion TEXT, fecha_vencimiento DATE, estado_inspeccion TEXT)''')
    
    # Gestión
    c.execute('''CREATE TABLE IF NOT EXISTS programa_anual (id INTEGER PRIMARY KEY AUTOINCREMENT, actividad TEXT, responsable TEXT, fecha_programada DATE, estado TEXT, fecha_ejecucion DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cphs_actas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_reunion DATE, nro_acta INTEGER, tipo_reunion TEXT, acuerdos TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS contratistas (id INTEGER PRIMARY KEY AUTOINCREMENT, rut_empresa TEXT, razon_social TEXT, estado_documental TEXT, fecha_vencimiento_f30 DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS protocolos_minsal (id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo TEXT, area TEXT, fecha_medicion DATE, resultado TEXT, estado TEXT)''')

    # Seed Inicial
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
        c.executemany("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion) VALUES (?,?,?,?)", [
            ("Casco Seguridad", 50, 5, "Bodega Central"),
            ("Lentes Seguridad", 100, 10, "Bodega Central"),
            ("Guantes Cabritilla", 200, 20, "Container"),
            ("Zapatos Seguridad", 30, 2, "Bodega Central")
        ])
        c.execute("INSERT INTO personal VALUES (?,?,?,?,?,?,?)", ("12.345.678-9", "JUAN PEREZ", "OPERADOR DE MAQUINARIA", "FAENA", date.today(), "ACTIVO", None))
        
        # Datos Matriz Ejemplo ISP
        datos_matriz = [
            ("Cosecha", "Operativo", "Operador Harvester", "Tala de árboles", "SI", "Pendiente abrupta (Ambiente)", "Volcamiento", "Seguridad", 2, 4, 8, "IMPORTANTE", "Cabina ROPS/FOPS, Procedimiento trabajo seguro"),
            ("Mantención", "Apoyo", "Mecánico", "Uso de esmeril angular", "SI", "Proyección de partículas (Equipo)", "Lesión ocular", "Seguridad", 4, 2, 8, "IMPORTANTE", "Uso de careta facial, Lentes de seguridad")
        ]
        c.executemany("""INSERT INTO matriz_iper 
            (proceso, tipo_proceso, puesto_trabajo, tarea, es_rutinaria, peligro_factor, riesgo_asociado, tipo_riesgo, probabilidad, consecuencia, vep, nivel_riesgo, medida_control) 
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", datos_matriz)

    conn.commit()
    conn.close()

def registrar_auditoria(usuario, accion, detalle):
    try:
        conn = get_conn()
        conn.execute("INSERT INTO auditoria (fecha, usuario, accion, detalle) VALUES (?,?,?,?)", (datetime.now(), usuario, accion, detalle))
        conn.commit(); conn.close()
    except: pass

def calcular_nivel_riesgo(vep):
    if vep <= 2: return "TOLERABLE"
    elif vep == 4: return "MODERADO"
    elif vep == 8: return "IMPORTANTE"
    elif vep >= 16: return "INTOLERABLE"
    return "NO CLASIFICADO"

def get_alertas():
    conn = get_conn()
    alertas = []
    hoy = date.today()
    
    # 1. Documentación Personal (DS44)
    trabs = pd.read_sql("SELECT rut, nombre FROM personal WHERE estado='ACTIVO'", conn)
    for i, t in trabs.iterrows():
        rut = t['rut']
        falta = []
        irl = pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(rut,)).iloc[0,0] > 0
        riohs = pd.read_sql("SELECT count(*) FROM registro_riohs WHERE rut_trabajador=?", conn, params=(rut,)).iloc[0,0] > 0
        if not irl: falta.append("IRL")
        if not riohs: falta.append("RIOHS")
        if falta: alertas.append(f"⚠️ <b>{t['nombre']}</b>: Falta {', '.join(falta)}")
    
    # 2. Stock EPP
    stock = pd.read_sql("SELECT producto, stock_actual, stock_minimo FROM inventario_epp", conn)
    for i, s in stock.iterrows():
        if s['stock_actual'] <= s['stock_minimo']: alertas.append(f"📦 <b>Stock Crítico:</b> {s['producto']} ({s['stock_actual']})")
    
    # 3. Extintores Vencidos
    exts = pd.read_sql("SELECT codigo, fecha_vencimiento FROM extintores", conn)
    for i, e in exts.iterrows():
        try:
            fv = datetime.strptime(e['fecha_vencimiento'], '%Y-%m-%d').date()
            if fv < hoy: alertas.append(f"🧯 <b>Extintor {e['codigo']}</b> VENCIDO")
        except: pass

    conn.close()
    return alertas

def get_incidentes_mes():
    conn = get_conn()
    try:
        mes_actual = datetime.now().strftime('%m')
        anio_actual = datetime.now().strftime('%Y')
        count = pd.read_sql(f"SELECT count(*) FROM incidentes WHERE strftime('%m', fecha) = '{mes_actual}' AND strftime('%Y', fecha) = '{anio_actual}'", conn).iloc[0,0]
    except: count = 0
    conn.close()
    return count

# ==============================================================================
# 3. MOTOR DOCUMENTAL ESTANDARIZADO (SGSST)
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO()
        self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=40, bottomMargin=40, leftMargin=40, rightMargin=40)
        self.elements = []
        self.styles = getSampleStyleSheet()
        self.titulo = titulo_doc
        self.codigo = codigo_doc
        self.logo_path = "logo_empresa.png"

    def _header(self):
        logo = Paragraph("<b>LOGO</b>", self.styles['Normal'])
        if os.path.exists(self.logo_path):
            try: logo = RLImage(self.logo_path, width=80, height=35)
            except: pass
        data = [[logo, Paragraph(f"SISTEMA DE GESTIÓN SST - DS44<br/><b>{self.titulo}</b>", ParagraphStyle('T', alignment=TA_CENTER, fontSize=11, fontName='Helvetica-Bold')), 
                 Paragraph(f"CÓDIGO: {self.codigo}<br/>VER: 05<br/>FECHA: {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle('C', alignment=TA_CENTER, fontSize=7))]]
        t = Table(data, colWidths=[90, 340, 90])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t); self.elements.append(Spacer(1, 20))

    def _signature_block(self, firma_b64, label="FIRMA TRABAJADOR"):
        sig_img = Paragraph("", self.styles['Normal'])
        if firma_b64:
            try: sig_img = RLImage(io.BytesIO(base64.b64decode(firma_b64)), width=120, height=50)
            except: pass
        data = [[sig_img, "HUELLA\nDACTILAR"], [label, ""]]
        t = Table(data, colWidths=[200, 60], rowHeights=[60, 20])
        t.setStyle(TableStyle([('ALIGN', (0,0), (0,0), 'CENTER'), ('VALIGN', (0,0), (0,0), 'BOTTOM'), ('LINEABOVE', (0,1), (0,1), 1, colors.black), ('GRID', (1,0), (1,1), 0.5, colors.grey), ('VALIGN', (1,0), (1,0), 'MIDDLE'), ('ALIGN', (1,0), (1,0), 'CENTER'), ('FONTSIZE', (1,0), (1,0), 6)]))
        main = Table([[t]], colWidths=[500]); main.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(Spacer(1, 20)); self.elements.append(main)

    def generar_epp(self, data):
        self._header()
        self.elements.append(Paragraph("I. ANTECEDENTES", self.styles['Heading3']))
        t_info = Table([[f"NOMBRE: {data['nombre']}", f"RUT: {data['rut']}"], [f"CARGO: {data['cargo']}", f"FECHA: {data['fecha']}"]], colWidths=[260, 260])
        t_info.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)]))
        self.elements.append(t_info); self.elements.append(Spacer(1, 15))
        try: items = ast.literal_eval(data['lista'])
        except: items = []
        t_data = [["CANT", "ELEMENTO", "MOTIVO"]]
        for i in items: t_data.append([str(i.get('cant','1')), i.get('prod','EPP'), i.get('mot','-')])
        t_prod = Table(t_data, colWidths=[40, 280, 200])
        t_prod.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(t_prod); self.elements.append(Spacer(1, 25))
        self.elements.append(Paragraph("Declaro recibir conforme (Art 53 DS594).", self.styles['Normal']))
        self.elements.append(Spacer(1, 30)); self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_riohs(self, data):
        self._header()
        self.elements.append(Paragraph(f"ENTREGA RIOHS: {data['nombre']} - {data['rut']}", self.styles['Heading3']))
        self.elements.append(Spacer(1, 20)); self.elements.append(Paragraph("Certifico haber recibido el Reglamento Interno de Orden, Higiene y Seguridad (Art 156 CT).", self.styles['Normal']))
        self.elements.append(Spacer(1, 40)); self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_irl(self, data, riesgos):
        self._header()
        self.elements.append(Paragraph(f"INFORMACIÓN RIESGOS LABORALES (IRL) - {data['nombre']}", self.styles['Heading3']))
        self.elements.append(Spacer(1, 10))
        r_data = [["PELIGRO (GEMA)", "RIESGO", "MEDIDA DE CONTROL"]]
        for r in riesgos: r_data.append([Paragraph(r[0], ParagraphStyle('s', fontSize=8)), Paragraph(r[1], ParagraphStyle('s', fontSize=8)), Paragraph(r[2], ParagraphStyle('s', fontSize=8))])
        t = Table(r_data, colWidths=[130, 130, 250])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
        self.elements.append(t); self.elements.append(Spacer(1, 30)); self.elements.append(Paragraph("Recibí información de riesgos (DS44).", self.styles['Normal'])); self.elements.append(Spacer(1, 30)); self._signature_block(None); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_asistencia_capacitacion(self, data, asis):
        self._header()
        self.elements.append(Paragraph(f"REGISTRO CAPACITACIÓN: {data['tema']}", self.styles['Heading3']))
        info = [[f"TEMA: {data['tema']}", f"TIPO: {data['tipo']}"], [f"RELATOR: {data['resp']}", f"FECHA: {data['fecha']}"]]
        tc = Table(info, colWidths=[260, 260])
        tc.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(tc); self.elements.append(Spacer(1, 15))
        a_data = [["NOMBRE", "RUT", "FIRMA"]]
        for a in asis: a_data.append([a['nombre'], a['rut'], "_______"])
        t = Table(a_data, colWidths=[200, 100, 150])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
        self.elements.append(t); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_diat(self, data):
        self._header()
        self.elements.append(Paragraph("DENUNCIA INDIVIDUAL ACCIDENTE (DIAT)", self.styles['Title']))
        self.elements.append(Paragraph(f"TRABAJADOR: {data['nombre']} | RUT: {data['rut']}", self.styles['Heading3']))
        self.elements.append(Paragraph(f"FECHA: {data['fecha']} | TIPO: {data['tipo']}", self.styles['Normal']))
        self.elements.append(Spacer(1, 20)); self.elements.append(Paragraph(data['descripcion'], self.styles['Normal']))
        self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

# ==============================================================================
# 4. FRONTEND (STREAMLIT)
# ==============================================================================
init_db()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user' not in st.session_state: st.session_state['user'] = "Invitado"

if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🔐 SGSST ERP")
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u == "admin" and p == "1234": 
                st.session_state['logged_in'] = True; st.session_state['user'] = u; registrar_auditoria(u, "LOGIN", "Acceso OK"); st.rerun()
            else: st.error("Error")
    st.stop()

with st.sidebar:
    st.title("MADERAS GÁLVEZ")
    st.caption("V114 - REAL FULL MASTER")
    menu = st.radio("MENÚ", ["📊 Dashboard", "🛡️ Matriz IPER (ISP)", "👥 Gestión Personas", "⚖️ Gestor Documental", "🦺 Logística EPP", "🎓 Capacitaciones", "🚨 Incidentes & DIAT", "📅 Plan Anual", "🧯 Extintores", "🏗️ Contratistas"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Cuadro de Mando</div>", unsafe_allow_html=True)
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.subheader("🔔 Estado de Cumplimiento")
        alertas = get_alertas()
        if alertas:
            with st.container(height=200):
                for a in alertas: st.markdown(f"<div class='alert-box alert-high'>{a}</div>", unsafe_allow_html=True)
        else: st.markdown("<div class='alert-box alert-ok'>✅ Todo al día</div>", unsafe_allow_html=True)
    with col_b:
        inc_count = get_incidentes_mes()
        st.metric("Incidentes (Mes)", inc_count, "Bajo Control" if inc_count == 0 else "Atención")
        st.metric("Stock Crítico", f"{len([a for a in alertas if 'Stock' in a])} Items", "Logística")

# --- 2. MATRIZ IPER (NUEVA ESTRUCTURA ISP) ---
elif menu == "🛡️ Matriz IPER (ISP)":
    st.markdown("<div class='main-header'>Matriz de Riesgos (Guía ISP 2024)</div>", unsafe_allow_html=True)
    tab_ver, tab_carga, tab_crear = st.tabs(["👁️ Ver Matriz", "📂 Carga Masiva Excel", "➕ Crear Riesgo"])
    conn = get_conn()
    
    with tab_ver:
        df_matriz = pd.read_sql("SELECT * FROM matriz_iper", conn)
        def highlight_riesgo(val):
            if val == 'TOLERABLE': return 'background-color: #81c784'
            elif val == 'MODERADO': return 'background-color: #ffb74d'
            elif val == 'IMPORTANTE': return 'background-color: #e57373'
            elif val == 'INTOLERABLE': return 'background-color: #d32f2f; color: white'
            return ''
        st.dataframe(df_matriz.style.applymap(highlight_riesgo, subset=['nivel_riesgo']), use_container_width=True)
        
        with st.expander("✏️ Editar Medidas"):
            edited_m = st.data_editor(df_matriz[['id', 'peligro_factor', 'medida_control']], key="edit_medidas")
            if st.button("Guardar Cambios Medidas"):
                c = conn.cursor()
                for i, r in edited_m.iterrows(): c.execute("UPDATE matriz_iper SET medida_control=? WHERE id=?", (r['medida_control'], r['id']))
                conn.commit(); st.success("Actualizado"); st.rerun()

    with tab_carga:
        st.subheader("Carga Masiva (Formato ISP)")
        up = st.file_uploader("Subir Excel Matriz", type=['xlsx'])
        if up:
            try:
                df_up = pd.read_excel(up)
                st.write("Previsualización:", df_up.head())
                if st.button("Procesar Matriz"):
                    c = conn.cursor()
                    for i, r in df_up.iterrows():
                        p = int(r.get('Probabilidad', 1))
                        cons = int(r.get('Consecuencia', 1))
                        vep = p * cons
                        nivel = calcular_nivel_riesgo(vep)
                        c.execute("""INSERT INTO matriz_iper (proceso, tipo_proceso, puesto_trabajo, tarea, es_rutinaria, peligro_factor, riesgo_asociado, tipo_riesgo, probabilidad, consecuencia, vep, nivel_riesgo, medida_control)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (r.get('Proceso',''), "Operativo", r.get('Puesto',''), r.get('Tarea',''), "SI", r.get('Peligro',''), r.get('Riesgo',''), "Seguridad", p, cons, vep, nivel, r.get('Medida','')))
                    conn.commit(); st.success("Carga OK"); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

    with tab_crear:
        with st.form("add_risk"):
            c1, c2, c3 = st.columns(3)
            proc = c1.text_input("Proceso"); puesto = c2.text_input("Puesto"); tarea = c3.text_input("Tarea")
            c4, c5 = st.columns(2)
            peligro = c4.text_input("Peligro (GEMA)"); riesgo = c5.text_input("Riesgo")
            c6, c7 = st.columns(2)
            prob = c6.selectbox("Probabilidad (P)", LISTA_PROBABILIDAD); cons = c7.selectbox("Consecuencia (C)", LISTA_CONSECUENCIA)
            medida = st.text_area("Medida Control")
            if st.form_submit_button("Guardar"):
                vep = prob * cons; nivel = calcular_nivel_riesgo(vep)
                conn.execute("""INSERT INTO matriz_iper (proceso, tipo_proceso, puesto_trabajo, tarea, es_rutinaria, peligro_factor, riesgo_asociado, tipo_riesgo, probabilidad, consecuencia, vep, nivel_riesgo, medida_control)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (proc, "Operativo", puesto, tarea, "SI", peligro, riesgo, "Seguridad", prob, cons, vep, nivel, medida))
                conn.commit(); st.success("Guardado"); st.rerun()
    conn.close()

# --- 3. GESTIÓN PERSONAS (COMPLETO) ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Personas (RH)</div>", unsafe_allow_html=True)
    tab_list, tab_carga, tab_new, tab_dig = st.tabs(["📋 Nómina", "📂 Carga Masiva", "➕ Nuevo", "🗂️ Carpeta"])
    conn = get_conn()
    
    with tab_list:
        df_p = pd.read_sql("SELECT rut, nombre, cargo, centro_costo, estado FROM personal", conn)
        edited = st.data_editor(df_p, key="edit_p", use_container_width=True)
        if st.button("💾 Guardar Cambios Nómina"):
            c = conn.cursor()
            for i, r in edited.iterrows(): c.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=?, estado=? WHERE rut=?", (r['nombre'], r['cargo'], r['centro_costo'], r['estado'], r['rut']))
            conn.commit(); st.success("Guardado")

    with tab_carga:
        up = st.file_uploader("Archivo Excel/CSV", type=['csv','xlsx'])
        if up:
            try:
                df = pd.read_csv(up) if up.name.endswith('.csv') else pd.read_excel(up)
                if st.button("Procesar"):
                    c = conn.cursor()
                    count = 0
                    for i, r in df.iterrows():
                        rut = str(r.get('RUT','')).strip(); nom = str(r.get('NOMBRE','')).strip(); car = str(r.get('CARGO','')).strip()
                        try: fec = pd.to_datetime(r.get('FECHA DE CONTRATO'), errors='coerce').date()
                        except: fec = date.today()
                        if rut and nom:
                            c.execute("INSERT OR REPLACE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (rut, nom, car, "FAENA", fec, "ACTIVO"))
                            count += 1
                    conn.commit(); st.success(f"Cargados {count}")
            except Exception as e: st.error(f"Error: {e}")

    with tab_new:
        with st.form("newp"):
            r = st.text_input("RUT"); n = st.text_input("Nombre"); c = st.selectbox("Cargo", LISTA_CARGOS)
            if st.form_submit_button("Guardar"): conn.execute("INSERT INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (r, n, c, "FAENA", date.today(), "ACTIVO")); conn.commit(); st.success("OK")

    with tab_dig:
        df_all = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        if not df_all.empty:
            sel = st.selectbox("Trabajador:", df_all['rut'] + " - " + df_all['nombre'])
            if QR_AVAILABLE: st.button("🪪 Ver Credencial")
    conn.close()

# --- 4. GESTOR DOCUMENTAL (CONECTADO) ---
elif menu == "⚖️ Gestor Documental":
    st.markdown("<div class='main-header'>Centro Documental (DS44)</div>", unsafe_allow_html=True)
    tab_irl, tab_riohs, tab_hist = st.tabs(["📄 IRL", "📘 RIOHS", "📂 Historial"])
    conn = get_conn()
    df_p = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    
    with tab_irl:
        sel = st.selectbox("Trabajador:", df_p['rut'] + " - " + df_p['nombre'])
        if st.button("Generar IRL (PDF)"):
            rut = sel.split(" - ")[0]; cargo = df_p[df_p['rut']==rut]['cargo'].values[0]
            # Búsqueda inteligente en Matriz
            riesgos = pd.read_sql("SELECT peligro_factor, riesgo_asociado, medida_control FROM matriz_iper WHERE puesto_trabajo LIKE ?", conn, params=(f'%{cargo}%',))
            if riesgos.empty: riesgos = pd.read_sql("SELECT peligro_factor, riesgo_asociado, medida_control FROM matriz_iper LIMIT 3", conn)
            pdf = DocumentosLegalesPDF("INFORMACIÓN RIESGOS LABORALES", "RG-GD-04").generar_irl({'nombre': sel.split(" - ")[1], 'rut': rut, 'cargo': cargo}, riesgos.values.tolist())
            st.download_button("Descargar PDF", pdf, f"IRL_{rut}.pdf", "application/pdf")

    with tab_riohs:
        sel_r = st.selectbox("Trabajador RIOHS:", df_p['rut'] + " | " + df_p['nombre'])
        tipo = st.selectbox("Formato", ["Físico", "Digital"])
        canvas = st_canvas(stroke_width=2, height=150, key="riohs_s")
        if st.button("Registrar Entrega"):
            if canvas.image_data is not None:
                img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
                conn.execute("INSERT INTO registro_riohs (fecha_entrega, rut_trabajador, nombre_trabajador, tipo_entrega, firma_b64) VALUES (?,?,?,?,?)", (date.today(), sel_r.split(" | ")[0], sel_r.split(" | ")[1], tipo, ib64))
                conn.commit()
                pdf = DocumentosLegalesPDF("RECEPCIÓN RIOHS", "RG-GD-03").generar_riohs({'nombre': sel_r.split(" | ")[1], 'rut': sel_r.split(" | ")[0], 'tipo': tipo, 'firma_b64': ib64})
                st.download_button("Descargar Acta", pdf, "RIOHS.pdf")

    with tab_hist:
        st.dataframe(pd.read_sql("SELECT * FROM registro_riohs", conn), use_container_width=True)
    conn.close()

# --- 5. LOGÍSTICA EPP (COMPLETO) ---
elif menu == "🦺 Logística EPP":
    st.markdown("<div class='main-header'>Gestión de EPP</div>", unsafe_allow_html=True)
    conn = get_conn()
    tab_ent, tab_inv = st.tabs(["Entrega", "Inventario"])
    
    with tab_inv:
        edited = st.data_editor(pd.read_sql("SELECT * FROM inventario_epp", conn), key="inv_ed", use_container_width=True)
        if st.button("Actualizar Stock"):
            c = conn.cursor(); c.execute("DELETE FROM inventario_epp")
            for i, r in edited.iterrows(): c.execute("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion) VALUES (?,?,?,?)", (r['producto'], r['stock_actual'], r['stock_minimo'], r['ubicacion']))
            conn.commit(); st.success("OK"); st.rerun()

    with tab_ent:
        df_p = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
        sel = st.selectbox("Trabajador:", df_p['rut'] + " | " + df_p['nombre'])
        inv = pd.read_sql("SELECT producto, stock_actual FROM inventario_epp WHERE stock_actual > 0", conn)
        
        if 'cart' not in st.session_state: st.session_state.cart = []
        c1, c2, c3 = st.columns(3)
        p = c1.selectbox("Producto", inv['producto']); q = c2.number_input("Cant", 1); m = c3.selectbox("Motivo", ["Nuevo", "Reposición", "Pérdida"])
        
        if st.button("Agregar"): st.session_state.cart.append({'prod': p, 'cant': q, 'mot': m})
        st.table(st.session_state.cart)
        
        canvas = st_canvas(stroke_width=2, height=150, key="epp_s")
        if st.button("Confirmar Entrega"):
            if canvas.image_data is not None:
                img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
                rut = sel.split(" | ")[0]; nom = sel.split(" | ")[1]; cargo = df_p[df_p['rut']==rut]['cargo'].values[0]
                
                c = conn.cursor()
                for i in st.session_state.cart: c.execute("UPDATE inventario_epp SET stock_actual = stock_actual - ? WHERE producto=?", (i['cant'], i['prod']))
                c.execute("INSERT INTO registro_epp (fecha_entrega, rut_trabajador, nombre_trabajador, cargo, lista_productos, firma_b64) VALUES (?,?,?,?,?,?)", (date.today(), rut, nom, cargo, str(st.session_state.cart), ib64))
                conn.commit()
                
                pdf = DocumentosLegalesPDF("COMPROBANTE EPP", "RG-GD-01").generar_epp({'nombre': nom, 'rut': rut, 'cargo': cargo, 'fecha': date.today(), 'lista': str(st.session_state.cart), 'firma_b64': ib64})
                st.download_button("Descargar PDF", pdf, "EPP.pdf")
                st.session_state.cart = []; st.success("Listo")
    conn.close()

# --- 6. INCIDENTES & DIAT ---
elif menu == "🚨 Incidentes & DIAT":
    st.markdown("<div class='main-header'>Accidentes (Ley 16.744)</div>", unsafe_allow_html=True)
    conn = get_conn()
    with st.form("inc"):
        fec = st.date_input("Fecha"); tipo = st.selectbox("Tipo", ["Accidente CTP", "Trayecto", "Incidente"])
        afec = st.selectbox("Afectado", pd.read_sql("SELECT nombre, rut FROM personal", conn)['nombre'])
        desc = st.text_area("Descripción")
        if st.form_submit_button("Guardar"):
            conn.execute("INSERT INTO incidentes (fecha, tipo, descripcion, nombre_afectado, estado) VALUES (?,?,?,?,?)", (fec, tipo, desc, afec, "ABIERTO"))
            conn.commit(); st.success("Registrado")
    
    st.divider()
    incs = pd.read_sql("SELECT * FROM incidentes ORDER BY id DESC", conn)
    if not incs.empty:
        sel_i = st.selectbox("Seleccione:", incs['id'].astype(str) + " - " + incs['nombre_afectado'])
        if st.button("Generar DIAT"):
            i_data = incs[incs['id']==int(sel_i.split(" - ")[0])].iloc[0]
            pdf = DocumentosLegalesPDF("DENUNCIA INDIVIDUAL", "DIAT").generar_diat({'nombre': i_data['nombre_afectado'], 'rut': "PENDIENTE", 'fecha': i_data['fecha'], 'tipo': i_data['tipo'], 'descripcion': i_data['descripcion']})
            st.download_button("Descargar DIAT", pdf, "DIAT.pdf")
    conn.close()

# --- 7. CAPACITACIONES (COMPLETO) ---
elif menu == "🎓 Capacitaciones":
    st.title("Capacitaciones"); conn = get_conn(); 
    with st.form("cap"):
        t = st.text_input("Tema"); tp = st.selectbox("Tipo", ["Inducción", "Charla"]); a = st.multiselect("Asistentes", pd.read_sql("SELECT rut, nombre FROM personal", conn)['nombre'])
        if st.form_submit_button("Guardar"):
            c = conn.cursor(); c.execute("INSERT INTO capacitaciones (fecha, tema, tipo_actividad, responsable_rut, estado) VALUES (?,?,?,?,?)", (date.today(), t, tp, "PREVENCIONISTA", "OK")); cid = c.lastrowid
            conn.commit(); st.success("OK")
    st.dataframe(pd.read_sql("SELECT * FROM capacitaciones", conn))
    conn.close()

# --- 8. PLAN ANUAL (COMPLETO) ---
elif menu == "📅 Plan Anual":
    st.title("Plan Anual"); conn = get_conn(); 
    st.data_editor(pd.read_sql("SELECT * FROM programa_anual", conn), key="plan_ed", num_rows="dynamic")
    conn.close()

# --- 9. EXTINTORES (COMPLETO) ---
elif menu == "🧯 Extintores":
    st.title("Extintores"); conn = get_conn(); 
    st.data_editor(pd.read_sql("SELECT * FROM extintores", conn), key="ext_ed", num_rows="dynamic")
    conn.close()

# --- 10. CONTRATISTAS (COMPLETO) ---
elif menu == "🏗️ Contratistas":
    st.title("Contratistas"); conn = get_conn(); 
    st.data_editor(pd.read_sql("SELECT * FROM contratistas", conn), key="cont_ed", num_rows="dynamic")
    conn.close()
