import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
import io
import hashlib
import os
import time
import base64
import uuid
from PIL import Image as PILImage
import matplotlib
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from fpdf import FPDF
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter, legal
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from streamlit_drawable_canvas import st_canvas

# Manejo seguro de librería QR (Para evitar caída del servidor)
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
st.set_page_config(page_title="SGSST ULTIMATE ERP", layout="wide", page_icon="🛡️")

DB_NAME = 'sgsst_erp_ultimate.db'
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"
MESES_ORDEN = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

# Estilos CSS
st.markdown("""
    <style>
    .main-header {font-size: 2.2rem; font-weight: 700; color: #2C3E50; border-bottom: 2px solid #8B0000; margin-bottom: 20px;}
    .kpi-card {background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #8B0000; text-align: center;}
    .alert-box {padding: 10px; border-radius: 5px; margin-bottom: 5px; font-weight: bold;}
    .alert-high {background-color: #ffcdd2; color: #b71c1c;}
    </style>
""", unsafe_allow_html=True)

# LISTAS MAESTRAS
LISTA_CARGOS = [
    "GERENTE GENERAL", "PREVENCIONISTA DE RIESGOS", "JEFE DE PATIO", 
    "OPERADOR DE ASERRADERO", "OPERADOR DE MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "MECANICO"
]

# ==============================================================================
# 2. CAPA DE DATOS (SQL) - ARQUITECTURA COMPLETA
# ==============================================================================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # 1. Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    
    # 2. Personal (RRHH)
    c.execute('''CREATE TABLE IF NOT EXISTS personal (
        rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, 
        fecha_contrato DATE, estado TEXT)''')
    
    # 3. Matriz IPER (Cerebro de Riesgos)
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cargo_asociado TEXT, proceso TEXT, 
        peligro TEXT, riesgo TEXT, consecuencia TEXT, medida_control TEXT, metodo_correcto TEXT, criticidad TEXT)''')
    
    # 4. Operaciones
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, 
        tipo_actividad TEXT, responsable_rut TEXT, estado TEXT)''')
        
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (
        id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, 
        trabajador_rut TEXT, estado TEXT, fecha_firma DATETIME)''')

    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, 
        rut_trabajador TEXT, nombre_trabajador TEXT, cargo TEXT, lista_productos TEXT, firma_b64 TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE,
        rut_trabajador TEXT, nombre_trabajador TEXT, tipo_entrega TEXT, firma_b64 TEXT)''')

    # --- SEEDING (Datos Iniciales si está vacío) ---
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
        
        # Datos Matriz Iniciales (8 Columnas Correctas)
        datos_matriz = [
            ("OPERADOR DE MAQUINARIA", "Cosecha", "Pendiente Abrupta", "Volcamiento", "Muerte", "Cabina ROPS/FOPS", "No operar >30%", "CRITICO"),
            ("MOTOSIERRISTA", "Tala", "Caída árbol", "Golpe", "Muerte", "Planificación caída", "Distancia seguridad", "CRITICO"),
            ("JEFE DE PATIO", "Logística", "Tránsito Maquinaria", "Atropello", "Muerte", "Chaleco Reflectante", "Contacto Visual", "ALTO")
        ]
        c.executemany("INSERT INTO matriz_iper (cargo_asociado, proceso, peligro, riesgo, consecuencia, medida_control, metodo_correcto, criticidad) VALUES (?,?,?,?,?,?,?,?)", datos_matriz)
        
        # Personal
        c.execute("INSERT INTO personal VALUES (?,?,?,?,?,?)", ("12.345.678-9", "JUAN PEREZ", "OPERADOR DE MAQUINARIA", "FAENA", date.today(), "ACTIVO"))

    conn.commit()
    conn.close()

# ==============================================================================
# 3. LÓGICA DE NEGOCIO Y REPORTES
# ==============================================================================
def get_alertas():
    conn = get_conn()
    alertas = []
    # Alerta ODI faltante
    trabs = pd.read_sql("SELECT rut, nombre FROM personal WHERE estado='ACTIVO'", conn)
    for i, t in trabs.iterrows():
        # Lógica simulada: Si no tiene capacitaciones, falta ODI
        count = pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(t['rut'],)).iloc[0,0]
        if count == 0:
            alertas.append(f"Falta ODI/Inducción para: {t['nombre']}")
    conn.close()
    return alertas

