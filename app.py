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
import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
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
st.set_page_config(page_title="SGSST ERP MASTER", layout="wide", page_icon="🏗️")

DB_NAME = 'sgsst_v181_roles_update.db' # Actualización de Cargos
COLOR_PRIMARY = "#8B0000"
COLOR_SECONDARY = "#2C3E50"

# --- DICCIONARIO DE RIESGOS ISP V3 ---
ISP_RISK_CODES = {
    "Seguridad": [
        "Caídas al mismo nivel (A1)", "Caídas a distinto nivel (A2)", "Caídas de altura (A3)", "Caídas al agua (A4)",
        "Atrapamiento (B1)", "Golpeado por/contra (B2)", "Cortes/Punzonantes (B3)", "Choque contra objetos (B4)",
        "Contacto con personas (C1)", "Contacto con animales/insectos (C2)",
        "Contacto con objetos calientes (E1)", "Contacto con objetos fríos (E2)",
        "Contacto eléctrico Baja Tensión (F1/F3)", "Contacto eléctrico Alta Tensión (F2/F4)",
        "Contacto sustancias cáusticas (G1)", "Otras sustancias químicas (G2)",
        "Proyección de partículas (H2)", "Atropellos (I1)", "Choque/Colisión Vehicular (I2)"
    ],
    "Higiene Ocupacional": [
        "Aerosoles Sólidos (Sílice/Polvos) (O1)", "Aerosoles Líquidos (Nieblas) (O2)", "Gases y Vapores (O3)",
        "Ruido (PREXOR) (P1)", "Vibraciones Cuerpo Entero (P2)", "Vibraciones Mano-Brazo (P3)",
        "Radiaciones Ionizantes (P4)", "Radiaciones No Ionizantes (UV/Solar) (P5)", 
        "Calor (P6)", "Frío (P7)", "Altas Presiones (P8)", "Bajas Presiones (Hipobaria) (P9)",
        "Agentes Biológicos (Fluidos) (Q1)", "Agentes Biológicos (Virus/Bacterias) (Q2)"
    ],
    "Músculo Esqueléticos": [
        "Manejo Manual de Cargas (R1)", "Manejo de Pacientes (R2)", "Trabajo Repetitivo (S1)", 
        "Postura de Pie (T1)", "Postura Sentado (T2)", "En Cuclillas (T3)", "Arrodillado (T4)",
        "Tronco Inclinado/Torsión (T5)", "Cabeza/Cuello Flexión (T6)", "Fuera del Alcance (T7)", "Posturas Estáticas (T8)"
    ],
    "Psicosociales (ISTAS21)": [
        "Carga de Trabajo (D1)", "Exigencias Emocionales (D2)", "Desarrollo Profesional (D3)",
        "Reconocimiento y Claridad (D4)", "Conflicto de Rol (D5)", "Calidad de Liderazgo (D6)",
        "Compañerismo (D7)", "Inseguridad (D8)", "Doble Presencia (D9)", 
        "Confianza y Justicia (D10)", "Vulnerabilidad (D11)", "Violencia y Acoso (D12)"
    ],
    "Desastres y Emergencias": [
        "Incendios (J)", "Explosiones (H1)", 
        "Ambientes Deficiencia Oxígeno (K1)", "Gases Tóxicos Emergencia (K2)",
        "Sismos / Terremotos (Natural)", "Inundaciones / Aluviones (Natural)"
    ]
}

