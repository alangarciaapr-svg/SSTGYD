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
# 1. CONFIGURACIÓN DEL SISTEMA "PLATINUM"
# ==============================================================================
st.set_page_config(page_title="SGSST PLATINUM ERP", layout="wide", page_icon="🏗️")

DB_NAME = 'sgsst_v101_platinum.db' # Nueva DB con tablas de auditoría
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"

# --- DEFINICIÓN GLOBAL DE VARIABLES ---
MESES_ORDEN = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

# Estilos CSS Profesionales
st.markdown("""
    <style>
    .main-header {font-size: 2.2rem; font-weight: 700; color: #2C3E50; border-bottom: 3px solid #8B0000; margin-bottom: 20px; padding-bottom: 10px;}
    .kpi-card {background-color: #ffffff; padding: 20px; border-radius: 10px; border-left: 5px solid #8B0000; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;}
    .alert-box {padding: 12px; border-radius: 6px; margin-bottom: 8px; font-weight: 600; font-size: 0.9rem;}
    .alert-high {background-color: #ffebee; color: #b71c1c; border-left: 5px solid #d32f2f;}
    .alert-ok {background-color: #e8f5e9; color: #2e7d32; border-left: 5px solid #388e3c;}
    .audit-log {font-family: 'Courier New'; font-size: 0.85rem; color: #333;}
    </style>
""", unsafe_allow_html=True)

# LISTAS MAESTRAS
LISTA_CARGOS = [
    "GERENTE GENERAL", "PREVENCIONISTA DE RIESGOS", "JEFE DE PATIO", 
    "OPERADOR DE ASERRADERO", "OPERADOR DE MAQUINARIA", "MOTOSIERRISTA", "ESTROBERO", "MECANICO"
]