def generar_credencial_pdf(data_t):
    buffer = BytesIO()
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(buffer, pagesize=(240, 150)) # Tamaño credencial
    c.setFillColor(HexColor(COLOR_PRIMARY))
    c.rect(0, 115, 240, 35, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 10); c.drawString(10, 130, "MADERAS GÁLVEZ - CREDENCIAL")
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 12); c.drawString(10, 95, data_t['nombre'][:22])
    c.setFont("Helvetica", 9); c.drawString(10, 75, f"RUT: {data_t['rut']}"); c.drawString(10, 60, f"CARGO: {data_t['cargo']}")
    
    # QR Seguro
    if QR_AVAILABLE:
        try:
            qr = qrcode.QRCode(box_size=5, border=1)
            qr.add_data(f"{data_t['rut']}|{data_t['cargo']}|SGSST")
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            qr_bytes = BytesIO(); img.save(qr_bytes, format='PNG'); qr_bytes.seek(0)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(qr_bytes.getvalue()); tmp_name = tmp.name
            c.drawImage(tmp_name, 160, 20, width=70, height=70)
        except: pass
        
    c.save()
    buffer.seek(0)
    return buffer

def generar_odi_pdf_sql(rut_trabajador):
    conn = get_conn()
    trab = pd.read_sql("SELECT * FROM personal WHERE rut=?", conn, params=(rut_trabajador,)).iloc[0]
    # Busca riesgos en la Matriz SQL
    riesgos = pd.read_sql("SELECT peligro, riesgo, medida_control FROM matriz_iper WHERE cargo_asociado=?", conn, params=(trab['cargo'],))
    if riesgos.empty: # Fallback si no hay riesgos específicos
        riesgos = pd.read_sql("SELECT peligro, riesgo, medida_control FROM matriz_iper LIMIT 3", conn)
    conn.close()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"OBLIGACIÓN DE INFORMAR (ODI) - {trab['nombre']}", styles['Heading1']))
    elements.append(Spacer(1, 10))
    
    data = [["PELIGRO", "RIESGO", "MEDIDA CONTROL"]]
    for i, r in riesgos.iterrows():
        data.append([r['peligro'], r['riesgo'], r['medida_control']])
    
    t = Table(data, colWidths=[130, 130, 250])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
    elements.append(t)
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("__________________________<br/>FIRMA TRABAJADOR", ParagraphStyle('C', alignment=TA_CENTER)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==============================================================================
# 4. FRONTEND (STREAMLIT)
# ==============================================================================
init_db()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# LOGIN
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🔐 ERP SGSST")
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u == "admin" and p == "1234": st.session_state['logged_in'] = True; st.rerun()
            else: st.error("Error")
    st.stop()

# SIDEBAR
with st.sidebar:
    st.title("MADERAS GÁLVEZ")
    menu = st.radio("MENÚ PRINCIPAL", ["📊 Dashboard & Alertas", "👥 Gestión de Personas", "🛡️ Matriz IPER", "⚖️ Generador ODI/IRL", "🦺 Entrega EPP", "📘 Entrega RIOHS", "🎓 Capacitaciones"])
    if st.button("Salir"): st.session_state['logged_in'] = False; st.rerun()

# --- MÓDULO DASHBOARD & ALERTAS ---
if menu == "📊 Dashboard & Alertas":
    st.markdown("<div class='main-header'>Cuadro de Mando Integral</div>", unsafe_allow_html=True)
    
    # Alertas
    alertas = get_alertas()
    if alertas:
        st.error(f"⚠️ Se detectaron {len(alertas)} alertas de cumplimiento.")
        with st.expander("Ver Detalles de Alertas"):
            for a in alertas: st.markdown(f"<div class='alert-box alert-high'>{a}</div>", unsafe_allow_html=True)
    
    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tasa Accidentabilidad", "2.1%", "-0.2%")
    k2.metric("Tasa Siniestralidad", "12.5", "Estable")
    k3.metric("Cumplimiento Prog.", "92%", "+2%")
    k4.metric("Días sin Accidentes", "145", "Récord")
    
    # Gráficos
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("### 📉 Accidentabilidad Anual")
        df_g = pd.DataFrame({'Mes': MESES[:6], 'Tasa': [3, 2.5, 2.1, 2.0, 2.2, 2.1]})
        fig = px.line(df_g, x='Mes', y='Tasa', markers=True)
        st.plotly_chart(fig, use_container_width=True)
    with g2:
        st.markdown("### 🚨 Hallazgos por Área")
        df_p = pd.DataFrame({'Area': ['Faena', 'Patio', 'Aserradero'], 'Hallazgos': [10, 5, 2]})
        fig2 = px.pie(df_p, values='Hallazgos', names='Area')
        st.plotly_chart(fig2, use_container_width=True)

# --- MÓDULO GESTIÓN PERSONAS (CON CARPETA DIGITAL) ---
elif menu == "👥 Gestión de Personas":
    st.markdown("<div class='main-header'>Capital Humano</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 Base de Datos", "📂 Carpeta Digital"])
    conn = get_conn()
    
    with tab1:
        df = pd.read_sql("SELECT * FROM personal", conn)
        st.dataframe(df, use_container_width=True)
        with st.expander("➕ Nuevo Trabajador"):
            with st.form("add_p"):
                c1, c2 = st.columns(2)
                rut = c1.text_input("RUT"); nom = c2.text_input("Nombre")
                cargo = c1.selectbox("Cargo", LISTA_CARGOS); cc = c2.selectbox("Centro Costo", ["FAENA", "ASERRADERO", "OFICINA"])
                if st.form_submit_button("Guardar"):
                    try:
                        conn.execute("INSERT INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (rut, nom, cargo, cc, date.today(), "ACTIVO"))
                        conn.commit(); st.success("Guardado"); st.rerun()
                    except: st.error("Error: RUT duplicado")
    
    with tab2:
        df = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        if not df.empty:
            sel = st.selectbox("Buscar Trabajador:", df['rut'] + " - " + df['nombre'])
            rut_sel = sel.split(" - ")[0]
            
            # Datos Resumen
            p = pd.read_sql("SELECT * FROM personal WHERE rut=?", conn, params=(rut_sel,)).iloc[0]
            caps = pd.read_sql("SELECT * FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(rut_sel,))
            epps = pd.read_sql("SELECT * FROM registro_epp WHERE rut_trabajador=?", conn, params=(rut_sel,))
            
            st.markdown(f"### 👤 {p['nombre']}")
            st.markdown(f"**Cargo:** {p['cargo']} | **Estado:** {p['estado']}")
            
            c_a, c_b = st.columns(2)
            with c_a:
                st.info(f"🎓 Capacitaciones: {len(caps)}")
                if QR_AVAILABLE:
                    if st.button("🪪 Generar Credencial"):
                        pdf = generar_credencial_pdf(p)
                        st.download_button("Descargar Credencial", pdf, f"Credencial_{p['rut']}.pdf", "application/pdf")
            with c_b:
                st.info(f"🦺 EPPs Entregados: {len(epps)}")
            
            st.markdown("#### Historial Reciente")
            st.dataframe(epps[['fecha_entrega', 'cargo', 'lista_productos']], use_container_width=True)
    conn.close()

# --- MÓDULO MATRIZ IPER (SQL EDITABLE) ---
elif menu == "🛡️ Matriz IPER":
    st.markdown("<div class='main-header'>Matriz de Riesgos (Editable)</div>", unsafe_allow_html=True)
    conn = get_conn()
    df_iper = pd.read_sql("SELECT id, cargo_asociado, peligro, riesgo, criticidad FROM matriz_iper", conn)
    
    edited = st.data_editor(df_iper, num_rows="dynamic", key="iper_ed", use_container_width=True)
    
    if st.button("💾 Actualizar Matriz"):
        c = conn.cursor()
        # Actualización simplificada para demo (borra e inserta para mantener consistencia visual)
        c.execute("DELETE FROM matriz_iper") 
        # Recuperar datos completos para re-insertar (en app real usar UPDATE por ID)
        # Aquí simplificamos asumiendo que el usuario edita lo visible
        for i, row in edited.iterrows():
            c.execute("INSERT INTO matriz_iper (cargo_asociado, peligro, riesgo, criticidad, medida_control) VALUES (?,?,?,?,?)",
                     (row['cargo_asociado'], row['peligro'], row['riesgo'], row['criticidad'], "Ver Procedimiento"))
        conn.commit()
        st.success("Matriz actualizada. Los nuevos ODI reflejarán estos cambios.")
        time.sleep(1)
        st.rerun()
    conn.close()

# --- MÓDULO GENERADOR ODI (CONECTADO A MATRIZ) ---
elif menu == "⚖️ Generador ODI/IRL":
    st.markdown("<div class='main-header'>Generador Documental</div>", unsafe_allow_html=True)
    conn = get_conn()
    df = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    
    sel = st.selectbox("Seleccione Trabajador:", df['rut'] + " - " + df['nombre'])
    if sel:
        rut = sel.split(" - ")[0]
        cargo = df[df['rut']==rut]['cargo'].values[0]
        st.info(f"Generando ODI para cargo: **{cargo}** usando datos de la Matriz IPER.")
        
        if st.button("📄 Generar PDF ODI"):
            pdf = generar_odi_pdf_sql(rut)
            st.download_button("📥 Descargar ODI", pdf, f"ODI_{rut}.pdf", "application/pdf")
    conn.close()

# --- MÓDULO EPP (OPERATIVO) ---
elif menu == "🦺 Entrega EPP":
    st.title("Registro EPP")
    conn = get_conn()
    df = pd.read_sql("SELECT rut, nombre FROM personal", conn)
    sel = st.selectbox("Trabajador:", df['rut'] + " | " + df['nombre'])
    
    if 'epp_cart' not in st.session_state: st.session_state.epp_cart = []
    
    c1, c2 = st.columns(2)
    prod = c1.selectbox("Producto", ["Casco", "Lentes", "Guantes", "Zapatos"])
    cant = c2.number_input("Cantidad", 1, 10, 1)
    if st.button("Agregar"): st.session_state.epp_cart.append(f"{prod} ({cant})")
    
    st.write(st.session_state.epp_cart)
    canvas = st_canvas(stroke_width=2, height=150, key="epp_sig")
    
    if st.button("Guardar Entrega"):
        if canvas.image_data is not None:
            rut = sel.split(" | ")[0]
            img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
            conn.execute("INSERT INTO registro_epp (fecha_entrega, rut_trabajador, nombre_trabajador, lista_productos, firma_b64) VALUES (?,?,?,?,?)",
                        (date.today(), rut, sel.split(" | ")[1], str(st.session_state.epp_cart), img_str))
            conn.commit()
            st.success("Guardado")
            st.session_state.epp_cart = []
    conn.close()

# --- MÓDULO RIOHS ---
elif menu == "📘 Entrega RIOHS":
    st.title("Entrega Reglamento Interno")
    conn = get_conn()
    df = pd.read_sql("SELECT rut, nombre FROM personal", conn)
    sel = st.selectbox("Trabajador:", df['rut'] + " | " + df['nombre'])
    tipo = st.selectbox("Formato", ["Digital", "Físico"])
    
    canvas = st_canvas(stroke_width=2, height=150, key="riohs_sig")
    if st.button("Registrar Entrega"):
        if canvas.image_data is not None:
            img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
            rut = sel.split(" | ")[0]
            conn.execute("INSERT INTO registro_riohs (fecha_entrega, rut_trabajador, nombre_trabajador, tipo_entrega, firma_b64) VALUES (?,?,?,?,?)",
                        (date.today(), rut, sel.split(" | ")[1], tipo, img_str))
            conn.commit(); st.success("Registrado")
    conn.close()

# --- MÓDULO CAPACITACIONES ---
elif menu == "🎓 Capacitaciones":
    st.title("Registro Capacitaciones")
    conn = get_conn()
    df = pd.read_sql("SELECT rut, nombre FROM personal", conn)
    
    with st.form("cap"):
        tema = st.text_input("Tema")
        asistentes = st.multiselect("Asistentes", df['rut'] + " | " + df['nombre'])
        if st.form_submit_button("Guardar"):
            c = conn.cursor()
            c.execute("INSERT INTO capacitaciones (fecha, tema, estado) VALUES (?,?,?)", (date.today(), tema, "EJECUTADA"))
            id_cap = c.lastrowid
            for a in asistentes:
                rut = a.split(" | ")[0]
                c.execute("INSERT INTO asistencia_capacitacion (capacitacion_id, trabajador_rut, estado) VALUES (?,?,?)", (id_cap, rut, "ASISTIÓ"))
            conn.commit(); st.success("Capacitación Guardada")
    conn.close()
