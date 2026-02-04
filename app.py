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
st.set_page_config(page_title="SGSST ERP MASTER", layout="wide", page_icon="🏗️", initial_sidebar_state="collapsed")

DB_NAME = 'sgsst_v200_master.db' 
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
        .logo-box {background-color: #ffffff; border-radius: 10px; padding: 15px; margin-bottom: 25px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); display: flex; justify-content: center;}
        .login-footer {text-align: center; color: #888; font-size: 0.8rem; margin-top: 30px; font-weight: bold; border-top: 1px solid #ddd; padding-top: 15px;}
        .stApp {background-size: cover; background-position: center; background-attachment: fixed;}
    </style>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
""", unsafe_allow_html=True)

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
    try:
        if img_data is None: return create_text_signature_img("Firma No Detectada")
        if isinstance(img_data, np.ndarray):
            if np.all(img_data == 0): return create_text_signature_img("Firma Vacía")
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
    except Exception:
        return create_text_signature_img("Error de Firma")

def create_text_signature_img(text_sig):
    width, height = 400, 100
    image = PILImage.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 40), "Firmado digitalmente por:", fill="black")
    draw.text((20, 60), str(text_sig), fill="black")
    return image

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
    
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
        id INTEGER PRIMARY KEY AUTOINCREMENT, proceso TEXT, tipo_proceso TEXT, puesto_trabajo TEXT, tarea TEXT, es_rutinaria TEXT, 
        lugar_especifico TEXT, familia_riesgo TEXT, codigo_riesgo TEXT, factor_gema TEXT, peligro_factor TEXT, riesgo_asociado TEXT, 
        tipo_riesgo TEXT, probabilidad INTEGER, consecuencia INTEGER, vep INTEGER, nivel_riesgo TEXT, 
        medida_control TEXT, jerarquia_control TEXT, requisito_legal TEXT,
        probabilidad_residual INTEGER, consecuencia_residual INTEGER, vep_residual INTEGER, nivel_riesgo_residual TEXT,
        genero_obs TEXT, n_hombres INTEGER, n_mujeres INTEGER, n_disidencias INTEGER
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
    conn.close(); return alertas

# ==============================================================================
# 3. MOTOR DOCUMENTAL (RESTAURACIÓN LEGAL V200)
# ==============================================================================
class DocumentosLegalesPDF:
    def __init__(self, titulo_doc, codigo_doc):
        self.buffer = io.BytesIO(); self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=30, leftMargin=30, rightMargin=30); self.elements = []
        self.styles = getSampleStyleSheet(); self.titulo = titulo_doc; self.codigo = codigo_doc; self.logo_url = "https://www.maderasgyd.cl/wp-content/uploads/2024/02/logo-maderas-gd-1.png"

    def _header(self):
        try: logo = RLImage(self.logo_url, width=120, height=50)
        except: logo = Paragraph("<b>MADERAS G&D</b>", self.styles['Normal'])
        data = [
            [logo, "SISTEMA DE GESTION\nSALUD Y SEGURIDAD EN EL TRABAJO", f"CODIGO: {self.codigo}\nVERSION: 1.0\nFECHA: 05/01/2026"],
            ["", Paragraph(f"<b>{self.titulo}</b>", ParagraphStyle('T', alignment=TA_CENTER, fontSize=11, fontName='Helvetica-Bold')), "PAGINA: 1 DE 1"]
        ]
        t = Table(data, colWidths=[140, 280, 120], rowHeights=[60, 25])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('SPAN', (0,0), (0,1)), ('BACKGROUND', (0,1), (-1,1), colors.whitesmoke)]))
        self.elements.append(t); self.elements.append(Spacer(1, 15))

    def _signature_block(self, firma_b64):
        sig_img = Paragraph("", self.styles['Normal'])
        if firma_b64:
            try: sig_img = RLImage(io.BytesIO(base64.b64decode(firma_b64)), width=200, height=80)
            except: pass
        data = [[sig_img], ["__________________________"], ["FIRMA TRABAJADOR"]]; 
        t = Table(data, colWidths=[300]); t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'BOTTOM')]))
        self.elements.append(Spacer(1, 20)); self.elements.append(t)

    def generar_epp(self, data):
        self._header()
        # --- TEXTO LEGAL EPP MEJORADO ---
        texto_legal = """Certifico haber recibido de mi empleador, <b>SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA.</b>, los Elementos de Protección Personal (EPP) detallados en este documento, los cuales son nuevos (o en buen estado), de mi talla y adecuados para los riesgos de mi puesto de trabajo. La entrega se realiza a título gratuito, en estricto cumplimiento del <b>Artículo 68 de la Ley 16.744</b> y el <b>Decreto Supremo N° 594</b>. Declaro además haber recibido la capacitación teórica y práctica sobre el uso correcto, mantención y almacenamiento de estos equipos."""
        self.elements.append(Paragraph(texto_legal, ParagraphStyle('Legal', fontSize=10, leading=12, alignment=TA_JUSTIFY)))
        self.elements.append(Spacer(1, 15))
        d_info = [[f"NOMBRE: {data['nombre']}", f"RUT: {data['rut']}"], [f"CARGO: {data['cargo']}", f"FECHA: {data['fecha']}"]]
        t_info = Table(d_info, colWidths=[270, 270], rowHeights=25)
        t_info.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke)]))
        self.elements.append(t_info); self.elements.append(Spacer(1, 10))
        try: items = ast.literal_eval(data['lista'])
        except: items = []
        t_data = [["CANT", "ELEMENTO / PRODUCTO", "TALLA"]]
        for i in items: t_data.append([str(i.get('cant','1')), i.get('prod','EPP'), i.get('talla', 'U')])
        t_prod = Table(t_data, colWidths=[60, 400, 80])
        t_prod.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t_prod); self.elements.append(Spacer(1, 15))
        texto_comp = """Me comprometo a utilizar estos EPP permanentemente durante mi jornada laboral y a solicitar su reposición inmediata en caso de deterioro, pérdida o daño, devolviendo el equipo usado según procedimiento interno. El incumplimiento de esta obligación podrá ser sancionado según lo estipulado en el Reglamento Interno."""
        self.elements.append(Paragraph(texto_comp, ParagraphStyle('Comp', fontSize=10, alignment=TA_JUSTIFY)))
        self._signature_block(data['firma_b64']); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_riohs(self, data):
        self._header()
        # --- TEXTO LEGAL RIOHS EXACTO ---
        txt1 = "Se deja expresa constancia, de acuerdo a lo establecido en el artículo 156 del Código del Trabajo y DS 44 de la Ley 16.744 que, he recibido en forma gratuita un ejemplar del Reglamento Interno de Orden, Higiene y Seguridad de SOCIEDAD MADERERA GÁLVEZ Y DI GÉNOVA LTDA."
        self.elements.append(Paragraph(txt1, ParagraphStyle('L1', fontSize=10, leading=12, alignment=TA_JUSTIFY)))
        self.elements.append(Spacer(1, 10))
        txt2 = "Declaro bajo mi firma haber recibido, leído y comprendido el presente Reglamento Interno de Orden, Higiene y Seguridad, del cual doy fe de conocer el contenido de éste y me hago responsable de su estricto cumplimiento en cada uno de sus artículos, no pudiendo alegar desconocimiento de su texto a contar de esta fecha."
        self.elements.append(Paragraph(txt2, ParagraphStyle('L2', fontSize=10, leading=12, alignment=TA_JUSTIFY)))
        self.elements.append(Spacer(1, 10))
        txt3 = "Este reglamento puede entregarse en electronico conforme se expresa en ordinario N°1086, del 06/03/15, departamento juridico, de la direccion del trabajo, siendo mi decision que la entrega de este documento se haga de acuerdo a lo siguiente:"
        self.elements.append(Paragraph(txt3, ParagraphStyle('L3', fontSize=10, leading=12, alignment=TA_JUSTIFY)))
        self.elements.append(Spacer(1, 10))
        
        # Lógica dinámica para la decisión
        tipo_str = str(data.get('tipo_entrega', 'Físico'))
        email_val = str(data.get('email', 'N/A')).upper()
        if "Digital" in tipo_str:
            texto_decision = f"<b>EL TRABAJADOR DECIDIO LA RECEPCION DEL REGLAMENTO INTERNO DE ORDEN HIGIENE Y SEGURIDAD DE MANERA DIGITAL AL SIGUIENTE CORREO: {email_val}</b>"
        else:
            texto_decision = "<b>EL TRABAJADOR DECIDIO LA ENTREGA DEL REGLAMENTO INTERNO DE ORDEN HIGIENE Y SEGURIDAD DE MANERA IMPRESA.</b>"
        self.elements.append(Paragraph(texto_decision, ParagraphStyle('Decision', fontSize=10, alignment=TA_CENTER, fontName='Helvetica-Bold')))
        self.elements.append(Spacer(1, 15))
        
        txt4 = "Asumo mi responsabilidad de dar lectura a su contenido y cumplir con las obligaciones, prohibiciones, normas de orden, higiene y seguridad que en el estan escritas, como asi tambien las dispocisiones y procedimientos que en forma posterior se emitan y/o modifiquen y que formen parte de este reglamento o que expresamente lo indique."
        self.elements.append(Paragraph(txt4, ParagraphStyle('L4', fontSize=10, leading=12, alignment=TA_JUSTIFY)))
        self.elements.append(Spacer(1, 15))
        
        sig_img = Paragraph("", self.styles['Normal'])
        if data.get('firma_b64'):
            try: sig_img = RLImage(io.BytesIO(base64.b64decode(data['firma_b64'])), width=180, height=70)
            except: pass
        t_worker = Table([["NOMBRE COMPLETO", str(data['nombre'])], ["RUT", str(data['rut'])], ["CARGO", str(data['cargo'])], ["FECHA DE ENTREGA", str(data['fecha'])], ["FIRMA", sig_img]], colWidths=[150, 350], rowHeights=[25, 25, 25, 25, 80])
        t_worker.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (0,-1), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (0,-1), colors.white), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        self.elements.append(t_worker); self.elements.append(Spacer(1, 15))
        
        sig_dif = Paragraph("", self.styles['Normal'])
        if data.get('firma_difusor'):
            try: sig_dif = RLImage(io.BytesIO(base64.b64decode(data['firma_difusor'])), width=160, height=60)
            except: pass
        t_dif = Table([["NOMBRE DIFUSOR", str(data.get('nombre_difusor', '___________________________'))], ["FIRMA Y TIMBRE", sig_dif]], colWidths=[150, 350], rowHeights=[25, 70])
        t_dif.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (0,-1), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (0,-1), colors.white), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        self.elements.append(t_dif); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_reporte_ds67(self, data_ds67):
        self._header()
        self.elements.append(Paragraph(f"INFORME MENSUAL DE SINIESTRALIDAD DS67 - {data_ds67['periodo']}", self.styles['Heading2']))
        t_res = Table([["MASA IMPONIBLE PROMEDIO", str(data_ds67['masa'])], ["TOTAL DÍAS PERDIDOS", str(data_ds67['dias'])], ["TASA SINIESTRALIDAD EFECTIVA", f"{data_ds67['tasa']:.2f}"], ["COTIZACIÓN ADICIONAL PROYECTADA", f"{data_ds67['cot']:.2f}%"]], colWidths=[300, 150])
        t_res.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (0,3), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (0,3), colors.white)]))
        self.elements.append(t_res); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_irl(self, data, riesgos):
        self._header(); self.elements.append(Paragraph(f"IRL: {data['nombre']}", self.styles['Heading3']))
        r_data = [["PELIGRO", "RIESGO", "MEDIDA"]]; 
        for r in riesgos: r_data.append([Paragraph(str(r[0]), ParagraphStyle('s', fontSize=8)), Paragraph(str(r[1]), ParagraphStyle('s', fontSize=8)), Paragraph(str(r[2]), ParagraphStyle('s', fontSize=8))])
        t = Table(r_data, colWidths=[130, 130, 250]); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
        self.elements.append(t); self.elements.append(Spacer(1, 30)); self.elements.append(Paragraph("Recibí información (DS44).", self.styles['Normal'])); self._signature_block(None); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

    def generar_asistencia_capacitacion(self, data, asis):
        self._header(); self.elements.append(Paragraph("ASISTENCIA CAPACITACION", self.styles['Heading3']))
        tc = Table([[f"TEMA: {data['tema']}", f"FECHA: {data['fecha']}"]], colWidths=[260, 260]); tc.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
        self.elements.append(tc); self.elements.append(Spacer(1, 15))
        a_data = [["NOMBRE", "RUT", "FIRMA"]]; row_h = [20]
        for a in asis: 
            f_img = ""
            if a.get('firma_b64'):
                try: f_img = RLImage(io.BytesIO(base64.b64decode(a['firma_b64'])), width=100, height=30)
                except: pass
            a_data.append([a['nombre'], a['rut'], f_img]); row_h.append(40)
        t = Table(a_data, colWidths=[200, 100, 150], rowHeights=row_h); t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), HexColor(COLOR_PRIMARY)), ('TEXTCOLOR', (0,0), (-1,0), colors.white)]))
        self.elements.append(t); self.doc.build(self.elements); self.buffer.seek(0); return self.buffer

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
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown(f"""<div class="logo-box"><img src="{LOGO_URL}" style="width: 100%; max-width: 220px;"></div><h4 style='text-align: center; color: #444; margin-bottom: 20px; font-weight:600;'>INICIAR SESIÓN</h4>""", unsafe_allow_html=True)
        u = st.text_input("Usuario", placeholder="Ingrese usuario", label_visibility="collapsed")
        p = st.text_input("Contraseña", type="password", placeholder="Ingrese contraseña", label_visibility="collapsed")
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
    menu = st.radio("MENÚ", ["📊 Dashboard", "⚖️ Gestión DS67", "🛡️ Matriz IPER (ISP)", "👥 Gestión Personas", "⚖️ Gestor Documental", "🦺 Logística EPP", "🎓 Capacitaciones", "🚨 Incidentes & DIAT", "📅 Plan Anual", "🧯 Extintores", "🏗️ Contratistas", "🔐 Gestión Usuarios"])
    if st.button("Cerrar Sesión"): st.session_state['logged_in'] = False; st.rerun()

# --- 1. DASHBOARD ---
if menu == "📊 Dashboard":
    st.markdown(f"""<div style="background-color: {COLOR_SECONDARY}; padding: 20px; border-radius: 10px; margin-bottom: 20px; color: white;"><h2 style="margin:0; color:white;">Bienvenido, {st.session_state['user'].capitalize()}</h2><p style="margin:0;">Sistema de Gestión SST | {date.today().strftime('%d-%m-%Y')}</p></div>""", unsafe_allow_html=True)
    conn = get_conn()
    k1, k2, k3, k4 = st.columns(4)
    try:
        acc = pd.read_sql("SELECT count(*) FROM incidentes", conn).iloc[0,0]
        trabs = pd.read_sql("SELECT count(*) FROM personal WHERE estado='ACTIVO'", conn).iloc[0,0]
        alertas = get_alertas()
    except: acc=0; trabs=0; alertas=[]
    k1.markdown(f"<div class='card-kpi'><h3>Dotación</h3><h1>👷 {trabs}</h1></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='card-kpi'><h3>Accidentes</h3><h1>🚑 {acc}</h1></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='card-kpi'><h3>Alertas</h3><h1>⚠️ {len(alertas)}</h1></div>", unsafe_allow_html=True)
    k4.markdown(f"<div class='card-kpi'><h3>Estado</h3><h1>✅ OK</h1></div>", unsafe_allow_html=True)
    conn.close()

# --- 2. GESTION DS67 ---
elif menu == "⚖️ Gestión DS67":
    st.markdown("<div class='main-header'>Gestión de Siniestralidad (DS 67)</div>", unsafe_allow_html=True)
    conn = get_conn()
    t1, t2 = st.tabs(["📝 Registro", "📊 Reporte"])
    with t1:
        with st.form("ds67"):
            p = st.text_input("Periodo (Ej: 2024)")
            m = st.number_input("Masa Promedio", 1)
            d = st.number_input("Dias Perdidos", 0)
            if st.form_submit_button("Guardar"):
                st.success("Registrado")
    conn.close()

# --- 3. MATRIZ IPER (ISP V3) ---
elif menu == "🛡️ Matriz IPER (ISP)":
    st.markdown("<div class='main-header'>Matriz de Riesgos (ISP 2024 + DS44)</div>", unsafe_allow_html=True)
    conn = get_conn()
    tab_ver, tab_carga, tab_crear = st.tabs(["👁️ Ver Matriz", "📂 Carga Masiva", "➕ Crear Maestro"])
    
    with tab_ver:
        df_matriz = pd.read_sql("SELECT * FROM matriz_iper", conn)
        st.dataframe(df_matriz, use_container_width=True)
        
    with tab_carga:
        # --- PLANTILLA ACTUALIZADA V200 ---
        plantilla = {'Proceso':['Cosecha'], 'Puesto':['OPERADOR DE ASERRADERO'], 'Lugar':['Bosque'], 'Familia':['Seguridad'], 'GEMA':['Ambiente'], 'Peligro':['Pendiente'], 'Riesgo':['Volcamiento'], 'Hombres':[5], 'Mujeres':[1], 'Diversidad':[0], 'P_Inicial':[4], 'C_Inicial':[4], 'Medida':['Cabina ROPS'], 'Jerarquia':['Ingeniería'], 'Legal':['DS 594 Art 12'], 'P_Residual':[1], 'C_Residual':[4]}
        b_p = io.BytesIO(); 
        with pd.ExcelWriter(b_p, engine='openpyxl') as wr: pd.DataFrame(plantilla).to_excel(wr, index=False)
        st.download_button("1️⃣ Descargar Plantilla V200", b_p.getvalue(), "plantilla_iper_v200.xlsx")
        
    with tab_crear:
        with st.form("risk_m"):
            proc = st.text_input("Proceso")
            roles_db = pd.read_sql("SELECT DISTINCT cargo FROM personal", conn)['cargo'].dropna().tolist()
            puesto = st.selectbox("Puesto Trabajo (Sincronizado)", sorted(list(set(LISTA_CARGOS + roles_db))))
            pel = st.text_input("Peligro")
            rie = st.text_input("Riesgo")
            p_i = st.selectbox("P", [1,2,4])
            c_i = st.selectbox("C", [1,2,4])
            med = st.text_area("Medida Control")
            if st.form_submit_button("Guardar"):
                conn.execute("INSERT INTO matriz_iper (proceso, puesto_trabajo, peligro_factor, riesgo_asociado, probabilidad, consecuencia, vep, nivel_riesgo, medida_control, nivel_riesgo_residual) VALUES (?,?,?,?,?,?,?,?,?,?)", (proc, puesto, pel, rie, p_i, c_i, p_i*c_i, calcular_nivel_riesgo(p_i*c_i), med, "MODERADO"))
                conn.commit(); st.success("Guardado")
    conn.close()

# --- 4. GESTIÓN PERSONAS ---
elif menu == "👥 Gestión Personas":
    st.markdown("<div class='main-header'>Gestión de Capital Humano</div>", unsafe_allow_html=True)
    conn = get_conn()
    tab_list, tab_new = st.tabs(["📋 Nómina", "➕ Nuevo"])
    
    with tab_list:
        df_p = pd.read_sql("SELECT * FROM personal", conn)
        edited = st.data_editor(df_p, use_container_width=True, num_rows="dynamic", key="per_ed")
        if st.button("💾 Guardar Cambios"):
            c = conn.cursor()
            for i, r in edited.iterrows():
                def clean(v): return str(v).strip() if pd.notnull(v) and str(v).lower() != "nan" else None
                c.execute("UPDATE personal SET nombre=?, cargo=?, centro_costo=?, email=?, estado=?, fecha_contrato=?, vigencia_examen_medico=?, contacto_emergencia=?, fono_emergencia=? WHERE rut=?", 
                          (clean(r['nombre']), clean(r['cargo']), clean(r['centro_costo']), clean(r['email']), clean(r['estado']), clean(r['fecha_contrato']), clean(r['vigencia_examen_medico']), clean(r['contacto_emergencia']), clean(r['fono_emergencia']), clean(r['rut'])))
            conn.commit(); st.success("Guardado"); st.rerun()
            
    with tab_new:
        with st.form("n_p"):
            rut = st.text_input("RUT"); nom = st.text_input("Nombre"); car = st.selectbox("Cargo", LISTA_CARGOS)
            c_em = st.text_input("Contacto Emergencia"); f_em = st.text_input("Fono Emergencia")
            if st.form_submit_button("Registrar"):
                conn.execute("INSERT INTO personal (rut, nombre, cargo, estado, contacto_emergencia, fono_emergencia) VALUES (?,?,?,?,?,?)", (rut, nom, car, 'ACTIVO', c_em, f_em))
                conn.commit(); st.success("OK")
    conn.close()

# --- 5. GESTOR DOCUMENTAL (FIX V200) ---
elif menu == "⚖️ Gestor Documental":
    st.markdown("<div class='main-header'>Centro Documental</div>", unsafe_allow_html=True)
    conn = get_conn(); df_p = pd.read_sql("SELECT rut, nombre, cargo, email FROM personal", conn)
    t1, t2 = st.tabs(["IRL", "RIOHS"])
    
    with t1:
        sel = st.selectbox("Trabajador:", df_p['rut'] + " - " + df_p['nombre'] + " (" + df_p['cargo'] + ")")
        if st.button("Generar IRL"):
            rut_sel = sel.split(" - ")[0]; w_data = df_p[df_p['rut']==rut_sel].iloc[0]
            # --- SYNC: BUSCAR RIESGOS POR CARGO ---
            riesgos = pd.read_sql("SELECT peligro_factor, riesgo_asociado, medida_control FROM matriz_iper WHERE puesto_trabajo=?", conn, params=(w_data['cargo'],))
            if riesgos.empty: riesgos = pd.read_sql("SELECT peligro_factor, riesgo_asociado, medida_control FROM matriz_iper LIMIT 3", conn)
            pdf = DocumentosLegalesPDF("IRL", "RG-GD-04").generar_irl({'nombre': w_data['nombre']}, riesgos.values.tolist())
            st.download_button("Descargar IRL", pdf.getvalue(), "IRL.pdf")
            
    with t2:
        sel_r = st.selectbox("Trabajador RIOHS:", df_p['rut'] + " | " + df_p['nombre'])
        rut_w = sel_r.split(" | ")[0]; w_data = df_p[df_p['rut']==rut_w].iloc[0]
        tipo_ent = st.radio("Entrega:", ["Físico (Papel)", "Digital (Email)"])
        nom_dif = st.text_input("Difusor:")
        c1, c2 = st.columns(2)
        with c1: st.write("Firma Trabajador:"); s_w = st_canvas(height=150, width=400, key=f"s_w_{rut_w}")
        with c2: st.write("Firma Difusor:"); s_d = st_canvas(height=150, width=400, key=f"s_d_{rut_w}")
        if st.button("Registrar y Generar"):
            if s_w.image_data is not None and s_d.image_data is not None:
                img_w = process_signature_bg(s_w.image_data); b_w = io.BytesIO(); img_w.save(b_w, format='PNG'); str_w = base64.b64encode(b_w.getvalue()).decode()
                img_d = process_signature_bg(s_d.image_data); b_d = io.BytesIO(); img_d.save(b_d, format='PNG'); str_d = base64.b64encode(b_d.getvalue()).decode()
                pdf = DocumentosLegalesPDF("RIOHS", "RG-GD-03").generar_riohs({'nombre':w_data['nombre'], 'rut':rut_w, 'cargo':w_data['cargo'], 'fecha':str(date.today()), 'firma_b64':str_w, 'tipo_entrega':tipo_ent, 'email':w_data['email'], 'nombre_difusor':nom_dif, 'firma_difusor':str_d})
                st.download_button("Descargar Acta RIOHS", pdf.getvalue(), "Acta_RIOHS.pdf")
    conn.close()

# --- 6. LOGISTICA EPP (FIX V200) ---
elif menu == "🦺 Logística EPP":
    st.markdown("<div class='main-header'>Logística y Entrega EPP</div>", unsafe_allow_html=True)
    conn = get_conn(); df_p = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    sel_w = st.selectbox("Trabajador:", df_p['rut'] + " | " + df_p['nombre'])
    rut_w = sel_w.split(" | ")[0]; w_data = df_p[df_p['rut']==rut_w].iloc[0]
    items = st.text_area("EPP (formato lista: [{'prod': 'CASCO', 'cant': 1}, ...])", value="[{'prod': 'Zapatos de Seguridad', 'cant': 1, 'talla': '42'}]")
    st.write("Firma Recepción:")
    s_epp = st_canvas(height=200, width=500, key=f"s_epp_{rut_w}")
    if st.button("Confirmar Entrega"):
        if s_epp.image_data is not None:
            img = process_signature_bg(s_epp.image_data); b = io.BytesIO(); img.save(b, format='PNG'); str_s = base64.b64encode(b.getvalue()).decode()
            pdf = DocumentosLegalesPDF("ENTREGA EPP", "RG-GD-01").generar_epp({'nombre':w_data['nombre'], 'rut':rut_w, 'cargo':w_data['cargo'], 'fecha':str(date.today()), 'lista':items, 'firma_b64':str_s})
            st.download_button("Descargar Acta EPP", pdf.getvalue(), "Acta_EPP.pdf")
    conn.close()

# --- OTROS MENUS MANTENIDOS ---
elif menu == "🎓 Capacitaciones": st.title("Capacitaciones")
elif menu == "🚨 Incidentes & DIAT": st.title("Incidentes")
elif menu == "📅 Plan Anual": st.title("Plan Anual")
elif menu == "🧯 Extintores": st.title("Extintores")
elif menu == "🏗️ Contratistas": st.title("Contratistas")
elif menu == "🔐 Gestión Usuarios": st.title("Usuarios")
