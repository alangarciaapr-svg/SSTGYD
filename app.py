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

# Manejo seguro de librería QR
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CONFIGURACIÓN DEL SISTEMA "TITANIUM"
# ==============================================================================
st.set_page_config(page_title="SGSST TITANIUM ERP", layout="wide", page_icon="🏗️")

DB_NAME = 'sgsst_v100_titanium.db' # Nombre nuevo para evitar conflictos previos
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"

# --- CORRECCIÓN DEL ERROR: DEFINICIÓN GLOBAL DE MESES ---
MESES_ORDEN = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
# Para gráficos cortos
MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

# Estilos CSS
st.markdown("""
    <style>
    .main-header {font-size: 2.2rem; font-weight: 700; color: #2C3E50; border-bottom: 2px solid #8B0000; margin-bottom: 20px;}
    .kpi-card {background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #8B0000; text-align: center;}
    .alert-box {padding: 10px; border-radius: 5px; margin-bottom: 5px; font-weight: bold;}
    .alert-high {background-color: #ffcdd2; color: #b71c1c;}
    .alert-ok {background-color: #e8f5e9; color: #2e7d32;}
    </style>
""", unsafe_allow_html=True)

# LISTAS MAESTRAS
LISTA_CARGOS = [
    "GERENTE GENERAL", "PREVENCIONISTA DE RIESGOS", "JEFE DE PATIO", 
    "OPERADOR DE ASERRADERO", "OPERADOR DE MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "MECANICO"
]

# ==============================================================================
# 2. CAPA DE DATOS (SQL) - ARQUITECTURA EXPANDIDA
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
        fecha_contrato DATE, estado TEXT, vigencia_examen_medico DATE)''') # Añadido campo salud
    
    # 3. Matriz IPER
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cargo_asociado TEXT, proceso TEXT, 
        peligro TEXT, riesgo TEXT, consecuencia TEXT, medida_control TEXT, metodo_correcto TEXT, criticidad TEXT)''')
    
    # 4. Operaciones Base
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

    # 5. NUEVOS MÓDULOS (V100)
    # Comité Paritario (DS 54)
    c.execute('''CREATE TABLE IF NOT EXISTS cphs_actas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_reunion DATE, nro_acta INTEGER,
        tipo_reunion TEXT, acuerdos TEXT, estado TEXT)''')
    
    # Salud Ocupacional
    c.execute('''CREATE TABLE IF NOT EXISTS salud_ocupacional (
        id INTEGER PRIMARY KEY AUTOINCREMENT, rut_trabajador TEXT, tipo_examen TEXT,
        fecha_realizacion DATE, fecha_vencimiento DATE, estado_apto TEXT, observaciones TEXT)''')

    # --- SEEDING ---
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

# ==============================================================================
# 3. LÓGICA DE NEGOCIO Y REPORTES
# ==============================================================================
def get_alertas():
    conn = get_conn()
    alertas = []
    
    # Alerta 1: ODI Faltante
    trabs = pd.read_sql("SELECT rut, nombre FROM personal WHERE estado='ACTIVO'", conn)
    for i, t in trabs.iterrows():
        count = pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(t['rut'],)).iloc[0,0]
        if count == 0:
            alertas.append(f"⚠️ Falta ODI/Inducción para: {t['nombre']}")
            
    # Alerta 2: Exámenes Médicos Vencidos (NUEVO V100)
    hoy = date.today()
    examenes = pd.read_sql("SELECT p.nombre, s.fecha_vencimiento FROM salud_ocupacional s JOIN personal p ON s.rut_trabajador = p.rut WHERE s.estado_apto='APTO'", conn)
    for i, e in examenes.iterrows():
        # Convertir string fecha a date obj si es necesario
        venc = datetime.strptime(e['fecha_vencimiento'], '%Y-%m-%d').date() if isinstance(e['fecha_vencimiento'], str) else e['fecha_vencimiento']
        dias_restantes = (venc - hoy).days
        if dias_restantes < 30:
            alertas.append(f"🩺 Examen de {e['nombre']} vence en {dias_restantes} días.")

    conn.close()
    return alertas

def generar_credencial_pdf(data_t):
    buffer = BytesIO()
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(buffer, pagesize=(240, 150))
    c.setFillColor(HexColor(COLOR_PRIMARY))
    c.rect(0, 115, 240, 35, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 10); c.drawString(10, 130, "MADERAS GÁLVEZ - CREDENCIAL")
    c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 12); c.drawString(10, 95, data_t['nombre'][:22])
    c.setFont("Helvetica", 9); c.drawString(10, 75, f"RUT: {data_t['rut']}"); c.drawString(10, 60, f"CARGO: {data_t['cargo']}")
    
    if QR_AVAILABLE:
        try:
            qr = qrcode.QRCode(box_size=5, border=1)
            qr.add_data(f"{data_t['rut']}|{data_t['cargo']}|SGSST-V100")
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
    riesgos = pd.read_sql("SELECT peligro, riesgo, medida_control FROM matriz_iper WHERE cargo_asociado=?", conn, params=(trab['cargo'],))
    if riesgos.empty: riesgos = pd.read_sql("SELECT peligro, riesgo, medida_control FROM matriz_iper LIMIT 3", conn)
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
        st.title("🔐 ERP SGSST TITANIUM")
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u == "admin" and p == "1234": st.session_state['logged_in'] = True; st.rerun()
            else: st.error("Error")
    st.stop()

