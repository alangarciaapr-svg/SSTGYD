import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
import io
import hashlib
import os
import time
import base64
from PIL import Image as PILImage
import matplotlib
import matplotlib.pyplot as plt
import plotly.express as px
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter, legal
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
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
# 1. CONFIGURACIÓN DEL SISTEMA
# ==============================================================================
st.set_page_config(page_title="SGSST ERP INTEGRAL", layout="wide", page_icon="🏗️")

DB_NAME = 'sgsst_v107_integral.db' # DB FINAL CON TODOS LOS MODULOS
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"
MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

# Estilos CSS
st.markdown("""
    <style>
    .main-header {font-size: 2.0rem; font-weight: 700; color: #2C3E50; border-bottom: 2px solid #8B0000; margin-bottom: 15px;}
    .alert-box {padding: 8px 12px; border-radius: 4px; margin-bottom: 6px; font-size: 0.85rem; font-weight: 500; display: flex; align-items: center;}
    .alert-high {background-color: #ffebee; color: #b71c1c; border-left: 4px solid #d32f2f;}
    .alert-med {background-color: #fff3e0; color: #ef6c00; border-left: 4px solid #ff9800;}
    .alert-ok {background-color: #e8f5e9; color: #2e7d32; border-left: 4px solid #388e3c;}
    </style>
""", unsafe_allow_html=True)