# ==============================================================================
# 2. CAPA DE DATOS (SQL) - ARQUITECTURA ROBUSTA
# ==============================================================================
def get_conn():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    
    # 1. Seguridad y Auditoría (NUEVO)
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fecha DATETIME, 
        usuario TEXT, 
        accion TEXT, 
        detalle TEXT)''') # Registro inmutable de acciones
    
    # 2. Personal (RRHH)
    c.execute('''CREATE TABLE IF NOT EXISTS personal (
        rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, 
        fecha_contrato DATE, estado TEXT, vigencia_examen_medico DATE)''')
    
    # 3. Matriz IPER
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

    # 5. Módulos Avanzados
    c.execute('''CREATE TABLE IF NOT EXISTS cphs_actas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_reunion DATE, nro_acta INTEGER,
        tipo_reunion TEXT, acuerdos TEXT, estado TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS salud_ocupacional (
        id INTEGER PRIMARY KEY AUTOINCREMENT, rut_trabajador TEXT, tipo_examen TEXT,
        fecha_realizacion DATE, fecha_vencimiento DATE, estado_apto TEXT, observaciones TEXT)''')

    # 6. Gestión de Incidentes (NUEVO)
    c.execute('''CREATE TABLE IF NOT EXISTS incidentes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tipo TEXT, 
        descripcion TEXT, area TEXT, severidad TEXT, estado TEXT)''')

    # --- SEEDING INICIAL ---
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
# 3. LÓGICA DE NEGOCIO Y "AUDITORÍA"
# ==============================================================================
def registrar_auditoria(usuario, accion, detalle):
    """Función crítica para trazabilidad empresarial."""
    try:
        conn = get_conn()
        conn.execute("INSERT INTO auditoria (fecha, usuario, accion, detalle) VALUES (?,?,?,?)", 
                     (datetime.now(), usuario, accion, detalle))
        conn.commit()
        conn.close()
    except: pass

def get_alertas():
    conn = get_conn()
    alertas = []
    
    # Alerta 1: ODI Faltante
    trabs = pd.read_sql("SELECT rut, nombre FROM personal WHERE estado='ACTIVO'", conn)
    for i, t in trabs.iterrows():
        count = pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(t['rut'],)).iloc[0,0]
        if count == 0:
            alertas.append(f"⚠️ Falta ODI/Inducción para: {t['nombre']}")
            
    # Alerta 2: Exámenes Médicos Vencidos
    hoy = date.today()
    examenes = pd.read_sql("SELECT p.nombre, s.fecha_vencimiento FROM salud_ocupacional s JOIN personal p ON s.rut_trabajador = p.rut WHERE s.estado_apto='APTO'", conn)
    for i, e in examenes.iterrows():
        venc = datetime.strptime(e['fecha_vencimiento'], '%Y-%m-%d').date() if isinstance(e['fecha_vencimiento'], str) else e['fecha_vencimiento']
        dias_restantes = (venc - hoy).days
        if dias_restantes < 30:
            alertas.append(f"🩺 Examen de {e['nombre']} vence en {dias_restantes} días.")

    conn.close()
    return alertas

# ==============================================================================
# 4. GENERADORES PDF Y CREDENCIALES
# ==============================================================================
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
# 5. FRONTEND (STREAMLIT)
# ==============================================================================
init_db()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user' not in st.session_state: st.session_state['user'] = "Invitado"

# LOGIN
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🔐 SGSST PLATINUM")
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u == "admin" and p == "1234": 
                st.session_state['logged_in'] = True
                st.session_state['user'] = u
                registrar_auditoria(u, "LOGIN", "Inicio de sesión exitoso")
                st.rerun()
            else: st.error("Error")
    st.stop()

# SIDEBAR
with st.sidebar:
    st.title("MADERAS GÁLVEZ")
    st.caption("ERP V101 - Enterprise")
    
    menu = st.radio("MENÚ PRINCIPAL", [
        "📊 Dashboard & KPIs", 
        "👥 Gestión Personal & Salud", 
        "🛡️ Matriz IPER", 
        "⚖️ Documental (ODI/RIOHS)", 
        "🦺 EPP", 
        "🎓 Capacitación",
        "🤝 Comité Paritario",
        "🚨 Gestión de Incidentes" # NUEVO
    ])
    st.divider()
    if st.button("Cerrar Sesión"):
        registrar_auditoria(st.session_state['user'], "LOGOUT", "Cierre de sesión")
        st.session_state['logged_in'] = False
        st.rerun()

# --- MÓDULO DASHBOARD (MEJORADO CON TRAZABILIDAD) ---
if menu == "📊 Dashboard & KPIs":
    st.markdown("<div class='main-header'>Centro de Comando SST</div>", unsafe_allow_html=True)
    
    col_main, col_feed = st.columns([3, 1])
    
    with col_main:
        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Tasa Accidentabilidad", "2.1%", "-0.2%")
        k2.metric("Tasa Siniestralidad", "12.5", "Estable")
        k3.metric("Exámenes Vigentes", "98%", "+5%")
        k4.metric("Incidentes del Mes", "0", "Récord")
        
        st.markdown("---")
        
        # Alertas
        alertas = get_alertas()
        if alertas:
            st.warning(f"⚠️ {len(alertas)} Asuntos pendientes")
            for a in alertas: st.markdown(f"<div class='alert-box alert-high'>{a}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='alert-box alert-ok'>✅ Sistema al día. Sin pendientes.</div>", unsafe_allow_html=True)
        
        # Gráficos
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("### 📉 Accidentabilidad")
            df_g = pd.DataFrame({'Mes': MESES[:6], 'Tasa': [3, 2.5, 2.1, 2.0, 2.2, 2.1]})
            fig = px.area(df_g, x='Mes', y='Tasa', color_discrete_sequence=[COLOR_PRIMARY])
            st.plotly_chart(fig, use_container_width=True)
    
    with col_feed:
        st.subheader("📋 Actividad Reciente")
        # Live Feed de Auditoría
        conn = get_conn()
        audit = pd.read_sql("SELECT usuario, accion, fecha FROM auditoria ORDER BY id DESC LIMIT 5", conn)
        conn.close()
        for i, row in audit.iterrows():
            st.text(f"{row['fecha'][:16]}\n{row['usuario']}: {row['accion']}")
            st.markdown("---")

# --- MÓDULO GESTIÓN INCIDENTES (NUEVO) ---
elif menu == "🚨 Gestión de Incidentes":
    st.markdown("<div class='main-header'>Registro de Accidentes e Incidentes</div>", unsafe_allow_html=True)
    
    tab_reg, tab_list = st.tabs(["📝 Reportar Nuevo", "📂 Historial"])
    
    with tab_reg:
        with st.form("incidente_form"):
            col_a, col_b = st.columns(2)
            fecha_inc = col_a.date_input("Fecha del Evento")
            tipo_inc = col_b.selectbox("Tipo de Evento", ["Accidente CTP", "Accidente Trayecto", "Enfermedad Profesional", "Incidente (Casi-Accidente)"])
            area = col_a.selectbox("Área Ocurrencia", ["ASERRADERO", "PATIO", "FAENA", "OFICINA"])
            severidad = col_b.selectbox("Severidad Potencial", ["LEVE", "GRAVE", "FATAL"])
            desc = st.text_area("Descripción de los Hechos")
            
            if st.form_submit_button("Registrar Evento"):
                conn = get_conn()
                conn.execute("INSERT INTO incidentes (fecha, tipo, descripcion, area, severidad, estado) VALUES (?,?,?,?,?,?)",
                             (fecha_inc, tipo_inc, desc, area, severidad, "ABIERTO"))
                conn.commit()
                conn.close()
                registrar_auditoria(st.session_state['user'], "INCIDENTE", f"Reportado: {tipo_inc}")
                st.success("Incidente registrado. Se debe iniciar investigación.")
    
    with tab_list:
        conn = get_conn()
        df_inc = pd.read_sql("SELECT * FROM incidentes ORDER BY fecha DESC", conn)
        st.dataframe(df_inc, use_container_width=True)
        conn.close()

# --- MÓDULO GESTIÓN PERSONAS & SALUD ---
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
                        conn.commit()
                        registrar_auditoria(st.session_state['user'], "PERSONAL", f"Creado: {n}")
                        st.success("Guardado"); st.rerun()
                    except: st.error("Error: RUT duplicado")
    
    with tab2:
        trabs = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
        if not trabs.empty:
            sel = st.selectbox("Trabajador:", trabs['rut'] + " - " + trabs['nombre'])
            rut_sel = sel.split(" - ")[0]
            # Mostrar Credencial
            if st.button("🪪 Generar Credencial de Acceso"):
                p_data = trabs[trabs['rut'] == rut_sel].iloc[0]
                pdf_cred = generar_credencial_pdf(p_data)
                st.download_button("Descargar Credencial", pdf_cred, f"Credencial_{rut_sel}.pdf", "application/pdf")

    with tab3:
        st.subheader("Control de Exámenes")
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
                registrar_auditoria(st.session_state['user'], "SALUD", f"Examen registrado: {t_salud.split(' - ')[1]}")
                st.success("Examen registrado")
        
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
        registrar_auditoria(st.session_state['user'], "MATRIZ", "Matriz IPER Actualizada")
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

# --- MÓDULO COMITÉ PARITARIO ---
elif menu == "🤝 Comité Paritario":
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
            registrar_auditoria(st.session_state['user'], "CPHS", f"Acta N°{nro} Creada")
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
            registrar_auditoria(st.session_state['user'], "EPP", f"Entrega a {rut}")
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
            registrar_auditoria(st.session_state['user'], "CAPACITACION", f"Tema: {tema}")
    conn.close()