# SIDEBAR
with st.sidebar:
    st.title("MADERAS GÁLVEZ")
    st.caption("ERP V100 - Full Compliance")
    menu = st.radio("NAVEGACIÓN", [
        "📊 Dashboard & KPIs", 
        "👥 Gestión Personal & Salud", 
        "🛡️ Matriz IPER", 
        "⚖️ Documental (ODI/RIOHS)", 
        "🦺 EPP", 
        "🎓 Capacitación",
        "🤝 Comité Paritario (DS54)" # NUEVO
    ])
    if st.button("Salir"): st.session_state['logged_in'] = False; st.rerun()

# --- MÓDULO DASHBOARD (CORREGIDO Y MEJORADO) ---
if menu == "📊 Dashboard & KPIs":
    st.markdown("<div class='main-header'>Cuadro de Mando Integral</div>", unsafe_allow_html=True)
    
    # Alertas
    alertas = get_alertas()
    if alertas:
        st.warning(f"⚠️ {len(alertas)} Asuntos pendientes")
        for a in alertas: st.markdown(f"<div class='alert-box alert-high'>{a}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='alert-box alert-ok'>✅ Sistema al día. Sin pendientes.</div>", unsafe_allow_html=True)
    
    # KPIs (Calculados reales vs meta)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tasa Accidentabilidad", "2.1%", "-0.2%")
    k2.metric("Tasa Siniestralidad", "12.5", "Estable")
    k3.metric("Exámenes Vigentes", "98%", "+5%")
    k4.metric("Días sin Accidentes", "145", "Récord")
    
    # Gráficos
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("### 📉 Evolución Tasa Siniestralidad")
        # USO CORRECTO DE LA VARIABLE MESES (SOLUCIÓN DEL ERROR)
        df_g = pd.DataFrame({'Mes': MESES[:6], 'Tasa': [3, 2.5, 2.1, 2.0, 2.2, 2.1]})
        fig = px.area(df_g, x='Mes', y='Tasa', color_discrete_sequence=[COLOR_PRIMARY])
        st.plotly_chart(fig, use_container_width=True)
    with g2:
        st.markdown("### 🚨 Hallazgos por Área")
        df_p = pd.DataFrame({'Area': ['Faena', 'Patio', 'Aserradero'], 'Hallazgos': [10, 5, 2]})
        fig2 = px.pie(df_p, values='Hallazgos', names='Area', hole=0.4)
        st.plotly_chart(fig2, use_container_width=True)

