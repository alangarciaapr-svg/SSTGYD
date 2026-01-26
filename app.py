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
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from streamlit_drawable_canvas import st_canvas

# Intento de importar librería QR (Manejo de errores si no está instalada)
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# Configuración Matplotlib
matplotlib.use('Agg')

# ==============================================================================
# 1. CONFIGURACIÓN DEL SISTEMA ENTERPRISE
# ==============================================================================
st.set_page_config(
    page_title="SGSST PRO | Enterprise ERP",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constantes de Arquitectura
DB_NAME = 'sgsst_v96_enterprise.db' # Nombre nuevo para inicio limpio
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50" 
MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

# Estilos CSS Profesionales
st.markdown("""
    <style>
    .main-header {font-size: 2.2rem; font-weight: 700; color: #2C3E50; margin-bottom: 10px; border-bottom: 2px solid #8B0000;}
    .card-worker {background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 6px solid #8B0000; box-shadow: 0 2px 4px rgba(0,0,0,0.1);}
    .alert-box {padding: 15px; border-radius: 8px; margin-bottom: 10px; font-weight: 600; font-size: 0.9rem;}
    .alert-high {background-color: #ffebee; color: #c62828; border: 1px solid #ef9a9a;}
    .alert-med {background-color: #fff3e0; color: #ef6c00; border: 1px solid #ffcc80;}
    .alert-ok {background-color: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7;}
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CAPA DE DATOS (DAL)
# ==============================================================================
def get_db_connection():
    return sqlite3.connect(DB_NAME)

def init_system():
    """Inicializa la estructura de base de datos relacional completa."""
    conn = get_db_connection()
    c = conn.cursor()

    # 1. Usuarios y Config
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT, nombre_completo TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS empresa_config (id INTEGER PRIMARY KEY, razon_social TEXT, rut_empresa TEXT, rubro TEXT)''')
    
    # 2. RRHH (Maestro de Personal)
    c.execute('''CREATE TABLE IF NOT EXISTS personal (
        rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, 
        fecha_contrato DATE, estado TEXT, email TEXT, foto_perfil_b64 TEXT
    )''')

    # 3. Matriz IPER (Cerebro de Riesgos)
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cargo_asociado TEXT, proceso TEXT, 
        peligro TEXT, riesgo TEXT, consecuencia TEXT, medida_control TEXT, metodo_correcto TEXT, criticidad TEXT
    )''')

    # 4. Operaciones (Capacitaciones)
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, 
        tipo_actividad TEXT, responsable_rut TEXT, estado TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia_capacitacion (
        id INTEGER PRIMARY KEY AUTOINCREMENT, capacitacion_id INTEGER, 
        trabajador_rut TEXT, estado TEXT, fecha_firma DATETIME,
        FOREIGN KEY(capacitacion_id) REFERENCES capacitaciones(id)
    )''')

    # 5. Operaciones (EPP)
    c.execute('''CREATE TABLE IF NOT EXISTS entrega_epp (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_entrega DATE, 
        trabajador_rut TEXT, producto TEXT, cantidad INTEGER, tipo_entrega TEXT
    )''')

    # --- SEEDING (DATOS INICIALES) ---
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        # Admin Default
        c.execute("INSERT INTO usuarios VALUES (?,?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR", "Super Admin"))
        
        # Matriz Default (Ejemplo)
        datos_matriz = [
            ("OPERADOR DE MAQUINARIA", "Cosecha", "Pendiente Abrupta", "Volcamiento", "Muerte", "Cabina ROPS/FOPS", "No operar >30%", "CRITICO"),
            ("MOTOSIERRISTA", "Tala", "Caída árbol", "Golpe", "Muerte", "Planificación caída", "Distancia seguridad", "CRITICO"),
            ("JEFE DE PATIO", "Logística", "Tránsito Maquinaria", "Atropello", "Muerte", "Chaleco Reflectante", "Contacto Visual", "ALTO")
        ]
        c.executemany("INSERT INTO matriz_iper (cargo_asociado, proceso, peligro, riesgo, consecuencia, medida_control, metodo_correcto, criticidad) VALUES (?,?,?,?,?,?,?,?)", datos_matriz)
        
        # Personal Default
        c.execute("INSERT INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", ("12.345.678-9", "JUAN PEREZ (EJEMPLO)", "OPERADOR DE MAQUINARIA", "FAENA", date.today(), "ACTIVO"))

    conn.commit()
    conn.close()

# ==============================================================================
# 3. LÓGICA DE NEGOCIO & INTELIGENCIA (BLL)
# ==============================================================================
def get_alertas_sistema():
    """Genera alertas automáticas para el Dashboard."""
    alertas = []
    conn = get_db_connection()
    
    # Alerta 1: Trabajadores activos sin capacitaciones recientes
    trabajadores = pd.read_sql("SELECT rut, nombre FROM personal WHERE estado='ACTIVO'", conn)
    for i, t in trabajadores.iterrows():
        asist = pd.read_sql("SELECT count(*) FROM asistencia_capacitacion WHERE trabajador_rut=?", conn, params=(t['rut'],)).iloc[0,0]
        if asist == 0:
            alertas.append({"nivel": "ALTO", "msg": f"🚫 {t['nombre']} no tiene capacitaciones registradas (Falta ODI)."})
    
    # Alerta 2: Matriz vacía
    riesgos = pd.read_sql("SELECT count(*) FROM matriz_iper", conn).iloc[0,0]
    if riesgos < 5:
        alertas.append({"nivel": "MEDIO", "msg": "⚠️ La Matriz IPER tiene pocos riesgos cargados. Revise la configuración."})

    conn.close()
    return alertas

def get_resumen_trabajador(rut):
    """Data Aggregation para la Carpeta Digital."""
    conn = get_db_connection()
    data = {}
    # Perfil
    data['perfil'] = pd.read_sql("SELECT * FROM personal WHERE rut=?", conn, params=(rut,)).iloc[0]
    # EPP Histórico
    data['epp'] = pd.read_sql("SELECT fecha_entrega, producto, cantidad, tipo_entrega FROM entrega_epp WHERE trabajador_rut=? ORDER BY fecha_entrega DESC", conn, params=(rut,))
    # Capacitaciones
    data['caps'] = pd.read_sql("""
        SELECT c.fecha, c.tema, c.tipo_actividad 
        FROM asistencia_capacitacion a 
        JOIN capacitaciones c ON a.capacitacion_id = c.id 
        WHERE a.trabajador_rut=? ORDER BY c.fecha DESC
    """, conn, params=(rut,))
    conn.close()
    return data

def login_user(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT rol, nombre_completo FROM usuarios WHERE username=? AND password=?", 
              (username, hashlib.sha256(password.encode()).hexdigest()))
    data = c.fetchone()
    conn.close()
    return data

# ==============================================================================
# 4. MOTOR DE REPORTES (PDF & QR)
# ==============================================================================
def generar_credencial_pdf(data_trabajador):
    """Genera PDF tamaño tarjeta de crédito con QR."""
    buffer = BytesIO()
    c_width, c_height = 240, 150 # Aprox tarjeta visita landscape
    
    # 1. Generar QR
    qr_img_path = None
    if QR_AVAILABLE:
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        # Data del QR: URL simulada o JSON con datos clave
        qr_data = f"SGSST|{data_trabajador['rut']}|{data_trabajador['cargo']}|{data_trabajador['estado']}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        
        qr_bytes = BytesIO()
        img_qr.save(qr_bytes, format='PNG')
        qr_bytes.seek(0)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(qr_bytes.getvalue())
            qr_img_path = tmp.name

    # 2. Dibujar PDF
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(buffer, pagesize=(c_width, c_height))
    
    # Fondo Header
    c.setFillColor(HexColor(COLOR_PRIMARY))
    c.rect(0, c_height-35, c_width, 35, fill=1, stroke=0)
    
    # Textos Header
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(10, c_height-15, "MADERAS GÁLVEZ Y DI GÉNOVA")
    c.setFont("Helvetica", 6)
    c.drawString(10, c_height-25, "CREDENCIAL DE ACCESO Y COMPETENCIAS - SGSST")
    
    # Datos Cuerpo
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(10, 90, data_trabajador['nombre'][:22]) # Truncar nombre largo
    
    c.setFont("Helvetica", 9)
    c.drawString(10, 70, f"RUT: {data_trabajador['rut']}")
    c.drawString(10, 55, f"CARGO: {data_trabajador['cargo']}")
    c.drawString(10, 40, f"ÁREA: {data_trabajador['centro_costo']}")
    
    # Estado Visual
    if data_trabajador['estado'] == 'ACTIVO':
        c.setFillColor(HexColor("#2E7D32")) # Verde
    else:
        c.setFillColor(HexColor("#C62828")) # Rojo
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10, 20, f"• {data_trabajador['estado']}")

    # Insertar QR
    if qr_img_path:
        c.drawImage(qr_img_path, 160, 20, width=70, height=70)
        os.unlink(qr_img_path)
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def generar_odi_pdf(rut_trabajador):
    """Genera el ODI basándose en la Matriz SQL."""
    conn = get_db_connection()
    trab = pd.read_sql("SELECT * FROM personal WHERE rut=?", conn, params=(rut_trabajador,)).iloc[0]
    # Buscar riesgos en SQL
    riesgos = pd.read_sql("SELECT peligro, riesgo, medida_control FROM matriz_iper WHERE cargo_asociado=?", conn, params=(trab['cargo'],))
    # Si no hay, buscar genericos
    if riesgos.empty:
        riesgos = pd.read_sql("SELECT peligro, riesgo, medida_control FROM matriz_iper LIMIT 3", conn) # Fallback
    conn.close()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Título
    elements.append(Paragraph(f"OBLIGACIÓN DE INFORMAR (ODI) - {trab['nombre']}", styles['Heading1']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Cargo: {trab['cargo']} | RUT: {trab['rut']}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # Tabla Riesgos
    data = [["PELIGRO", "RIESGO", "MEDIDA DE CONTROL"]]
    for i, r in riesgos.iterrows():
        data.append([r['peligro'], r['riesgo'], r['medida_control']])
    
    t = Table(data, colWidths=[120, 120, 250])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 8)
    ]))
    elements.append(t)
    elements.append(Spacer(1, 40))
    
    # Firma
    elements.append(Paragraph("___________________________", styles['Normal']))
    elements.append(Paragraph("FIRMA TRABAJADOR", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==============================================================================
# 5. FRONTEND (STREAMLIT)
# ==============================================================================
init_system()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# --- LOGIN ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.title("🔐 SGSST ENTERPRISE")
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Iniciar Sesión", use_container_width=True):
            user_data = login_user(u, p)
            if user_data:
                st.session_state['logged_in'] = True
                st.session_state['user_name'] = user_data[1]
                st.rerun()
            else:
                st.error("Credenciales Incorrectas (Prueba: admin / 1234)")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.title("MADERAS GÁLVEZ")
    st.caption("Enterprise V96")
    menu = st.radio("MENÚ PRINCIPAL", ["📊 Dashboard & Alertas", "👥 Gestión de Personas", "🛡️ Matriz IPER", "⚖️ Documentación Legal", "⚙️ Configuración"])
    st.divider()
    if st.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

# --- MÓDULO 1: DASHBOARD INTELIGENTE ---
if menu == "📊 Dashboard & Alertas":
    st.markdown("<div class='main-header'>Centro de Comando SST</div>", unsafe_allow_html=True)
    
    # Panel de Alertas
    st.subheader("🔔 Centro de Alertas Tempranas")
    alertas = get_alertas_sistema()
    if alertas:
        for a in alertas:
            color_cls = "alert-high" if a['nivel'] == "ALTO" else "alert-med"
            st.markdown(f"<div class='alert-box {color_cls}'>{a['msg']}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='alert-box alert-ok'>✅ Sistema Operativo Óptimo. Sin pendientes.</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # KPIs Visuales
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tasa Accidentabilidad", "2.1%", "-0.5%")
    c2.metric("Cumplimiento Prog.", "92%", "+5%")
    c3.metric("Trabajadores Activos", "14", "Estable")
    c4.metric("Días sin Accidentes", "145", "Récord")

    # Gráficos
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("### 📉 Evolución Tasa Siniestralidad")
        df_chart = pd.DataFrame({'Mes': ['Ene','Feb','Mar','Abr','May','Jun'], 'Tasa': [12, 10, 8, 8, 5, 2]})
        fig = px.area(df_chart, x='Mes', y='Tasa', color_discrete_sequence=[COLOR_PRIMARY])
        st.plotly_chart(fig, use_container_width=True)
    
    with g2:
        st.markdown("### 🚨 Hallazgos por Área")
        df_pie = pd.DataFrame({'Area': ['Aserradero', 'Patio', 'Faena'], 'Hallazgos': [5, 2, 8]})
        fig2 = px.pie(df_pie, values='Hallazgos', names='Area', hole=0.4)
        st.plotly_chart(fig2, use_container_width=True)

# --- MÓDULO 2: GESTIÓN DE PERSONAS (CON CARPETA DIGITAL) ---
elif menu == "👥 Gestión de Personas":
    st.markdown("<div class='main-header'>Capital Humano</div>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📋 Base de Datos", "📂 Carpeta Digital & Credencial"])
    conn = get_db_connection()
    
    with tab1:
        df_p = pd.read_sql("SELECT rut, nombre, cargo, centro_costo, estado FROM personal", conn)
        st.dataframe(df_p, use_container_width=True)
        
        with st.expander("➕ Ingresar Nuevo Trabajador"):
            with st.form("new_w"):
                c1, c2 = st.columns(2)
                r = c1.text_input("RUT"); n = c2.text_input("Nombre")
                cg = c1.selectbox("Cargo", ["OPERADOR DE MAQUINARIA", "JEFE DE PATIO", "OTROS"])
                cc = c2.selectbox("Centro Costo", ["FAENA", "ASERRADERO", "OFICINA"])
                if st.form_submit_button("Guardar"):
                    try:
                        conn.execute("INSERT INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", (r, n, cg, cc, date.today(), "ACTIVO"))
                        conn.commit()
                        st.success("Guardado"); st.rerun()
                    except: st.error("Error: RUT duplicado")

    with tab2:
        trabajadores = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        if not trabajadores.empty:
            sel = st.selectbox("Buscar Trabajador:", trabajadores['rut'] + " - " + trabajadores['nombre'])
            rut_sel = sel.split(" - ")[0]
            
            # Obtener datos completos
            data = get_resumen_trabajador(rut_sel)
            p = data['perfil']
            
            # TARJETA VISUAL
            st.markdown(f"""
                <div class='card-worker'>
                    <h3>👤 {p['nombre']}</h3>
                    <p><b>RUT:</b> {p['rut']} &nbsp;|&nbsp; <b>Cargo:</b> {p['cargo']} &nbsp;|&nbsp; <b>Estado:</b> {p['estado']}</p>
                    <p><i>Antigüedad: {p['fecha_contrato']}</i></p>
                </div>
            """, unsafe_allow_html=True)
            
            c_izq, c_der = st.columns([1, 2])
            
            with c_izq:
                st.markdown("#### 🪪 Credencial")
                if QR_AVAILABLE:
                    if st.button("Generar Credencial QR"):
                        pdf_cred = generar_credencial_pdf(p)
                        st.download_button("📥 Descargar Credencial", pdf_cred, f"Credencial_{p['rut']}.pdf", "application/pdf")
                else:
                    st.warning("Instale 'qrcode' para generar credenciales.")
                
                st.markdown("#### 📊 Cumplimiento")
                cump = 0
                if len(data['caps']) > 0: cump += 50
                if len(data['epp']) > 0: cump += 50
                st.progress(cump/100)
                st.caption(f"Nivel Documental: {cump}%")

            with c_der:
                st.markdown("#### 📜 Historial")
                subtab1, subtab2 = st.tabs(["🦺 EPP Entregado", "🎓 Capacitaciones"])
                with subtab1:
                    st.dataframe(data['epp'][['fecha_entrega', 'producto', 'cantidad']], use_container_width=True)
                with subtab2:
                    st.dataframe(data['caps'], use_container_width=True)
    conn.close()

# --- MÓDULO 3: MATRIZ IPER (EDITABLE) ---
elif menu == "🛡️ Matriz IPER":
    st.markdown("<div class='main-header'>Matriz de Riesgos (IPER)</div>", unsafe_allow_html=True)
    conn = get_db_connection()
    df_iper = pd.read_sql("SELECT id, cargo_asociado, peligro, riesgo, criticidad FROM matriz_iper", conn)
    
    edited_df = st.data_editor(df_iper, num_rows="dynamic", key="iper_edit", use_container_width=True)
    
    if st.button("💾 Guardar Cambios en Matriz"):
        # Lógica simplificada de actualización: Borrar y reescribir para evitar conflictos complejos en demo
        # En producción real usar UPDATE WHERE id
        c = conn.cursor()
        c.execute("DELETE FROM matriz_iper") # Limpia
        for index, row in edited_df.iterrows():
            c.execute("INSERT INTO matriz_iper (cargo_asociado, peligro, riesgo, criticidad) VALUES (?,?,?,?)",
                     (row['cargo_asociado'], row['peligro'], row['riesgo'], row['criticidad']))
        conn.commit()
        st.success("Matriz Actualizada. Los ODI se generarán con estos nuevos datos.")
        time.sleep(1)
        st.rerun()
    conn.close()

# --- MÓDULO 4: LEGAL (ODI DINÁMICO) ---
elif menu == "⚖️ Documentación Legal":
    st.markdown("<div class='main-header'>Generador Documental</div>", unsafe_allow_html=True)
    
    conn = get_db_connection()
    trabajadores = pd.read_sql("SELECT rut, nombre FROM personal", conn)
    conn.close()
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("Generación de ODI (Obligación de Informar) basada en la Matriz IPER.")
        sel_odi = st.selectbox("Trabajador para ODI:", trabajadores['rut'] + " - " + trabajadores['nombre'])
        
        if st.button("📄 Generar ODI PDF"):
            rut = sel_odi.split(" - ")[0]
            pdf_odi = generar_odi_pdf(rut)
            st.download_button("📥 Descargar ODI", pdf_odi, f"ODI_{rut}.pdf", "application/pdf")

# --- MÓDULO 5: CONFIGURACIÓN ---
elif menu == "⚙️ Configuración":
    st.header("Configuración Global")
    st.write("Parámetros de la empresa para reportes.")
    with st.form("conf"):
        st.text_input("Razón Social", "SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA")
        st.text_input("RUT Empresa", "77.110.060-0")
        st.form_submit_button("Guardar")