# --- FUNCIÓN DE ENVÍO DE CORREO ---
def enviar_correo_riohs(destinatario, nombre_trabajador, pdf_bytes, nombre_archivo):
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    EMAIL_EMISOR = "tu_correo@empresa.com" 
    EMAIL_PASSWORD = "tu_contraseña_aplicacion" 
    
    if EMAIL_EMISOR == "tu_correo@empresa.com":
        time.sleep(1.5) 
        return True, "Simulación: Correo enviado exitosamente (Configurar SMTP para real)"

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_EMISOR
        msg['To'] = destinatario
        msg['Subject'] = f"ENTREGA RIOHS - {nombre_trabajador}"

        body = f"Estimado/a {nombre_trabajador},\n\nAdjunto encontrará su comprobante de recepción del RIOHS.\n\nAtte,\nPrevención."
        msg.attach(MIMEText(body, 'plain'))
        part = MIMEApplication(pdf_bytes, Name=nombre_archivo)
        part['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
        msg.attach(part)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_EMISOR, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True, "Enviado Exitosamente"
    except Exception as e:
        return False, str(e)

# --- FUNCIÓN PROCESAMIENTO FIRMA ---
def process_signature_bg(img_data):
    img = PILImage.fromarray(img_data.astype('uint8'), 'RGBA')
    data = img.getdata()
    new_data = []
    for item in data:
        if item[0] > 220 and item[1] > 220 and item[2] > 220:
            new_data.append((255, 255, 255, 0)) 
        else:
            new_data.append(item) 
    img.putdata(new_data)
    return img

# --- MODO KIOSCO ---
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
                            else: st.error("❌ RUT no inscrito.")
                        else: st.warning("⚠️ Faltan datos.")
            else: st.error("Capacitación no encontrada.")
        except: st.error("Error de conexión con DB Móvil.")
        conn.close()
    st.stop() 

# --- ESTILOS CSS GENERALES ---
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
    
    div[data-testid="stCanvas"] {{
        border: 2px solid #a0a0a0 !important;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        background-color: #ffffff;
        margin-bottom: 10px;
    }}
    </style>
""", unsafe_allow_html=True)

# --- LISTA DE CARGOS ACTUALIZADA ---
LISTA_CARGOS = [
    "GERENTE GENERAL", 
    "GERENTE DE FINANZAS", 
    "PREVENCIONISTA DE RIESGOS", 
    "JEFE DE PATIO", 
    "OPERADOR DE ASERRADERO", 
    "AYUDANTE DE ASERRADERO", 
    "OPERADOR DE MAQUINARIA", 
    "MOTOSIERRISTA", 
    "ESTROBERO", 
    "MECANICO", 
    "MECANICO LIDER", 
    "CALIBRADOR", 
    "PAÑOLERO", 
    "ADMINISTRATIVO"
]

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
    
    # --- MATRIZ IPER V181 ---
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        proceso TEXT, 
        tipo_proceso TEXT, 
        puesto_trabajo TEXT, 
        tarea TEXT, 
        es_rutinaria TEXT, 
        lugar_especifico TEXT,
        familia_riesgo TEXT,
        codigo_riesgo TEXT,
        factor_gema TEXT,
        peligro_factor TEXT, 
        riesgo_asociado TEXT, 
        tipo_riesgo TEXT, 
        probabilidad INTEGER, 
        consecuencia INTEGER, 
        vep INTEGER, 
        nivel_riesgo TEXT, 
        medida_control TEXT, 
        jerarquia_control TEXT,
        requisito_legal TEXT,
        probabilidad_residual INTEGER,
        consecuencia_residual INTEGER,
        vep_residual INTEGER,
        nivel_riesgo_residual TEXT,
        genero_obs TEXT,
        n_hombres INTEGER,
        n_mujeres INTEGER,
        n_disidencias INTEGER
    )''')
    
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
    c.execute('''CREATE TABLE IF NOT EXISTS periodos_ds67 (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre_periodo TEXT, fecha_inicio DATE, fecha_fin DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS detalle_mensual_ds67 (id INTEGER PRIMARY KEY AUTOINCREMENT, periodo_id INTEGER, mes INTEGER, anio INTEGER, masa_imponible INTEGER, dias_perdidos INTEGER, invalideces_muertes INTEGER, observacion TEXT)''')

    # FIX COLUMNAS
    for col in ["n_hombres", "n_mujeres", "n_disidencias", "probabilidad_residual", "consecuencia_residual", "vep_residual"]:
        check_and_add_column(c, "matriz_iper", col, "INTEGER")
    for col in ["lugar_especifico", "familia_riesgo", "codigo_riesgo", "factor_gema", "jerarquia_control", "requisito_legal", "nivel_riesgo_residual"]:
        check_and_add_column(c, "matriz_iper", col, "TEXT")

    check_and_add_column(c, "personal", "contacto_emergencia", "TEXT")
    check_and_add_column(c, "personal", "fono_emergencia", "TEXT")
    check_and_add_column(c, "personal", "obs_medica", "TEXT")
    check_and_add_column(c, "personal", "vigencia_examen_medico", "DATE")
    check_and_add_column(c, "inventario_epp", "precio", "INTEGER")
    check_and_add_column(c, "registro_riohs", "nombre_difusor", "TEXT")
    check_and_add_column(c, "registro_riohs", "firma_difusor_b64", "TEXT")
    check_and_add_column(c, "registro_riohs", "email_copia", "TEXT")
    check_and_add_column(c, "registro_riohs", "estado_envio", "TEXT")
    check_and_add_column(c, "incidentes", "dias_perdidos", "INTEGER")

    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
        epp_list = [
            ("ZAPATOS DE SEGURIDAD", 50, 5, "Bodega", 25000), ("LENTES DE SEGURIDAD", 100, 10, "Bodega", 3000),
            ("GUANTE CABRITILLA", 100, 10, "Bodega", 4500), ("GUANTES MULTIFLEX", 100, 10, "Bodega", 2000),
            ("GORRO LEGIONARIO", 50, 5, "Bodega", 5000), ("ARNES DE SEGURIDAD", 20, 2, "Bodega", 45000),
            ("PROTECTOR SOLAR UV", 50, 5, "Bodega", 8000), ("CASCO DE SEGURIDAD", 50, 5, "Bodega", 12000),
            ("CABO DE VIDA", 20, 2, "Bodega", 15000), ("OVEROL TIPO PILOTO", 50, 5, "Bodega", 18000),
            ("TRAJE DE AGUA", 50, 5, "Bodega", 22000), ("PROTECTOR FACIAL", 30, 3, "Bodega", 9000),
            ("CHALECO REFLECTANTE", 50, 5, "Bodega", 3500), ("PANTALON ANTICORTE", 30, 3, "Bodega", 65000),
            ("MASCARILLAS DESECHABLES", 200, 20, "Bodega", 200), ("ALCOHOL GEL", 50, 5, "Bodega", 1500),
            ("CHAQUETA ANTICORTE", 30, 3, "Bodega", 55000), ("FONO AUDITIVO", 50, 5, "Bodega", 7000),
            ("FONO PARA CASCO", 50, 5, "Bodega", 12000), ("BOTA FORESTAL", 30, 3, "Bodega", 85000)
        ]
        c.executemany("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion, precio) VALUES (?,?,?,?,?)", epp_list)
        
        c.execute("SELECT count(*) FROM matriz_iper")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO matriz_iper (proceso, tipo_proceso, puesto_trabajo, tarea, es_rutinaria, peligro_factor, riesgo_asociado, tipo_riesgo, probabilidad, consecuencia, vep, nivel_riesgo, medida_control, genero_obs, familia_riesgo, lugar_especifico, n_hombres, n_mujeres, n_disidencias, requisito_legal, probabilidad_residual, consecuencia_residual, vep_residual, nivel_riesgo_residual) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 ("Cosecha", "Operativo", "Operador", "Tala", "SI", "Pendiente", "Volcamiento", "Seguridad", 2, 4, 8, "IMPORTANTE", "Cabina ROPS", "Sin Obs", "Seguridad", "Bosque", 5, 0, 0, "DS 594 Art 11", 1, 4, 4, "MODERADO"))
    conn.commit(); conn.close()
    st.session_state['db_setup_complete'] = True

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

# --- LOGICA DS67 AVANZADA ---
def determinar_tramo_cotizacion(tasa):
    if tasa < 33: return 0.0
    elif tasa < 66: return 0.34
    elif tasa < 99: return 0.68
    elif tasa < 132: return 1.02
    elif tasa < 165: return 1.36
    elif tasa < 198: return 1.70
    elif tasa < 231: return 2.04
    elif tasa < 264: return 2.38
    elif tasa < 297: return 2.72
    elif tasa < 330: return 3.06
    else: return 3.40

# ==============================================================================
# 3. MOTOR DOCUMENTAL
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO(); self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=30, leftMargin=30, rightMargin=30); self.elements = []
        self.styles = getSampleStyleSheet(); self.titulo = titulo_doc; self.codigo = codigo_doc; self.logo_url = "https://www.maderasgyd.cl/wp-content/uploads/2024/02/logo-maderas-gd-1.png"

    def _header(self):
        try:
            logo = RLImage(self.logo_url, width=120, height=50)
        except:
            logo = Paragraph("<b>MADERAS G&D</b>", self.styles['Normal'])
            
        data = [
            [logo, "SISTEMA DE GESTION\nSALUD Y SEGURIDAD EN EL TRABAJO", f"CODIGO: {self.codigo}\nVERSION: 1.0\nFECHA: 05/01/2026"],
            ["", Paragraph(f"<b>{self.titulo}</b>", ParagraphStyle('T', alignment=TA_CENTER, fontSize=11, fontName='Helvetica-Bold')), "PAGINA: 1 DE 1"]
        ]
        
        t = Table(data, colWidths=[140, 280, 120], rowHeights=[60, 25])
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('SPAN', (0,0), (0,1)),
            ('FONTSIZE', (2,0), (2,0), 8),
            ('FONTSIZE', (1,0), (1,0), 10),
            ('BACKGROUND', (0,1), (-1,1), colors.whitesmoke)
        ]))
        self.elements.append(t); self.elements.append(Spacer(1, 15))

    def _signature_block(self, firma_b64):
        sig_img = Paragraph("", self.styles['Normal'])
        if firma_b64:
            if firma_b64 == "PENDIENTE_DIGITAL":
                sig_img = Paragraph("ENVÍO DIGITAL MASIVO - PENDIENTE DE ACUSE", ParagraphStyle('P', fontSize=8, alignment=TA_CENTER, textColor=colors.red))
            else:
                try: sig_img = RLImage(io.BytesIO(base64.b64decode(firma_b64)), width=250, height=100)
                except: pass
        
        data = [[sig_img], ["__________________________"], ["FIRMA TRABAJADOR"]]; 
        t = Table(data, colWidths=[300])
        t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'BOTTOM')]))
        self.elements.append(Spacer(1, 20)); self.elements.append(t)

    def generar_reporte_ds67(self, data_ds67):
        self._header()
        self.elements.append(Paragraph(f"INFORME MENSUAL DE SINIESTRALIDAD DS67 - {data_ds67['periodo']}", self.styles['Heading2']))
        self.elements.append(Spacer(1, 10))
        t_res = Table([["MASA IMPONIBLE PROMEDIO", str(data_ds67['masa'])], ["TOTAL DÍAS PERDIDOS", str(data_ds67['dias'])], ["INVALIDECES / MUERTES", str(data_ds67['inv'])], ["TASA SINIESTRALIDAD EFECTIVA", f"{data_ds67['tasa']:.2f}"], ["COTIZACIÓN ADICIONAL PROYECTADA", f"{data_ds67['cot']:.2f}%"]], colWidths=[300, 150])
        t_res.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (0,4), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (0,4), colors.white)]))
        self.elements.append(t_res); self.elements.append(Spacer(1, 20)); self.elements.append(Paragraph("Detalle Mensual:", self.styles['Heading3']))
        det = [["MES/AÑO", "MASA", "DIAS PERDIDOS", "INVALIDEZ"]]
        for d in data_ds67['detalle']: det.append([f"{d['mes']}/{d['anio']}", str(d['masa']), str(d['dias']), str(d['inv'])])
        t_det = Table(det, colWidths=[100, 100, 100, 100]); t_det.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
        self.elements.append(t_det); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_epp(self, data):
        self._header()
        texto_legal = """De conformidad a lo dispuesto en la <b>Ley 16.744 (Art. 68, inciso 3°)</b> sobre Accidentes del Trabajo y Enfermedades Profesionales..."""
        self.elements.append(Paragraph(texto_legal, ParagraphStyle('Legal', fontSize=11, leading=14, alignment=TA_JUSTIFY)))
        self.elements.append(Spacer(1, 20))
        d_info = [[f"NOMBRE: {data['nombre']}", f"RUT: {data['rut']}"], [f"CARGO: {data['cargo']}", f"FECHA: {data['fecha']}"]]
        t_info = Table(d_info, colWidths=[270, 270], rowHeights=25)
        t_info.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)]))
        self.elements.append(t_info); self.elements.append(Spacer(1, 15))
        self.elements.append(Paragraph("<b>ELEMENTOS DE PROTECCION PERSONAL ENTREGADOS</b>", self.styles['Normal'])); self.elements.append(Spacer(1, 5))
        try: items = ast.literal_eval(data['lista'])
        except: items = []
        t_data = [["CANT", "ELEMENTO / PRODUCTO", "TALLA"]]
        for i in items: t_data.append([str(i.get('cant','1')), i.get('prod','EPP'), i.get('talla', 'U')])
        t_prod = Table(t_data, colWidths=[60, 400, 80])
        t_prod.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('FONTSIZE', (0,0), (-1,-1), 9)]))
        self.elements.append(t_prod); self.elements.append(Spacer(1, 20))
        texto_comp = """El trabajador se compromete a mantener los Elementos de Protección Personal en buen estado..."""
        self.elements.append(Paragraph(texto_comp, ParagraphStyle('Comp', fontSize=11, alignment=TA_JUSTIFY)))
        self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_riohs(self, data):
        self._header()
        legal_1 = """Se deja expresa constancia, de acuerdo a lo establecido en el artículo 156 del Código del Trabajo..."""
        self.elements.append(Paragraph(legal_1, ParagraphStyle('L1', fontSize=10, leading=12, alignment=TA_JUSTIFY))); self.elements.append(Spacer(1, 10))
        legal_2 = """Declaro bajo mi firma haber recibido, leído y comprendido el presente Reglamento Interno..."""
        self.elements.append(Paragraph(legal_2, ParagraphStyle('L2', fontSize=10, leading=12, alignment=TA_JUSTIFY))); self.elements.append(Spacer(1, 10))
        legal_3 = """Este reglamento puede entregarse en electronico conforme se expresa en ordinario N°1086..."""
        self.elements.append(Paragraph(legal_3, ParagraphStyle('L3', fontSize=10, leading=12, alignment=TA_JUSTIFY))); self.elements.append(Spacer(1, 15))
        
        if "Digital" in data.get('tipo_entrega', ''):
            email_val = data.get('email', 'N/A')
            texto_decision = f"<b>EL TRABAJADOR DECIDIO LA RECEPCION DEL RELGAMENTO INTERNO DE ORDEN HIGIENE Y SEGURIDAD DE MANERA DIGITAL AL SIGUIENTE CORREO: {email_val}</b>"
        else:
            texto_decision = "<b>EL TRABAJADOR DECIDIO LA ENTREGA DEL REGLAMENTO INTERNO DE ORDEN HIGIENE Y SEGURIDAD DE MANERA IMPRESA.</b>"
            
        self.elements.append(Paragraph(texto_decision, ParagraphStyle('Decision', fontSize=10, leading=14, alignment=TA_CENTER, fontName='Helvetica-Bold')))
        self.elements.append(Spacer(1, 20))
        legal_4 = """Asumo mi responsabilidad de dar lectura a su contenido y cumplir con las obligaciones..."""
        self.elements.append(Paragraph(legal_4, ParagraphStyle('L4', fontSize=10, leading=12, alignment=TA_JUSTIFY))); self.elements.append(Spacer(1, 20))
        
        sig_img = Paragraph("", self.styles['Normal'])
        if data.get('firma_b64'):
            try: sig_img = RLImage(io.BytesIO(base64.b64decode(data['firma_b64'])), width=200, height=80)
            except: pass
        t_data = [["NOMBRE COMPLETO", data['nombre']], ["RUT", data['rut']], ["CARGO", data['cargo']], ["FECHA DE ENTREGA", data['fecha']], ["FIRMA", sig_img]]
        t_worker = Table(t_data, colWidths=[150, 350], rowHeights=[25, 25, 25, 25, 90])
        t_worker.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (0,-1), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (0,-1), colors.white), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (1,4), (1,4), 'CENTER')]))
        self.elements.append(t_worker); self.elements.append(Spacer(1, 20))
        
        sig_dif = Paragraph("", self.styles['Normal'])
        if data.get('firma_difusor'):
            try: sig_dif = RLImage(io.BytesIO(base64.b64decode(data['firma_difusor'])), width=180, height=70)
            except: pass
        t_difusor = [["NOMBRE DIFUSOR", data.get('nombre_difusor', '___________________________')], ["FIRMA Y TIMBRE", sig_dif]]
        t_dif = Table(t_difusor, colWidths=[150, 350], rowHeights=[25, 80])
        t_dif.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (0,-1), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (0,-1), colors.white), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (1,1), (1,1), 'CENTER')]))
        self.elements.append(t_dif); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

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
# 4. FRONTEND
# ==============================================================================
if 'db_setup_complete' not in st.session_state:
    init_db()
    st.session_state['db_setup_complete'] = True

# --- LOGIN ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user' not in st.session_state: st.session_state['user'] = "Invitado"
if 'rol' not in st.session_state: st.session_state['rol'] = "VISITOR"

if not st.session_state['logged_in']:
    BG_IMAGE = "https://i.imgur.com/aHPH6U6.jpeg"
    LOGO_URL = "https://www.maderasgyd.cl/wp-content/uploads/2024/02/logo-maderas-gd-1.png"
    
    st.markdown(f"""
        <style>
            html, body, [data-testid="stAppViewContainer"] {{overflow: hidden !important; height: 100vh !important; margin: 0;}}
            [data-testid="stSidebar"], [data-testid="stHeader"] {{display: none !important;}}
            .stApp {{background-image: linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.7)), url("{BG_IMAGE}"); background-size: cover; background-position: center; background-attachment: fixed;}}
            div[data-testid="column"]:nth-of-type(2) {{background-color: rgba(255, 255, 255, 0.95); border-radius: 20px; padding: 30px !important; box-shadow: 0 15px 40px rgba(0,0,0,0.6); border-top: 8px solid {COLOR_PRIMARY}; backdrop-filter: blur(5px);}}
            .logo-box {{background-color: #ffffff; border-radius: 10px; padding: 15px; margin-bottom: 25px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); display: flex; justify-content: center;}}
            .login-footer {{text-align: center; color: #888; font-size: 0.8rem; margin-top: 30px; font-weight: bold; border-top: 1px solid #ddd; padding-top: 15px;}}
            div[data-testid="stTextInput"] input {{background-color: #f8f9fa; border: 1px solid #ccc; border-radius: 8px; padding: 10px;}}
        </style>
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown(f"""<div class="logo-box"><img src="{LOGO_URL}" style="width: 100%; max-width: 220px;"></div><h4 style='text-align: center; color: #444; margin-bottom: 20px; font-weight:600;'>INICIAR SESIÓN</h4>""", unsafe_allow_html=True)
        u = st.text_input("Usuario", placeholder="Ingrese usuario", label_visibility="collapsed")
        p = st.text_input("Contraseña", type="password", placeholder="Ingrese contraseña", label_visibility="collapsed")
        st.write("") 
        if st.button("INGRESAR", type="primary", use_container_width=True):
            conn_l = sqlite3.connect(DB_NAME)
            pass_hash = hashlib.sha256(p.encode()).hexdigest()
            user_data = pd.read_sql("SELECT * FROM usuarios WHERE username=? AND password=?", conn_l, params=(u, pass_hash))
            conn_l.close()
            if not user_data.empty:
                st.session_state['logged_in'] = True; st.session_state['user'] = u; st.session_state['rol'] = user_data.iloc[0]['rol']; registrar_auditoria(u, "LOGIN", "OK"); st.rerun()
            else: st.error("🚫 Credenciales incorrectas")
        st.markdown('<div class="login-footer">© 2026 SEGAV<br>Seguridad & Gestión Avanzada</div>', unsafe_allow_html=True)
    st.stop()

with st.sidebar:
    st.title("MADERAS GÁLVEZ")
    st.caption(f"Usuario: {st.session_state['user']} | Rol: {st.session_state['rol']}")
    with open(DB_NAME, "rb") as fp: st.download_button(label="💾 Respaldar BD", data=fp, file_name=f"backup_{date.today()}.db")
    menu_options = ["📊 Dashboard", "⚖️ Gestión DS67", "🛡️ Matriz IPER (ISP)", "👥 Gestión Personas", "⚖️ Gestor Documental", "🦺 Logística EPP", "🎓 Capacitaciones", "🚨 Incidentes & DIAT", "📅 Plan Anual", "🧯 Extintores", "🏗️ Contratistas"]
    if st.session_state['rol'] == "ADMINISTRADOR": menu_options.append("🔐 Gestión Usuarios")
    menu = st.radio("MENÚ", menu_options)
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

# --- 2. GESTION DS67 AVANZADA ---
elif menu == "⚖️ Gestión DS67":
    st.markdown("<div class='main-header'>Gestión de Siniestralidad (DS 67)</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    t1, t2, t3 = st.tabs(["📅 Periodos Evaluación", "📝 Registro Mensual (Bitácora)", "📊 Reporte y Tasa"])
    
    with t1:
        st.subheader("Configuración de Periodos (Ej: Proceso 2025)")
        with st.form("new_period_ds67"):
            p_name = st.text_input("Nombre del Proceso (Ej: 2023-2025)")
            f_start = st.date_input("Fecha Inicio", value=date(2023, 7, 1))
            f_end = st.date_input("Fecha Fin", value=date(2025, 6, 30))
            if st.form_submit_button("Crear Periodo"):
                conn.execute("INSERT INTO periodos_ds67 (nombre_periodo, fecha_inicio, fecha_fin) VALUES (?,?,?)", (p_name, f_start, f_end))
                conn.commit()
                st.success("Periodo creado.")
        st.write("Periodos Activos:")
        st.dataframe(pd.read_sql("SELECT * FROM periodos_ds67", conn))

    with t2:
        st.subheader("Carga de Información Mensual")
        periods = pd.read_sql("SELECT id, nombre_periodo FROM periodos_ds67", conn)
        if not periods.empty:
            sel_p_id = st.selectbox("Seleccione Periodo", periods['id'].astype(str) + " - " + periods['nombre_periodo'])
            pid = sel_p_id.split(" - ")[0]
            
            c1, c2 = st.columns(2)
            with c1:
                mes_sel = st.selectbox("Mes", range(1, 13))
                anio_sel = st.number_input("Año", min_value=2020, max_value=2030, value=2024)
                masa_input = st.number_input("Masa Imponible (N° Trabajadores)", min_value=0, value=100)
            
            with c2:
                # AUTO CALCULO DE DIAS PERDIDOS DESDE INCIDENTES
                dias_auto = 0
                try:
                    query_inc = f"SELECT SUM(dias_perdidos) FROM incidentes WHERE strftime('%m', fecha) = '{mes_sel:02d}' AND strftime('%Y', fecha) = '{anio_sel}'"
                    dias_res = pd.read_sql(query_inc, conn).iloc[0,0]
                    if dias_res: dias_auto = int(dias_res)
                except: pass
                
                st.info(f"Días perdidos detectados en Incidentes: {dias_auto}")
                dias_input = st.number_input("Días Perdidos (Confirmar)", value=dias_auto)
                inv_input = st.number_input("Invalideces / Muertes (Cantidad)", min_value=0, value=0)
            
            if st.button("Guardar Registro Mensual"):
                conn.execute("INSERT INTO detalle_mensual_ds67 (periodo_id, mes, anio, masa_imponible, dias_perdidos, invalideces_muertes) VALUES (?,?,?,?,?,?)",
                             (pid, mes_sel, anio_sel, masa_input, dias_input, inv_input))
                conn.commit()
                st.success("Mes registrado.")
                
            st.divider()
            st.write("Registros del Periodo:")
            st.dataframe(pd.read_sql("SELECT * FROM detalle_mensual_ds67 WHERE periodo_id=?", conn, params=(pid,)))

    with t3:
        st.subheader("Dashboard de Siniestralidad")
        if not periods.empty:
            sel_rep = st.selectbox("Periodo a Evaluar", periods['id'].astype(str) + " - " + periods['nombre_periodo'], key="rep_sel")
            pid_rep = sel_rep.split(" - ")[0]
            
            data_raw = pd.read_sql("SELECT * FROM detalle_mensual_ds67 WHERE periodo_id=?", conn, params=(pid_rep,))
            
            if not data_raw.empty:
                # CALCULOS MUTUALIDAD
                total_masa = data_raw['masa_imponible'].sum()
                avg_masa = data_raw['masa_imponible'].mean()
                total_dias = data_raw['dias_perdidos'].sum()
                total_inv = data_raw['invalideces_muertes'].sum()
                factor_inv = total_inv * 2500 # VALOR LEY DS67
                
                tasa_siniestralidad = ((total_dias + factor_inv) / avg_masa) * 100 if avg_masa > 0 else 0
                cotizacion = determinar_tramo_cotizacion(tasa_siniestralidad)
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Promedio Masa", f"{avg_masa:.1f}")
                k2.metric("Total Días Perdidos", total_dias)
                k3.metric("Tasa Siniestralidad", f"{tasa_siniestralidad:.2f}")
                k4.metric("Cotización Adicional", f"{cotizacion}%")
                
                st.write("Evolución Mensual:")
                st.bar_chart(data_raw, x="mes", y="dias_perdidos")
                
                if st.button("Generar Reporte Oficial PDF"):
                    pdf = DocumentosLegalesPDF("REPORTE TASA DE SINIESTRALIDAD DS67", "INF-DS67-01").generar_reporte_ds67({
                        'periodo': sel_rep, 'masa': round(avg_masa, 1), 'dias': total_dias, 
                        'inv': total_inv, 'tasa': tasa_siniestralidad, 'cot': cotizacion,
                        'detalle': data_raw.to_dict('records')
                    })
                    st.download_button("Descargar Informe", pdf.getvalue(), "Informe_DS67.pdf")
            else:
                st.warning("No hay datos mensuales cargados para este periodo.")

    conn.close()

# --- 3. MATRIZ IPER (V179 - DYNAMIC ROLES & SMART MATRIX) ---
elif menu == "🛡️ Matriz IPER (ISP)":
    st.markdown("<div class='main-header'>Matriz de Riesgos (ISP 2024 + DS44)</div>", unsafe_allow_html=True)
    tab_ver, tab_carga, tab_crear = st.tabs(["👁️ Matriz & Dashboard", "📂 Carga Masiva Inteligente", "➕ Crear Riesgo (Maestro)"])
    conn = get_conn()
    
    with tab_ver:
        # CONSULTA MAESTRA
        query = """SELECT id, 
                   proceso as 'PROCESO', puesto_trabajo as 'PUESTO', tarea as 'TAREA', 
                   lugar_especifico as 'LUGAR', familia_riesgo as 'FAMILIA', codigo_riesgo as 'COD ISP', 
                   factor_gema as 'GEMA', peligro_factor as 'PELIGRO', riesgo_asociado as 'RIESGO',
                   n_hombres as 'H', n_mujeres as 'M', n_disidencias as 'D',
                   probabilidad as 'P_INI', consecuencia as 'C_INI', vep as 'VEP_INI', nivel_riesgo as 'NIVEL_INI',
                   medida_control as 'MEDIDA CONTROL', jerarquia_control as 'JERARQUIA', requisito_legal as 'LEGAL',
                   probabilidad_residual as 'P_RES', consecuencia_residual as 'C_RES', vep_residual as 'VEP_RES', nivel_riesgo_residual as 'NIVEL_RES'
                   FROM matriz_iper"""
        df_matriz = pd.read_sql(query, conn)
        
        # Filtros
        cf1, cf2, cf3 = st.columns(3)
        filtro_nivel = cf1.multiselect("Nivel Riesgo", ["INTOLERABLE", "IMPORTANTE", "MODERADO", "TOLERABLE"])
        filtro_fam = cf2.multiselect("Familia Riesgo", list(ISP_RISK_CODES.keys()))
        filtro_puesto = cf3.multiselect("Puesto Trabajo", df_matriz['PUESTO'].unique() if not df_matriz.empty else [])
        
        df_view = df_matriz.copy()
        if filtro_nivel: df_view = df_view[df_view['NIVEL_INI'].isin(filtro_nivel)]
        if filtro_fam: df_view = df_view[df_view['FAMILIA'].isin(filtro_fam)]
        if filtro_puesto: df_view = df_view[df_view['PUESTO'].isin(filtro_puesto)]
        
        # Dashboard Visual
        with st.expander("📊 Ver Dashboard Visual (Click para abrir)", expanded=False):
            g1, g2 = st.columns(2)
            with g1:
                if not df_view.empty:
                    fig_heat = px.density_heatmap(df_view, x="P_INI", y="C_INI", title="Mapa de Calor (Probabilidad vs Consecuencia)", 
                                                 nbinsx=4, nbinsy=4, color_continuous_scale="Reds")
                    st.plotly_chart(fig_heat, use_container_width=True)
            with g2:
                if not df_view.empty:
                    total_h = df_view['H'].sum(); total_m = df_view['M'].sum(); total_d = df_view['D'].sum()
                    fig_gen = px.pie(values=[total_h, total_m, total_d], names=["Hombres", "Mujeres", "Diversidad"], title="Exposición por Género")
                    st.plotly_chart(fig_gen, use_container_width=True)

        # Editor
        edited_df = st.data_editor(df_view, use_container_width=True, 
            column_config={
                "P_INI": st.column_config.NumberColumn("P (Ini)", min_value=1, max_value=4), 
                "C_INI": st.column_config.NumberColumn("C (Ini)", min_value=1, max_value=4), 
                "VEP_INI": st.column_config.NumberColumn("VEP (Ini)", disabled=True), 
                "NIVEL_INI": st.column_config.TextColumn("Nivel (Ini)", disabled=True),
                "P_RES": st.column_config.NumberColumn("P (Res)", min_value=1, max_value=4), 
                "C_RES": st.column_config.NumberColumn("C (Res)", min_value=1, max_value=4), 
                "VEP_RES": st.column_config.NumberColumn("VEP (Res)", disabled=True), 
                "NIVEL_RES": st.column_config.TextColumn("Nivel (Res)", disabled=True),
                "FAMILIA": st.column_config.SelectboxColumn("FAMILIA", options=list(ISP_RISK_CODES.keys())),
                "GEMA": st.column_config.SelectboxColumn("GEMA", options=["Gente", "Equipos", "Materiales", "Ambiente"]),
                "JERARQUIA": st.column_config.SelectboxColumn("JERARQUIA", options=["Eliminación", "Sustitución", "Ingeniería", "Administrativo", "EPP"])
            }, hide_index=True, key="matriz_ed")
            
        if st.button("💾 Guardar y Recalcular Matriz"):
            c = conn.cursor()
            for i, r in edited_df.iterrows():
                pi = int(r['P_INI']); ci = int(r['C_INI']); vi = pi*ci; ni = calcular_nivel_riesgo(vi)
                pr = int(r['P_RES']) if pd.notnull(r['P_RES']) else 1
                cr = int(r['C_RES']) if pd.notnull(r['C_RES']) else 1
                vr = pr*cr; nr = calcular_nivel_riesgo(vr)
                c.execute("""UPDATE matriz_iper SET 
                             probabilidad=?, consecuencia=?, vep=?, nivel_riesgo=?, 
                             probabilidad_residual=?, consecuencia_residual=?, vep_residual=?, nivel_riesgo_residual=?,
                             medida_control=?, familia_riesgo=?, codigo_riesgo=?, jerarquia_control=?, requisito_legal=?,
                             factor_gema=?, lugar_especifico=?, n_hombres=?, n_mujeres=?, n_disidencias=?
                             WHERE id=?""", 
                             (pi, ci, vi, ni, pr, cr, vr, nr, 
                              r['MEDIDA CONTROL'], r['FAMILIA'], r['COD ISP'], r['JERARQUIA'], r['LEGAL'],
                              r['GEMA'], r['LUGAR'], r['H'], r['M'], r['D'], r['id']))
            conn.commit(); st.success("Matriz Actualizada"); st.rerun()
            
        b = io.BytesIO(); 
        with pd.ExcelWriter(b, engine='openpyxl') as w: edited_df.to_excel(w, index=False)
        st.download_button("📥 Descargar Excel Filtrado", b.getvalue(), "MIPER_FILTRADA.xlsx")

    with tab_carga:
        st.subheader("Carga Masiva Inteligente (Smart Upload)")
        
        # 1. Descarga Template ACTUALIZADO V179
        plantilla = {
            'Proceso':['Cosecha'], 'Puesto':['Operador'], 'Lugar':['Bosque'], 'Familia':['Seguridad'], 'GEMA':['Ambiente'],
            'Peligro':['Pendiente'], 'Riesgo':['Volcamiento'], 
            'Hombres':[5], 'Mujeres':[1], 'Diversidad':[0],
            'P_Inicial':[4], 'C_Inicial':[4], 
            'Medida':['Cabina ROPS'], 'Jerarquia':['Ingeniería'], 'Legal':['DS 594 Art 12'],
            'P_Residual':[1], 'C_Residual':[4]
        }
        b2 = io.BytesIO(); 
        with pd.ExcelWriter(b2, engine='openpyxl') as w: pd.DataFrame(plantilla).to_excel(w, index=False)
        st.download_button("1️⃣ Descargar Plantilla Maestra V179", b2.getvalue(), "plantilla_iper_master.xlsx")
        
        # 2. Carga y Validación
        up = st.file_uploader("2️⃣ Subir Excel", type=['xlsx'])
        if up:
            try:
                df_up = pd.read_excel(up)
                st.info("Pre-visualización y Corrección de Datos (Edite aquí antes de guardar)")
                
                if 'P_Inicial' in df_up.columns and 'C_Inicial' in df_up.columns:
                    df_up['Estado'] = df_up.apply(lambda x: "⚠️ Error P/C" if x['P_Inicial'] not in [1,2,4] or x['C_Inicial'] not in [1,2,4] else "✅ OK", axis=1)
                else:
                    st.error("El archivo no tiene las columnas P_Inicial o C_Inicial. Descargue la plantilla V179.")
                    st.stop()
                
                edited_up = st.data_editor(df_up, num_rows="dynamic", key="editor_up")
                
                if st.button("3️⃣ Procesar Carga Definitiva"):
                    c = conn.cursor()
                    count_ok = 0
                    for i, r in edited_up.iterrows():
                        if r['Estado'] == "✅ OK": 
                            # Safe Int Conversion
                            def s_int(val): return int(val) if pd.notnull(val) else 1
                            def s_str(val): return str(val) if pd.notnull(val) else ""
                            def s_int_0(val): return int(val) if pd.notnull(val) else 0

                            pi = s_int(r.get('P_Inicial')); ci = s_int(r.get('C_Inicial')); vi = pi*ci; ni = calcular_nivel_riesgo(vi)
                            pr = s_int(r.get('P_Residual')); cr = s_int(r.get('C_Residual')); vr = pr*cr; nr = calcular_nivel_riesgo(vr)
                            
                            c.execute("""INSERT INTO matriz_iper 
                                (proceso, puesto_trabajo, lugar_especifico, familia_riesgo, factor_gema, peligro_factor, riesgo_asociado,
                                n_hombres, n_mujeres, n_disidencias,
                                probabilidad, consecuencia, vep, nivel_riesgo, 
                                medida_control, jerarquia_control, requisito_legal,
                                probabilidad_residual, consecuencia_residual, vep_residual, nivel_riesgo_residual) 
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", 
                                (s_str(r.get('Proceso')), s_str(r.get('Puesto')), s_str(r.get('Lugar')), s_str(r.get('Familia')), s_str(r.get('GEMA')), s_str(r.get('Peligro')), s_str(r.get('Riesgo')),
                                 s_int_0(r.get('Hombres')), s_int_0(r.get('Mujeres')), s_int_0(r.get('Diversidad')),
                                 pi, ci, vi, ni, s_str(r.get('Medida')), s_str(r.get('Jerarquia')), s_str(r.get('Legal')), pr, cr, vr, nr))
                            count_ok += 1
                    conn.commit()
                    st.success(f"✅ Se cargaron exitosamente {count_ok} registros.")
                    time.sleep(2)
                    st.rerun()
            except Exception as e: st.error(f"Error crítico en archivo: {e}")

    with tab_crear:
        st.subheader("Evaluación de Riesgo Maestra (Norma ISP 2024)")
        with st.form("risk_master"):
            st.markdown("##### 1. Contexto y Demografía")
            c1, c2, c3 = st.columns(3)
            pro = c1.text_input("Proceso (Ej: Cosecha)")
            
            # --- VINCULO DINAMICO DE PUESTOS (V179) ---
            roles_db = pd.read_sql("SELECT DISTINCT cargo FROM personal", conn)['cargo'].dropna().tolist()
            all_roles = sorted(list(set(LISTA_CARGOS + roles_db)))
            pue = c2.selectbox("Puesto de Trabajo", all_roles)
            
            lug = c3.text_input("Lugar Específico")
            
            d1, d2, d3 = st.columns(3)
            nh = d1.number_input("Hombres (Cis)", min_value=0)
            nm = d2.number_input("Mujeres (Cis)", min_value=0)
            nd = d3.number_input("Diversidades (Trans/No Binario)", min_value=0)
            
            st.markdown("##### 2. Identificación del Peligro (GEMA)")
            c4, c5, c6 = st.columns(3)
            fam = c4.selectbox("Familia Riesgo", list(ISP_RISK_CODES.keys()))
            cod = c5.selectbox("Riesgo Específico (ISP)", ISP_RISK_CODES[fam])
            gema = c6.selectbox("Factor GEMA", ["Gente", "Equipos", "Materiales", "Ambiente"])
            
            pel = st.text_input("Peligro / Factor Específico")
            rie = st.text_input("Riesgo Asociado (Consecuencia Potencial)")
            
            st.markdown("---")
            st.markdown("##### 3. Evaluación PURA (Inicial)")
            e1, e2 = st.columns(2)
            pi = e1.selectbox("Probabilidad Inicial", [1,2,4], key="pi_m")
            ci = e2.selectbox("Consecuencia Inicial", [1,2,4], key="ci_m")
            st.warning(f"Nivel Inicial: {pi*ci} ({calcular_nivel_riesgo(pi*ci)})")
            
            st.markdown("---")
            st.markdown("##### 4. Control y Marco Legal")
            med = st.text_area("Medida de Control")
            l1, l2 = st.columns(2)
            jc = l1.selectbox("Jerarquía Control", ["Eliminación", "Sustitución", "Ingeniería", "Administrativo", "EPP"])
            leg = l2.text_input("Requisito Legal (Ej: DS 594 Art 53)")
            
            st.markdown("---")
            st.markdown("##### 5. Evaluación RESIDUAL (Final)")
            e3, e4 = st.columns(2)
            pr = e3.selectbox("Probabilidad Residual", [1,2,4], key="pr_m")
            cr = e4.selectbox("Consecuencia Residual", [1,2,4], key="cr_m")
            st.success(f"Nivel Residual: {pr*cr} ({calcular_nivel_riesgo(pr*cr)})")
            
            if st.form_submit_button("Guardar Evaluación Maestra"):
                vi = pi*ci; ni = calcular_nivel_riesgo(vi)
                vr = pr*cr; nr = calcular_nivel_riesgo(vr)
                cod_clean = cod.split("(")[-1].replace(")", "")
                
                conn.execute("""INSERT INTO matriz_iper 
                    (proceso, puesto_trabajo, lugar_especifico, familia_riesgo, codigo_riesgo, factor_gema, peligro_factor, riesgo_asociado, 
                    n_hombres, n_mujeres, n_disidencias,
                    probabilidad, consecuencia, vep, nivel_riesgo, 
                    medida_control, jerarquia_control, requisito_legal,
                    probabilidad_residual, consecuencia_residual, vep_residual, nivel_riesgo_residual) 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", 
                    (pro, pue, lug, fam, cod_clean, gema, pel, rie, nh, nm, nd, pi, ci, vi, ni, med, jc, leg, pr, cr, vr, nr))
                conn.commit(); st.success("Riesgo Maestro Guardado"); st.rerun()
            
    conn.close()

# --- 4. GESTION PERSONAS ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Capital Humano</div>", unsafe_allow_html=True)
    conn = get_conn()
    try:
        total = pd.read_sql("SELECT count(*) FROM personal", conn).iloc[0,0]
        activos = pd.read_sql("SELECT count(*) FROM personal WHERE estado='ACTIVO'", conn).iloc[0,0]
    except: total=0; activos=0
    k1, k2, k3 = st.columns(3)
    k1.metric("Dotación Total", total); k2.metric("Activos", activos); k3.metric("Bajas", total-activos)
    
    tab_list, tab_carga, tab_new, tab_dig, tab_del = st.tabs(["📋 Nómina", "📂 Carga Masiva", "➕ Nuevo", "🗂️ Carpeta", "❌ Eliminar"])
    
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
                
                # HELPER PARA EVITAR NULOS (FIX V180)
                def clean_str(val): return str(val) if pd.notnull(val) else ""
                
                fec = r['fecha_contrato']; f_ex = r['vigencia_examen_medico']
                if pd.isna(fec) or str(fec)=='NaT': fec = date.today()
                if pd.isna(f_ex) or str(f_ex)=='NaT': f_ex = None
                
                if r['rut'] != r['rut_old']:
                    c.execute("UPDATE personal SET rut=?, nombre=?, cargo=?, centro_costo=?, email=?, estado=?, fecha_contrato=?, vigencia_examen_medico=?, contacto_emergencia=?, fono_emergencia=? WHERE rut=?", 
                              (clean_str(r['rut']), clean_str(r['nombre']), clean_str(r['cargo']), clean_str(r['centro_costo']), clean_str(r['email']), clean_str(r['estado']), fec, f_ex, clean_str(r['contacto_emergencia']), clean_str(r['fono_emergencia']), r['rut_old']))
                    c.execute("UPDATE asistencia_capacitacion SET trabajador_rut=? WHERE trabajador_rut=?", (r['rut'], r['rut_old']))
                    c.execute("UPDATE registro_epp SET rut_trabajador=? WHERE rut_trabajador=?", (r['rut'], r['rut_old']))
                    c.execute("UPDATE registro_riohs SET rut_trabajador=? WHERE rut_trabajador=?", (r['rut'], r['rut_old']))
                else:
                    c.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=?, email=?, estado=?, fecha_contrato=?, vigencia_examen_medico=?, contacto_emergencia=?, fono_emergencia=? WHERE rut=?", 
                              (clean_str(r['nombre']), clean_str(r['cargo']), clean_str(r['centro_costo']), clean_str(r['email']), clean_str(r['estado']), fec, f_ex, clean_str(r['contacto_emergencia']), clean_str(r['fono_emergencia']), r['rut']))
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
        limpiar_db = st.checkbox("⚠️ Borrar TODA la base de datos antes de cargar", value=False)
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
    
    with tab_del:
        st.subheader("🗑️ Eliminar Trabajador")
        st.warning("⚠️ Esta acción es irreversible. Se eliminará el trabajador y su historial.")
        all_workers = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        if not all_workers.empty:
            del_sel = st.selectbox("Seleccione Trabajador a Eliminar:", all_workers['rut'] + " - " + all_workers['nombre'])
            del_rut = del_sel.split(" - ")[0]
            if st.button("CONFIRMAR ELIMINACIÓN", type="primary"):
                conn.execute("DELETE FROM personal WHERE rut=?", (del_rut,))
                conn.commit()
                st.success("Trabajador eliminado correctamente.")
                time.sleep(1)
                st.rerun()
    conn.close()

# --- 5. GESTOR DOCUMENTAL (V168 - RIOHS PRO CON EMAIL, CAMPAÑA MASIVA Y TRAZABILIDAD) ---
elif menu == "⚖️ Gestor Documental":
    st.markdown("<div class='main-header'>Centro Documental</div>", unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["IRL", "RIOHS", "Historial"])
    conn = get_conn(); df_p = pd.read_sql("SELECT rut, nombre, cargo, email FROM personal", conn)
    
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
            st.subheader("Entrega de Reglamento Interno (RIOHS)")
            tab_ind, tab_mass = st.tabs(["Entrega Individual", "📢 Campaña Masiva"])
            
            with tab_ind:
                sel_r = st.selectbox("Trabajador RIOHS:", df_p['rut'] + " | " + df_p['nombre'])
                rut_w = sel_r.split(" | ")[0]
                nom_w = sel_r.split(" | ")[1]
                worker_data = df_p[df_p['rut'] == rut_w].iloc[0]
                email_w = worker_data['email'] if worker_data['email'] else "Sin Email"
                
                with st.form("riohs_form"):
                    c1, c2 = st.columns(2)
                    with c1:
                        tipo_ent = st.radio("Formato de Entrega:", ["Físico (Papel)", "Digital (Email)"], index=0)
                        if tipo_ent == "Digital (Email)":
                            st.info(f"📧 Se enviará al correo: {email_w}")
                    with c2:
                        nom_dif = st.text_input("Nombre del Difusor (Quien entrega):")
                    
                    st.divider()
                    c3, c4 = st.columns(2)
                    with c3:
                        st.write("Firma Trabajador:")
                        sig_worker = st_canvas(stroke_width=2, stroke_color="black", background_color="#eeeeee", height=150, width=400, key="sig_w_riohs_v168")
                    with c4:
                        st.write("Firma Difusor:")
                        sig_diffuser = st_canvas(stroke_width=2, stroke_color="black", background_color="#eeeeee", height=150, width=400, key="sig_d_riohs_v168")
                    
                    if st.form_submit_button("Registrar Entrega RIOHS"):
                        if sig_worker.image_data is not None and sig_diffuser.image_data is not None and nom_dif:
                            img_w = process_signature_bg(sig_worker.image_data); b_w = io.BytesIO(); img_w.save(b_w, format='PNG'); str_w = base64.b64encode(b_w.getvalue()).decode()
                            img_d = process_signature_bg(sig_diffuser.image_data); b_d = io.BytesIO(); img_d.save(b_d, format='PNG'); str_d = base64.b64encode(b_d.getvalue()).decode()
                            
                            tipo_db = "Digital" if "Digital" in tipo_ent else "Físico"
                            
                            pdf = DocumentosLegalesPDF("REGISTRO DE ENTREGA DE REGLAMENTO INTERNO DE ORDEN, HIGIENE Y SEGURIDAD", "RG-SSTGD-03").generar_riohs({
                                'nombre': nom_w, 'rut': rut_w, 'cargo': worker_data['cargo'], 
                                'fecha': date.today().strftime("%d-%m-%Y"), 
                                'firma_b64': str_w, 'tipo_entrega': tipo_db, 'email': email_w,
                                'nombre_difusor': nom_dif, 'firma_difusor': str_d
                            })
                            pdf_bytes = pdf.getvalue()
                            
                            estado_envio = "N/A"
                            if tipo_db == "Digital":
                                exito, msg = enviar_correo_riohs(email_w, nom_w, pdf_bytes, f"RIOHS_{rut_w}.pdf")
                                estado_envio = "ENVIADO" if exito else "ERROR"
                                if exito: st.success(f"📧 {msg}")
                                else: st.error(f"❌ Error envío: {msg}")
                            
                            conn.execute("""INSERT INTO registro_riohs (fecha_entrega, rut_trabajador, nombre_trabajador, tipo_entrega, firma_b64, nombre_difusor, firma_difusor_b64, email_copia, estado_envio) VALUES (?,?,?,?,?,?,?,?,?)""", 
                                (date.today(), rut_w, nom_w, tipo_db, str_w, nom_dif, str_d, email_w, estado_envio))
                            conn.commit()
                            
                            st.download_button("📥 Descargar Acta", pdf_bytes, f"RIOHS_{rut_w}.pdf", "application/pdf")
                            st.success("Entrega registrada.")
                        else:
                            st.warning("⚠️ Faltan firmas.")

            with tab_mass:
                st.info("📢 Campaña Masiva de RIOHS Digital")
                difusor_mass = st.text_input("Nombre del Difusor (Campaña Masiva):")
                st.write("Firma del Difusor:")
                sig_mass = st_canvas(stroke_width=2, stroke_color="black", background_color="#eeeeee", height=150, width=400, key="sig_mass_v168")
                
                if st.button("🚀 INICIAR CAMPAÑA", type="primary"):
                    if difusor_mass and sig_mass.image_data is not None:
                        img_d = process_signature_bg(sig_mass.image_data); b_d = io.BytesIO(); img_d.save(b_d, format='PNG'); str_d = base64.b64encode(b_d.getvalue()).decode()
                        targets = pd.read_sql("SELECT rut, nombre, cargo, email FROM personal WHERE estado='ACTIVO' AND email IS NOT NULL AND email != ''", conn)
                        
                        prog_bar = st.progress(0); status_txt = st.empty()
                        count = 0
                        
                        for i, t in targets.iterrows():
                            pdf = DocumentosLegalesPDF("REGISTRO DE ENTREGA DE REGLAMENTO INTERNO DE ORDEN, HIGIENE Y SEGURIDAD", "RG-SSTGD-03").generar_riohs({
                                'nombre': t['nombre'], 'rut': t['rut'], 'cargo': t['cargo'], 
                                'fecha': date.today().strftime("%d-%m-%Y"), 
                                'firma_b64': "PENDIENTE_DIGITAL", 
                                'tipo_entrega': "Digital", 'email': t['email'],
                                'nombre_difusor': difusor_mass, 'firma_difusor': str_d
                            })
                            exito, msg = enviar_correo_riohs(t['email'], t['nombre'], pdf.getvalue(), f"RIOHS_{t['rut']}.pdf")
                            st_env = "ENVIADO" if exito else "ERROR"
                            conn.execute("""INSERT INTO registro_riohs (fecha_entrega, rut_trabajador, nombre_trabajador, tipo_entrega, firma_b64, nombre_difusor, firma_difusor_b64, email_copia, estado_envio) VALUES (?,?,?,?,?,?,?,?,?)""", 
                                (date.today(), t['rut'], t['nombre'], "Digital", "PENDIENTE_DIGITAL", difusor_mass, str_d, t['email'], st_env))
                            count += 1
                            prog_bar.progress((i + 1) / len(targets))
                            status_txt.text(f"Procesando: {t['nombre']} - {st_env}")
                            
                        conn.commit()
                        st.success(f"✅ Campaña finalizada. {count} correos procesados.")
                    else:
                        st.warning("Falta nombre o firma del difusor.")

        with t3:
            st.dataframe(pd.read_sql("SELECT id, fecha_entrega, nombre_trabajador, tipo_entrega, email_copia, estado_envio FROM registro_riohs ORDER BY id DESC", conn))
    conn.close()

# --- 6. LOGISTICA EPP ---
elif menu == "🦺 Logística EPP":
    st.markdown("<div class='main-header'>Logística y Entrega EPP</div>", unsafe_allow_html=True)
    conn = get_conn()
    
    t1, t2, t3 = st.tabs(["🛍️ Entrega (Carrito)", "📦 Inventario", "📜 Historial"])
    
    with t1:
        st.subheader("Registro de Entrega")
        df_workers = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
        
        if df_workers.empty:
            st.warning("No hay personal registrado.")
        else:
            w_opts = df_workers['rut'] + " | " + df_workers['nombre']
            sel_w = st.selectbox("Seleccionar Trabajador:", w_opts)
            rut_w = sel_w.split(" | ")[0]
            nom_w = sel_w.split(" | ")[1]
            cargo_w = df_workers[df_workers['rut'] == rut_w]['cargo'].values[0]
            
            st.divider()
            
            if 'epp_cart' not in st.session_state: st.session_state.epp_cart = []
            if 'epp_step' not in st.session_state: st.session_state.epp_step = 1
            
            if st.session_state.epp_step == 1:
                if st.button("📦 Cargar Kit Básico (Nuevo Ingreso)"):
                    kit = [{"prod": "CASCO DE SEGURIDAD", "cant": 1, "talla": "U", "precio": 12000}, {"prod": "LENTES DE SEGURIDAD", "cant": 1, "talla": "U", "precio": 3000}, {"prod": "GUANTE CABRITILLA", "cant": 1, "talla": "U", "precio": 4500}, {"prod": "CHALECO REFLECTANTE", "cant": 1, "talla": "L", "precio": 3500}]
                    st.session_state.epp_cart = kit
                    st.success("Kit cargado. Revise tallas.")

                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                inv_df = pd.read_sql("SELECT producto, stock_actual, precio FROM inventario_epp WHERE stock_actual > 0", conn)
                
                if inv_df.empty:
                    st.error("No hay stock disponible en bodega.")
                else:
                    with c1: 
                        prod_sel = st.selectbox("Elemento EPP", inv_df['producto'])
                        last_del = pd.read_sql("SELECT fecha_entrega FROM registro_epp WHERE rut_trabajador=? AND lista_productos LIKE ? ORDER BY id DESC LIMIT 1", conn, params=(rut_w, f"%{prod_sel}%"))
                        if not last_del.empty:
                            f_last = datetime.strptime(last_del.iloc[0,0], '%Y-%m-%d').date()
                            dias = (date.today() - f_last).days
                            if dias < 30: st.warning(f"⚠️ {prod_sel} entregado hace solo {dias} días ({f_last})")
                            else: st.caption(f"✅ Última entrega: {f_last} (Hace {dias} días)")
                    
                    with c2: cant_sel = st.number_input("Cant", min_value=1, value=1)
                    with c3: talla_sel = st.selectbox("Talla", ["U", "S", "M", "L", "XL", "XXL", "38", "39", "40", "41", "42", "43", "44", "45"], index=0)
                    with c4:
                        st.write("")
                        if st.button("➕ Agregar"):
                            row = inv_df[inv_df['producto'] == prod_sel].iloc[0]
                            if row['stock_actual'] >= cant_sel:
                                st.session_state.epp_cart.append({"prod": prod_sel, "cant": cant_sel, "talla": talla_sel, "precio": int(row['precio'])})
                            else: st.error("Stock insuficiente.")

                if st.session_state.epp_cart:
                    st.write("---"); st.markdown("##### Resumen de Entrega y Costos")
                    cart_df = pd.DataFrame(st.session_state.epp_cart)
                    cart_df['Subtotal'] = cart_df['cant'] * cart_df['precio']
                    total_cost = cart_df['Subtotal'].sum()
                    st.table(cart_df); st.metric("Costo Total Estimado", f"${total_cost:,.0f}")
                    
                    if st.button("🗑️ Vaciar Carrito"): st.session_state.epp_cart = []; st.rerun()
                    
                    st.write("---"); st.write("Firma de Recepción (Trabajador):")
                    firm_canvas = st_canvas(stroke_width=2, height=350, width=700, key="epp_sig_big", background_color="#eeeeee")
                    
                    if st.button("✅ CONFIRMAR ENTREGA"):
                        if firm_canvas.image_data is not None:
                            img = process_signature_bg(firm_canvas.image_data)
                            b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
                            conn.execute("INSERT INTO registro_epp (fecha_entrega, rut_trabajador, nombre_trabajador, cargo, lista_productos, firma_b64) VALUES (?,?,?,?,?,?)", (date.today(), rut_w, nom_w, cargo_w, str(st.session_state.epp_cart), img_str))
                            for item in st.session_state.epp_cart:
                                conn.execute("UPDATE inventario_epp SET stock_actual = stock_actual - ? WHERE producto=?", (item['cant'], item['prod']))
                            conn.commit()
                            pdf = DocumentosLegalesPDF("REGISTRO ENTREGA ELEMENTOS DE PROTECCION PERSONAL", "RG-SSTGD-01").generar_epp({
                                'nombre': nom_w, 'rut': rut_w, 'cargo': cargo_w, 'fecha': date.today().strftime("%d-%m-%Y"), 'lista': str(st.session_state.epp_cart), 'firma_b64': img_str
                            })
                            st.session_state.pdf_buffer = pdf.getvalue(); st.session_state.epp_step = 2; st.rerun()
                        else: st.warning("Debe firmar para confirmar.")

            elif st.session_state.epp_step == 2:
                st.success("✅ Entrega registrada exitosamente.")
                st.download_button(label="📥 DESCARGAR ACTA RG-SSTGD-01", data=st.session_state.pdf_buffer, file_name=f"EPP_{rut_w}.pdf", mime="application/pdf")
                st.write("")
                if st.button("🔄 Finalizar y Limpiar"):
                    st.session_state.epp_cart = []; st.session_state.epp_step = 1; del st.session_state.pdf_buffer; st.rerun()

    with t2:
        st.subheader("Gestión de Inventario (Precios y Stock)")
        current_inv = pd.read_sql("SELECT * FROM inventario_epp", conn)
        edited_inv = st.data_editor(current_inv, num_rows="dynamic", use_container_width=True, key="inv_editor", column_config={"precio": st.column_config.NumberColumn("Precio Unitario ($)", format="$%d")})
        if st.button("💾 Guardar Cambios Inventario"):
            conn.execute("DELETE FROM inventario_epp")
            for i, r in edited_inv.iterrows():
                p = r.get('precio', 0); 
                if pd.isna(p): p = 0
                conn.execute("INSERT INTO inventario_epp (producto, stock_actual, stock_minimo, ubicacion, precio) VALUES (?,?,?,?,?)", (r['producto'], r['stock_actual'], r['stock_minimo'], r['ubicacion'], int(p)))
            conn.commit(); st.success("Inventario actualizado."); time.sleep(1); st.rerun()
            
    with t3:
        st.subheader("📜 Historial Detallado")
        hist_df = pd.read_sql("SELECT fecha_entrega, nombre_trabajador, cargo, lista_productos FROM registro_epp ORDER BY id DESC", conn)
        st.dataframe(hist_df, use_container_width=True)
            
    conn.close()

# --- 7. CAPACITACIONES (CON QR FIXED) ---
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

# --- 8. OTROS ---
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

# --- 9. GESTIÓN USUARIOS ---
elif menu == "🔐 Gestión Usuarios":
    st.markdown("<div class='main-header'>Administración de Usuarios y Accesos</div>", unsafe_allow_html=True)
    conn = get_conn()
    try:
        total_u = pd.read_sql("SELECT count(*) FROM usuarios", conn).iloc[0,0]
        admins = pd.read_sql("SELECT count(*) FROM usuarios WHERE rol='ADMINISTRADOR'", conn).iloc[0,0]
    except: total_u=0; admins=0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Usuarios Totales", total_u)
    c2.metric("Administradores", admins)
    c3.metric("Seguridad", "Activa", delta_color="normal")
    st.divider()

    tab_list, tab_edit, tab_create = st.tabs(["👥 Directorio", "🛠️ Editar / Eliminar", "➕ Nuevo Usuario"])
    
    with tab_list:
        st.subheader("Directorio de Accesos")
        users_df = pd.read_sql("SELECT username as 'Usuario', rol as 'Rol Asignado' FROM usuarios", conn)
        st.dataframe(users_df, use_container_width=True, hide_index=True)
        
    with tab_edit:
        st.subheader("Gestión de Cuentas Existentes")
        all_users = pd.read_sql("SELECT username FROM usuarios", conn)['username'].tolist()
        user_to_edit = st.selectbox("Seleccione Usuario a gestionar:", all_users)
        
        if user_to_edit:
            st.info(f"Editando a: **{user_to_edit}**")
            col_a, col_b = st.columns(2)
            with col_a:
                with st.form("edit_role"):
                    st.markdown("##### Cambiar Rol")
                    new_role = st.selectbox("Nuevo Rol", ["ADMINISTRADOR", "VISOR", "PREVENCIONISTA", "GERENCIA"])
                    if st.form_submit_button("Actualizar Rol"):
                        if user_to_edit == "admin" and new_role != "ADMINISTRADOR":
                            st.error("🚫 No puedes quitarle el rol de admin al superusuario principal.")
                        else:
                            conn.execute("UPDATE usuarios SET rol=? WHERE username=?", (new_role, user_to_edit))
                            conn.commit()
                            registrar_auditoria(st.session_state['user'], "UPDATE_USER", f"Cambio rol de {user_to_edit} a {new_role}")
                            st.success("Rol actualizado.")
                            time.sleep(1)
                            st.rerun()
            with col_b:
                with st.form("reset_pass"):
                    st.markdown("##### Resetear Contraseña")
                    new_p1 = st.text_input("Nueva Contraseña", type="password")
                    new_p2 = st.text_input("Confirmar Contraseña", type="password")
                    if st.form_submit_button("Cambiar Clave"):
                        if new_p1 and new_p1 == new_p2:
                            hashed = hashlib.sha256(new_p1.encode()).hexdigest()
                            conn.execute("UPDATE usuarios SET password=? WHERE username=?", (hashed, user_to_edit))
                            conn.commit()
                            registrar_auditoria(st.session_state['user'], "RESET_PASS", f"Cambio clave de {user_to_edit}")
                            st.success("Contraseña actualizada exitosamente.")
                        else:
                            st.error("Las contraseñas no coinciden o están vacías.")
            st.divider()
            with st.expander("🗑️ Zona de Peligro - Eliminar Usuario"):
                st.warning(f"¿Estás seguro de eliminar a {user_to_edit}? Esta acción no se puede deshacer.")
                if st.button("SÍ, ELIMINAR CUENTA DEFINITIVAMENTE", type="primary"):
                    if user_to_edit == st.session_state['user']:
                        st.error("🚫 No puedes eliminar tu propia cuenta mientras estás logueado.")
                    elif user_to_edit == "admin":
                        st.error("🚫 El usuario 'admin' base no puede ser eliminado.")
                    else:
                        conn.execute("DELETE FROM usuarios WHERE username=?", (user_to_edit,))
                        conn.commit()
                        registrar_auditoria(st.session_state['user'], "DELETE_USER", f"Eliminó al usuario {user_to_edit}")
                        st.success(f"Usuario {user_to_edit} eliminado.")
                        time.sleep(1)
                        st.rerun()

    with tab_create:
        st.subheader("Registrar Nuevo Acceso")
        with st.form("create_user_pro"):
            c1, c2 = st.columns(2)
            new_u = c1.text_input("Nombre de Usuario (Único)")
            new_r = c2.selectbox("Rol de Acceso", ["ADMINISTRADOR", "PREVENCIONISTA", "VISOR", "GERENCIA"])
            c3, c4 = st.columns(2)
            pass1 = c3.text_input("Contraseña", type="password")
            pass2 = c4.text_input("Repetir Contraseña", type="password")
            if st.form_submit_button("Crear Usuario"):
                if new_u and pass1 and pass2:
                    if pass1 != pass2:
                        st.error("❌ Las contraseñas no coinciden.")
                    else:
                        try:
                            exists = pd.read_sql("SELECT username FROM usuarios WHERE username=?", conn, params=(new_u,))
                            if not exists.empty:
                                st.error("❌ El usuario ya existe.")
                            else:
                                h_pw = hashlib.sha256(pass1.encode()).hexdigest()
                                conn.execute("INSERT INTO usuarios (username, password, rol) VALUES (?,?,?)", (new_u, h_pw, new_r))
                                conn.commit()
                                registrar_auditoria(st.session_state['user'], "CREATE_USER", f"Creó usuario {new_u}")
                                st.success(f"✅ Usuario {new_u} creado correctamente.")
                                time.sleep(1)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error técnico: {e}")
                else:
                    st.warning("⚠️ Complete todos los campos obligatorios.")
    conn.close()