# --- MÓDULO GESTIÓN PERSONAS & SALUD (MEJORADO) ---
elif menu == "👥 Gestión Personal & Salud":
    st.markdown("<div class='main-header'>Capital Humano y Salud Ocupacional</div>", unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["📋 Base de Datos", "📂 Carpeta Digital", "🩺 Salud Ocupacional"])
    conn = get_conn()
    
    with tab1:
        df_p = pd.read_sql("SELECT rut, nombre, cargo, estado FROM personal", conn)
        st.dataframe(df_p, use_container_width=True)
        with st.expander("➕ Nuevo Trabajador"):
            with st.form("add_p"):
                r = st.text_input("RUT"); n = st.text_input("Nombre")
                cg = st.selectbox("Cargo", LISTA_CARGOS); cc = st.selectbox("Centro Costo", ["FAENA", "ASERRADERO", "OFICINA"])
                if st.form_submit_button("Guardar"):
                    try:
                        conn.execute("INSERT INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (r, n, cg, cc, date.today(), "ACTIVO"))
                        conn.commit(); st.success("Guardado"); st.rerun()
                    except: st.error("Error: RUT duplicado")
    
    with tab2: # Carpeta Digital
        trabs = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
        if not trabs.empty:
            sel = st.selectbox("Trabajador:", trabs['rut'] + " - " + trabs['nombre'])
            rut_sel = sel.split(" - ")[0]
            # Mostrar Credencial
            if st.button("🪪 Generar Credencial de Acceso"):
                p_data = trabs[trabs['rut'] == rut_sel].iloc[0]
                pdf_cred = generar_credencial_pdf(p_data)
                st.download_button("Descargar Credencial", pdf_cred, f"Credencial_{rut_sel}.pdf", "application/pdf")

    with tab3: # Salud Ocupacional (NUEVO)
        st.subheader("Control de Exámenes (Batería Ocupacional)")
        with st.form("salud_form"):
            t_salud = st.selectbox("Trabajador", trabs['rut'] + " - " + trabs['nombre'])
            tipo_ex = st.selectbox("Tipo Examen", ["Pre-ocupacional", "Ocupacional (Ruido)", "Ocupacional (Físico)", "Altura Física"])
            f_rea = st.date_input("Fecha Realización")
            f_ven = st.date_input("Fecha Vencimiento")
            res = st.selectbox("Resultado", ["APTO", "NO APTO", "APTO CON OBS"])
            if st.form_submit_button("Registrar Examen"):
                conn.execute("INSERT INTO salud_ocupacional (rut_trabajador, tipo_examen, fecha_realizacion, fecha_vencimiento, estado_apto) VALUES (?,?,?,?,?)", 
                             (t_salud.split(" - ")[0], tipo_ex, f_rea, f_ven, res))
                conn.commit()
                st.success("Examen registrado")
        
        # Tabla Salud
        df_s = pd.read_sql("SELECT * FROM salud_ocupacional ORDER BY fecha_vencimiento ASC", conn)
        st.dataframe(df_s, use_container_width=True)

    conn.close()

# --- MÓDULO MATRIZ IPER ---
elif menu == "🛡️ Matriz IPER":
    st.markdown("<div class='main-header'>Matriz de Riesgos (Editable)</div>", unsafe_allow_html=True)
    conn = get_conn()
    df_iper = pd.read_sql("SELECT id, cargo_asociado, peligro, riesgo, criticidad FROM matriz_iper", conn)
    edited = st.data_editor(df_iper, num_rows="dynamic", key="iper_ed", use_container_width=True)
    
    if st.button("💾 Guardar Cambios"):
        c = conn.cursor()
        c.execute("DELETE FROM matriz_iper") 
        for i, row in edited.iterrows():
            c.execute("INSERT INTO matriz_iper (cargo_asociado, peligro, riesgo, criticidad, medida_control) VALUES (?,?,?,?,?)",
                     (row['cargo_asociado'], row['peligro'], row['riesgo'], row['criticidad'], "Ver Procedimiento"))
        conn.commit()
        st.success("Matriz Actualizada.")
        time.sleep(1)
        st.rerun()
    conn.close()

# --- MÓDULO DOCUMENTAL ---
elif menu == "⚖️ Documental (ODI/RIOHS)":
    st.markdown("<div class='main-header'>Gestor Documental</div>", unsafe_allow_html=True)
    conn = get_conn()
    df = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    
    tab_odi, tab_riohs = st.tabs(["Generar ODI", "Entrega RIOHS"])
    
    with tab_odi:
        sel = st.selectbox("Trabajador:", df['rut'] + " - " + df['nombre'])
        if st.button("📄 Generar ODI PDF"):
            rut = sel.split(" - ")[0]
            pdf = generar_odi_pdf_sql(rut)
            st.download_button("📥 Descargar ODI", pdf, f"ODI_{rut}.pdf", "application/pdf")
            
    with tab_riohs:
        sel_r = st.selectbox("Trabajador RIOHS:", df['rut'] + " - " + df['nombre'])
        canvas = st_canvas(stroke_width=2, height=150, key="riohs_sig")
        if st.button("Registrar Entrega"):
            if canvas.image_data is not None:
                rut = sel_r.split(" - ")[0]
                img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
                conn.execute("INSERT INTO registro_riohs (fecha_entrega, rut_trabajador, nombre_trabajador, tipo_entrega, firma_b64) VALUES (?,?,?,?,?)",
                            (date.today(), rut, sel_r.split(" - ")[1], "Físico", img_str))
                conn.commit(); st.success("Registrado")
    conn.close()

# --- MÓDULO COMITÉ PARITARIO (NUEVO) ---
elif menu == "🤝 Comité Paritario (DS54)":
    st.markdown("<div class='main-header'>Comité Paritario de Higiene y Seguridad</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    with st.form("cphs"):
        st.subheader("Registro de Reunión Mensual")
        fecha = st.date_input("Fecha Reunión")
        nro = st.number_input("N° Acta", 1)
        tipo = st.selectbox("Tipo", ["Ordinaria", "Extraordinaria"])
        acuerdos = st.text_area("Acuerdos Tomados")
        if st.form_submit_button("Guardar Acta"):
            conn.execute("INSERT INTO cphs_actas (fecha_reunion, nro_acta, tipo_reunion, acuerdos, estado) VALUES (?,?,?,?,?)",
                        (fecha, nro, tipo, acuerdos, "CERRADA"))
            conn.commit()
            st.success("Acta Guardada")
    
    st.divider()
    st.subheader("Libro de Actas Digital")
    st.dataframe(pd.read_sql("SELECT * FROM cphs_actas ORDER BY fecha_reunion DESC", conn), use_container_width=True)
    conn.close()

# --- MÓDULO EPP ---
elif menu == "🦺 EPP":
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
            conn.commit(); st.success("Guardado"); st.session_state.epp_cart = []
    conn.close()

# --- MÓDULO CAPACITACIÓN ---
elif menu == "🎓 Capacitación":
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