# LISTAS MAESTRAS
LISTA_CARGOS = ["GERENTE GENERAL", "PREVENCIONISTA DE RIESGOS", "JEFE DE PATIO", "OPERADOR DE ASERRADERO", "OPERADOR DE MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "MECANICO"]

# ==============================================================================
# 2. CAPA DE DATOS (SQL)
# ==============================================================================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # --- MÓDULOS BASE (V106) ---
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATETIME, usuario TEXT, accion TEXT, detalle TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS personal (rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, fecha_contrato DATE, estado TEXT, vigencia_examen_medico DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (id INTEGER PRIMARY KEY AUTOINCREMENT, cargo_asociado TEXT, proceso TEXT, peligro TEXT, riesgo TEXT, consecuencia TEXT, medida_control TEXT, metodo_correcto TEXT, criticidad TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, tipo_actividad TEXT, responsable_rut TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, trabajador_rut TEXT, nombre_trabajador TEXT, cargo_trabajador TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, cargo TEXT, lista_productos TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cphs_actas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_reunion DATE, nro_acta INTEGER, tipo_reunion TEXT, acuerdos TEXT, estado TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, descripcion TEXT, area TEXT, severidad TEXT, rut_afectado TEXT, nombre_afectado TEXT, estado TEXT)''')

    # --- MÓDULOS NUEVOS (V107) ---
    # Gestión de Extintores (DS 594)
    c.execute('''CREATE TABLE IF NOT EXISTS extintores (
        id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, tipo TEXT, capacidad TEXT, 
        ubicacion TEXT, fecha_vencimiento DATE, estado_inspeccion TEXT)''')
    
    # Programa de Trabajo (DS 44)
    c.execute('''CREATE TABLE IF NOT EXISTS programa_anual (
        id INTEGER PRIMARY KEY AUTOINCREMENT, actividad TEXT, responsable TEXT, 
        fecha_programada DATE, estado TEXT, fecha_ejecucion DATE)''')

    # Seed Inicial
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
        datos_matriz = [
            ("OPERADOR DE MAQUINARIA", "Cosecha", "Pendiente Abrupta", "Volcamiento", "Muerte", "Cabina ROPS/FOPS", "No operar >30%", "CRITICO"),
            ("MOTOSIERRISTA", "Tala", "Caída árbol", "Golpe", "Muerte", "Planificación caída", "Distancia seguridad", "CRITICO"),
            ("JEFE DE PATIO", "Logística", "Tránsito Maquinaria", "Atropello", "Muerte", "Chaleco Reflectante", "Contacto Visual", "ALTO")
        ]
        c.executemany("INSERT INTO matriz_iper (cargo_asociado, proceso, peligro, riesgo, consecuencia, medida_control, metodo_correcto, criticidad) VALUES (?,?,?,?,?,?,?,?)", datos_matriz)
        c.execute("INSERT INTO personal VALUES (?,?,?,?,?,?,?)", ("12.345.678-9", "JUAN PEREZ", "OPERADOR DE MAQUINARIA", "FAENA", date.today(), "ACTIVO", date(2026, 12, 31)))

    conn.commit()
    conn.close()

def registrar_auditoria(usuario, accion, detalle):
    try:
        conn = get_conn()
        conn.execute("INSERT INTO auditoria (fecha, usuario, accion, detalle) VALUES (?,?,?,?)", (datetime.now(), usuario, accion, detalle))
        conn.commit(); conn.close()
    except: pass

def get_alertas():
    conn = get_conn()
    alertas = []
    hoy = date.today()
    
    # 1. Alertas Personales
    trabs = pd.read_sql("SELECT rut, nombre FROM personal WHERE estado='ACTIVO'", conn)
    for i, t in trabs.iterrows():
        rut = t['rut']
        falta = []
        irl = pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(rut,)).iloc[0,0] > 0
        riohs = pd.read_sql("SELECT count(*) FROM registro_riohs WHERE rut_trabajador=?", conn, params=(rut,)).iloc[0,0] > 0
        if not irl: falta.append("IRL")
        if not riohs: falta.append("RIOHS")
        if falta: alertas.append(f"⚠️ <b>{t['nombre']}</b>: Falta {', '.join(falta)}")
    
    # 2. Alertas Extintores (NUEVO V107)
    exts = pd.read_sql("SELECT codigo, ubicacion, fecha_vencimiento FROM extintores", conn)
    for i, e in exts.iterrows():
        try:
            venc = datetime.strptime(e['fecha_vencimiento'], '%Y-%m-%d').date()
            if venc < hoy:
                alertas.append(f"🧯 <b>Extintor {e['codigo']} ({e['ubicacion']})</b>: VENCIDO")
            elif (venc - hoy).days < 30:
                alertas.append(f"🧯 <b>Extintor {e['codigo']}</b>: Vence pronto")
        except: pass

    conn.close()
    return alertas

# ==============================================================================
# 3. MOTOR DOCUMENTAL (REPORTLAB)
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO()
        self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=30, bottomMargin=30)
        self.elements = []
        self.styles = getSampleStyleSheet()
        self.titulo = titulo_doc
        self.codigo = codigo_doc
        self.logo_path = "logo_empresa.png"

    def _header(self):
        logo = Paragraph("<b>MADERAS GÁLVEZ</b>", self.styles['Normal'])
        if os.path.exists(self.logo_path):
            try: logo = RLImage(self.logo_path, width=90, height=40)
            except: pass
        data = [[logo, Paragraph(f"SISTEMA DE GESTIÓN SST - DS44<br/><b>{self.titulo}</b>", ParagraphStyle('T', alignment=TA_CENTER, fontSize=12, fontName='Helvetica-Bold')), 
                 Paragraph(f"CÓDIGO: {self.codigo}<br/>VER: 03<br/>FECHA: {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle('C', alignment=TA_CENTER, fontSize=8))]]
        t = Table(data, colWidths=[100, 320, 100])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t); self.elements.append(Spacer(1, 20))

    def _signature_block(self, firma_b64, label="FIRMA TRABAJADOR"):
        if firma_b64:
            try:
                img_data = base64.b64decode(firma_b64)
                img = RLImage(io.BytesIO(img_data), width=140, height=50)
                self.elements.append(Spacer(1, 10)); self.elements.append(img)
            except: pass
        self.elements.append(Paragraph(f"__________________________<br/>{label}", ParagraphStyle('C', alignment=TA_CENTER)))

    # --- MÉTODOS EXISTENTES (EPP, RIOHS, IRL, CAP) ---
    def generar_epp(self, data):
        self._header()
        items = eval(data['lista'])
        t_data = [["CANT", "DESCRIPCIÓN EPP"]]
        for i in items: t_data.append([str(i.split('(')[1].replace(')','')), i.split('(')[0]])
        t = Table(t_data, colWidths=[60, 460])
        t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(Paragraph(f"ENTREGA EPP A: {data['nombre']} - RUT: {data['rut']}", self.styles['Heading3']))
        self.elements.append(Spacer(1,10)); self.elements.append(t); self.elements.append(Spacer(1,30))
        self.elements.append(Paragraph("Declaro recibir conforme (Art 53 DS594).", self.styles['Normal'])); self.elements.append(Spacer(1,30))
        self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_riohs(self, data):
        self._header()
        self.elements.append(Paragraph(f"ENTREGA RIOHS A: {data['nombre']} - RUT: {data['rut']}", self.styles['Heading3']))
        self.elements.append(Spacer(1,20)); self.elements.append(Paragraph("Recibo Reglamento Interno (Art 156 CT).", self.styles['Normal']))
        self.elements.append(Spacer(1,40)); self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_irl(self, data, riesgos):
        self._header()
        self.elements.append(Paragraph(f"IRL - {data['nombre']} ({data['cargo']})", self.styles['Heading3']))
        self.elements.append(Spacer(1,10))
        r_data = [["PELIGRO", "RIESGO", "MEDIDA"]]
        for r in riesgos: r_data.append([Paragraph(r[0], ParagraphStyle('s', fontSize=8)), Paragraph(r[1], ParagraphStyle('s', fontSize=8)), Paragraph(r[3], ParagraphStyle('s', fontSize=8))])
        t = Table(r_data, colWidths=[120, 150, 250])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
        self.elements.append(t); self.elements.append(Spacer(1,30))
        self.elements.append(Paragraph("Recibí información de riesgos (DS44/DS40).", self.styles['Normal'])); self.elements.append(Spacer(1,30))
        self._signature_block(None); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_asistencia_capacitacion(self, data, asis):
        self._header()
        self.elements.append(Paragraph(f"CAPACITACIÓN: {data['tema']}", self.styles['Heading3']))
        a_data = [["NOMBRE", "RUT", "FIRMA"]]
        for a in asis: a_data.append([a['nombre'], a['rut'], "_______"])
        t = Table(a_data, colWidths=[200, 100, 150])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
        self.elements.append(Spacer(1,10)); self.elements.append(t); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    # --- NUEVO: GENERADOR DE DIAT (LEY 16.744) ---
    def generar_diat(self, data):
        self._header()
        self.elements.append(Paragraph("DENUNCIA INDIVIDUAL DE ACCIDENTE DEL TRABAJO (DIAT)", self.styles['Title']))
        self.elements.append(Spacer(1, 20))
        
        # Sección A: Empleador
        self.elements.append(Paragraph("A. IDENTIFICACIÓN DEL EMPLEADOR", self.styles['Heading3']))
        emp = [["RAZÓN SOCIAL:", "MADERAS GÁLVEZ LTDA"], ["RUT:", "77.110.060-0"], ["DIRECCIÓN:", "RUTA 215 KM 12, OSORNO"]]
        t1 = Table(emp, colWidths=[120, 350]); t1.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(t1); self.elements.append(Spacer(1, 15))
        
        # Sección B: Trabajador
        self.elements.append(Paragraph("B. IDENTIFICACIÓN DEL TRABAJADOR", self.styles['Heading3']))
        trab = [["NOMBRE:", data['nombre']], ["RUT:", data['rut']], ["CARGO:", "VERIFICAR EN CONTRATO"]]
        t2 = Table(trab, colWidths=[120, 350]); t2.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(t2); self.elements.append(Spacer(1, 15))
        
        # Sección C: Accidente
        self.elements.append(Paragraph("C. DATOS DEL ACCIDENTE", self.styles['Heading3']))
        acc = [["FECHA:", str(data['fecha'])], ["TIPO:", data['tipo']], ["LUGAR:", data['area']], ["GRAVEDAD:", data['severidad']]]
        t3 = Table(acc, colWidths=[120, 350]); t3.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(t3); self.elements.append(Spacer(1, 15))
        
        self.elements.append(Paragraph("<b>DESCRIPCIÓN BREVE:</b>", self.styles['Normal']))
        self.elements.append(Paragraph(data['descripcion'], self.styles['Normal']))
        self.elements.append(Spacer(1, 40))
        
        self.elements.append(Paragraph("__________________________<br/>FIRMA REPRESENTANTE LEGAL", ParagraphStyle('C', alignment=TA_CENTER)))
        
        self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

# ==============================================================================
# 4. FRONTEND
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
    st.caption("V107 - Integral Suite")
    menu = st.radio("MENÚ", ["📊 Dashboard", "📅 Plan Anual (DS44)", "👥 Gestión Personas", "🛡️ Matriz IPER", "🧯 Extintores (DS594)", "⚖️ Generador IRL", "🦺 Entrega EPP", "📘 Entrega RIOHS", "🎓 Capacitaciones", "🚨 Incidentes & DIAT"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# --- DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Cuadro de Mando Integral</div>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.subheader("🔔 Estado de Cumplimiento")
        alertas = get_alertas()
        if alertas:
            with st.container(height=200):
                for a in alertas: st.markdown(f"<div class='alert-box alert-high'>{a}</div>", unsafe_allow_html=True)
        else: st.markdown("<div class='alert-box alert-ok'>✅ Sistema al día.</div>", unsafe_allow_html=True)
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Accidentabilidad", "2.1%", "-0.2%")
        k2.metric("Siniestralidad", "12.5", "0%")
        k3.metric("Cumplimiento Plan", "45%", "En Proceso")

    with col_b:
        st.write("**Resumen Actividad**")
        conn = get_conn()
        audit = pd.read_sql("SELECT accion, fecha FROM auditoria ORDER BY id DESC LIMIT 5", conn)
        st.dataframe(audit, use_container_width=True)
        conn.close()

# --- MÓDULO PLAN ANUAL (NUEVO V107) ---
elif menu == "📅 Plan Anual (DS44)":
    st.markdown("<div class='main-header'>Programa de Trabajo de SST</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    c1, c2 = st.columns([1, 2])
    with c1:
        with st.form("plan"):
            act = st.text_input("Actividad")
            resp = st.text_input("Responsable")
            fec = st.date_input("Fecha Programada")
            if st.form_submit_button("Agendar"):
                conn.execute("INSERT INTO programa_anual (actividad, responsable, fecha_programada, estado) VALUES (?,?,?,?)", (act, resp, fec, "PENDIENTE"))
                conn.commit(); st.success("Agendado"); st.rerun()
                
    with c2:
        df = pd.read_sql("SELECT * FROM programa_anual ORDER BY fecha_programada", conn)
        if not df.empty:
            prog = len(df[df['estado']=='REALIZADO']) / len(df)
            st.progress(prog)
            st.caption(f"Avance del Plan: {int(prog*100)}%")
            st.dataframe(df, use_container_width=True)
            
            # Marcar como realizado
            act_id = st.selectbox("Marcar como Realizado:", df['id'].astype(str) + " - " + df['actividad'])
            if st.button("✅ Confirmar Realización"):
                conn.execute("UPDATE programa_anual SET estado='REALIZADO', fecha_ejecucion=? WHERE id=?", (date.today(), int(act_id.split(" - ")[0])))
                conn.commit(); st.rerun()
    conn.close()

# --- MÓDULO EXTINTORES (NUEVO V107) ---
elif menu == "🧯 Extintores (DS594)":
    st.markdown("<div class='main-header'>Gestión de Extintores</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    tab_inv, tab_alert = st.tabs(["Inventario", "Alertas Vencimiento"])
    
    with tab_inv:
        with st.form("ext"):
            c1, c2 = st.columns(2)
            cod = c1.text_input("Código Interno")
            tipo = c2.selectbox("Tipo", ["PQS", "CO2", "Agua"])
            cap = c1.selectbox("Capacidad", ["2KG", "4KG", "6KG", "10KG"])
            ubic = c2.text_input("Ubicación")
            venc = st.date_input("Vencimiento Carga")
            if st.form_submit_button("Registrar Extintor"):
                conn.execute("INSERT INTO extintores (codigo, tipo, capacidad, ubicacion, fecha_vencimiento, estado_inspeccion) VALUES (?,?,?,?,?,?)",
                            (cod, tipo, cap, ubic, venc, "OK"))
                conn.commit(); st.success("Guardado"); st.rerun()
        
        st.dataframe(pd.read_sql("SELECT * FROM extintores", conn), use_container_width=True)

    with tab_alert:
        df_e = pd.read_sql("SELECT * FROM extintores", conn)
        alert_count = 0
        for i, row in df_e.iterrows():
            fv = datetime.strptime(row['fecha_vencimiento'], '%Y-%m-%d').date()
            if fv < date.today():
                st.error(f"🔴 VENCIDO: Extintor {row['codigo']} en {row['ubicacion']}")
                alert_count += 1
            elif (fv - date.today()).days < 30:
                st.warning(f"🟡 POR VENCER: Extintor {row['codigo']} en {row['ubicacion']}")
                alert_count += 1
        if alert_count == 0: st.success("Todos los equipos operativos.")
    conn.close()

# --- GESTIÓN PERSONAS ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Personas (RH)</div>", unsafe_allow_html=True)
    tab_list, tab_carga, tab_new = st.tabs(["📋 Nómina & Edición", "📂 Carga Masiva", "➕ Nuevo Manual"])
    conn = get_conn()
    with tab_list:
        df_p = pd.read_sql("SELECT rut, nombre, cargo, centro_costo, estado FROM personal", conn)
        edited_df = st.data_editor(df_p, num_rows="dynamic", key="editor_personal", use_container_width=True)
        if st.button("💾 Guardar Cambios"):
            c = conn.cursor()
            for i, r in edited_df.iterrows(): c.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=?, estado=? WHERE rut=?", (r['nombre'], r['cargo'], r['centro_costo'], r['estado'], r['rut']))
            conn.commit(); st.success("Actualizado.")
    with tab_carga:
        up = st.file_uploader("Excel/CSV", type=['csv','xlsx'])
        if up:
            try:
                df = pd.read_csv(up) if up.name.endswith('.csv') else pd.read_excel(up)
                if st.button("Procesar"):
                    c = conn.cursor()
                    for i, r in df.iterrows():
                        fec = date.today() # Simplificado para evitar error
                        c.execute("INSERT OR REPLACE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", 
                                 (str(r.get('RUT','')), str(r.get('NOMBRE','')), str(r.get('CARGO','')), "FAENA", fec, "ACTIVO"))
                    conn.commit(); st.success("Carga OK")
            except Exception as e: st.error(f"Error: {e}")
    with tab_new:
        with st.form("newp"):
            r = st.text_input("RUT"); n = st.text_input("Nombre"); c = st.selectbox("Cargo", LISTA_CARGOS)
            if st.form_submit_button("Guardar"): conn.execute("INSERT INTO personal VALUES (?,?,?,?,?,?,?)", (r, n, c, "FAENA", date.today(), "ACTIVO", None)); conn.commit(); st.success("OK")
    conn.close()

# --- MÓDULOS OPERATIVOS CONSERVADOS ---
elif menu == "🛡️ Matriz IPER":
    st.title("Matriz IPER"); conn = get_conn(); st.data_editor(pd.read_sql("SELECT * FROM matriz_iper", conn), key="iper"); conn.close()

elif menu == "⚖️ Generador IRL":
    st.title("Generador IRL (DS44)"); conn = get_conn()
    df = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    sel = st.selectbox("Trabajador:", df['rut'] + " - " + df['nombre'])
    if st.button("Generar IRL"):
        rut = sel.split(" - ")[0]; cargo = df[df['rut']==rut]['cargo'].values[0]
        riesgos = pd.read_sql("SELECT peligro, riesgo, consecuencia, medida_control, metodo_correcto FROM matriz_iper WHERE cargo_asociado=?", conn, params=(cargo,))
        if riesgos.empty: riesgos = pd.read_sql("SELECT peligro, riesgo, consecuencia, medida_control, metodo_correcto FROM matriz_iper LIMIT 3", conn)
        pdf = DocumentosLegalesPDF("INFORMACIÓN RIESGOS LABORALES", "RG-GD-04").generar_irl({'nombre': sel.split(" - ")[1], 'rut': rut, 'cargo': cargo}, riesgos.values.tolist())
        st.download_button("Descargar PDF", pdf, f"IRL_{rut}.pdf", "application/pdf")
    conn.close()

elif menu == "🦺 Entrega EPP":
    st.title("EPP"); conn = get_conn(); df = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn); sel = st.selectbox("Trabajador:", df['rut'] + " | " + df['nombre'])
    if 'cart' not in st.session_state: st.session_state.cart = []
    p = st.selectbox("Prod", ["Casco", "Lentes"]); q = st.number_input("Cant", 1); 
    if st.button("Agregar"): st.session_state.cart.append(f"{p} ({q})")
    st.write(st.session_state.cart); canvas = st_canvas(stroke_width=2, height=150, key="epp")
    if st.button("Guardar"):
        if canvas.image_data is not None:
            img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
            rut = sel.split(" | ")[0]; cargo = df[df['rut']==rut]['cargo'].values[0]
            conn.execute("INSERT INTO registro_epp (fecha_entrega, rut_trabajador, nombre_trabajador, cargo, lista_productos, firma_b64) VALUES (?,?,?,?,?,?)", (date.today(), rut, sel.split(" | ")[1], cargo, str(st.session_state.cart), ib64))
            conn.commit(); st.success("OK"); st.session_state.cart = []
            pdf = DocumentosLegalesPDF("COMPROBANTE EPP", "RG-GD-01").generar_epp({'nombre': sel.split(" | ")[1], 'rut': rut, 'cargo': cargo, 'fecha': date.today(), 'lista': str(st.session_state.cart), 'firma_b64': ib64})
            st.download_button("Descargar PDF", pdf, "EPP.pdf")
    conn.close()

elif menu == "📘 Entrega RIOHS":
    st.title("RIOHS"); conn = get_conn(); df = pd.read_sql("SELECT rut, nombre FROM personal", conn); sel = st.selectbox("Trabajador", df['rut']+" | "+df['nombre']); canvas = st_canvas(stroke_width=2, height=150, key="riohs")
    if st.button("Registrar"):
        if canvas.image_data is not None:
            img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); ib64 = base64.b64encode(b.getvalue()).decode()
            conn.execute("INSERT INTO registro_riohs (fecha_entrega, rut_trabajador, nombre_trabajador, tipo_entrega, firma_b64) VALUES (?,?,?,?,?)", (date.today(), sel.split(" | ")[0], sel.split(" | ")[1], "Físico", ib64))
            conn.commit(); st.success("OK"); pdf = DocumentosLegalesPDF("RECEPCIÓN RIOHS", "RG-GD-03").generar_riohs({'nombre': sel.split(" | ")[1], 'rut': sel.split(" | ")[0], 'tipo': 'Físico', 'firma_b64': ib64})
            st.download_button("Descargar", pdf, "RIOHS.pdf")
    conn.close()

elif menu == "🎓 Capacitaciones":
    st.title("Capacitaciones"); conn = get_conn(); 
    with st.form("c"): 
        t = st.text_input("Tema"); a = st.multiselect("Asistentes", pd.read_sql("SELECT rut, nombre FROM personal", conn)['rut'].astype(str) + " - " + pd.read_sql("SELECT nombre FROM personal", conn)['nombre'])
        if st.form_submit_button("Guardar"):
            c = conn.cursor(); c.execute("INSERT INTO capacitaciones (fecha, tema, estado) VALUES (?,?,?)", (date.today(), t, "OK")); cid = c.lastrowid
            for x in a: c.execute("INSERT INTO asistencia_capacitacion (capacitacion_id, trabajador_rut, nombre_trabajador, estado) VALUES (?,?,?,?)", (cid, x.split(" - ")[0], x.split(" - ")[1], "OK"))
            conn.commit(); st.success("Guardado")
    conn.close()

# --- INCIDENTES & DIAT (MEJORADO V107) ---
elif menu == "🚨 Incidentes & DIAT":
    st.markdown("<div class='main-header'>Gestión de Accidentes (Ley 16.744)</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    with st.form("inc"):
        st.subheader("Reporte Inmediato")
        fec = st.date_input("Fecha"); tipo = st.selectbox("Tipo", ["Accidente CTP", "Trayecto", "Incidente"])
        afectado = st.selectbox("Afectado", pd.read_sql("SELECT rut, nombre FROM personal", conn)['rut'].astype(str) + " | " + pd.read_sql("SELECT nombre FROM personal", conn)['nombre'])
        desc = st.text_area("Relato")
        if st.form_submit_button("Guardar Reporte"):
            conn.execute("INSERT INTO incidentes (fecha, tipo, descripcion, rut_afectado, nombre_afectado, estado) VALUES (?,?,?,?,?,?)",
                        (fec, tipo, desc, afectado.split(" | ")[0], afectado.split(" | ")[1], "ABIERTO"))
            conn.commit(); st.success("Registrado")
    
    st.divider()
    st.subheader("Generación DIAT (Oficial)")
    incs = pd.read_sql("SELECT * FROM incidentes ORDER BY id DESC", conn)
    if not incs.empty:
        sel_inc = st.selectbox("Seleccione Incidente:", incs['id'].astype(str) + " - " + incs['nombre_afectado'])
        if st.button("📄 Generar PDF DIAT"):
            i_data = incs[incs['id']==int(sel_inc.split(" - ")[0])].iloc[0]
            pdf = DocumentosLegalesPDF("DENUNCIA INDIVIDUAL", "DIAT").generar_diat({
                'nombre': i_data['nombre_afectado'], 'rut': i_data['rut_afectado'], 
                'fecha': i_data['fecha'], 'tipo': i_data['tipo'], 
                'area': 'FAENA', 'severidad': 'GRAVE', 'descripcion': i_data['descripcion']
            })
            st.download_button("Descargar DIAT", pdf, "DIAT.pdf", "application/pdf")
    conn.close()
