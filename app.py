import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import io
import hashlib
import os
import base64
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter, legal
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as ReportLabImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from streamlit_drawable_canvas import st_canvas

# ==============================================================================
# 1. CONFIGURACIÓN ESTRATÉGICA (ERP)
# ==============================================================================
st.set_page_config(page_title="SGSST | Gestión Documental", layout="wide", page_icon="🛡️")

DB_NAME = 'sgsst_v97_production.db'  # Nueva DB limpia
LOGO_FILE = "logo_empresa.png"
G_CORP = HexColor('#8B0000') # Rojo Corporativo
G_BLACK = colors.black
G_WHITE = colors.white

# --- BASE DE CONOCIMIENTO TÉCNICA (RIESGOS POR CARGO) ---
# Esta estructura garantiza que el IRL siempre tenga contenido técnico válido
RIESGOS_DB = {
    "OPERADOR DE MAQUINARIA": [
        ("Volcamiento", "Muerte/Aplastamiento", "Uso cabina ROPS/FOPS, Cinturón de seguridad"),
        ("Atropello", "Muerte/Fracturas", "Alerta sonora de retroceso, Respetar señalización"),
        ("Ruido", "Hipoacusia", "Uso permanente de fonos certificados")
    ],
    "MOTOSIERRISTA": [
        ("Corte por cadena", "Amputación/Hemorragia", "Uso pantalón anticorte, Botín forestal"),
        ("Caída de ramas", "Golpe/Muerte", "Uso de casco, Planificación de caída"),
        ("Vibración", "Trastornos musculoesqueléticos", "Pausas activas, Guantes antivibración")
    ],
    "JEFE DE PATIO": [
        ("Atropello", "Muerte", "Chaleco Geólogo Alta Visibilidad, Contacto visual"),
        ("Caída mismo nivel", "Esguince", "Tránsito por vías habilitadas y despejadas")
    ],
    "DEFAULT": [
        ("Caída mismo nivel", "Contusiones", "Mantener orden y aseo"),
        ("Golpe por objetos", "Hematomas", "Atención al entorno")
    ]
}

# ==============================================================================
# 2. ARQUITECTURA DE DATOS (SQL)
# ==============================================================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Tabla Usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    
    # Tabla Personal (Maestro de Trabajadores)
    c.execute('''CREATE TABLE IF NOT EXISTS personal (
        rut TEXT PRIMARY KEY, nombre TEXT, cargo TEXT, centro_costo TEXT, 
        fecha_contrato DATE, estado TEXT)''')
    
    # Tabla EPP (Historial de Entregas)
    c.execute('''CREATE TABLE IF NOT EXISTS registro_epp (
        id INTEGER PRIMARY KEY AUTOINCREMENT, rut_trabajador TEXT, nombre_trabajador TEXT,
        cargo TEXT, fecha_entrega DATE, lista_productos TEXT, firma_b64 TEXT)''')
    
    # Tabla RIOHS (Reglamento Interno)
    c.execute('''CREATE TABLE IF NOT EXISTS registro_riohs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, rut_trabajador TEXT, nombre_trabajador TEXT,
        tipo_entrega TEXT, fecha_entrega DATE, firma_b64 TEXT)''')
        
    # Tabla Capacitaciones (Cabecera)
    c.execute('''CREATE TABLE IF NOT EXISTS capacitaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, tema TEXT, 
        relator TEXT, tipo_actividad TEXT, estado TEXT)''')
        
    # Tabla Asistencia (Detalle)
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia (
        id INTEGER PRIMARY KEY AUTOINCREMENT, id_cap INTEGER, 
        rut_trabajador TEXT, nombre_trabajador TEXT, firma_b64 TEXT)''')

    # Seed Admin
    c.execute("SELECT count(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO usuarios VALUES (?,?,?)", ("admin", hashlib.sha256("1234".encode()).hexdigest(), "ADMINISTRADOR"))
        
    # Seed Trabajadores Ejemplo
    c.execute("SELECT count(*) FROM personal")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO personal VALUES (?,?,?,?,?,?)", ("12.345.678-9", "JUAN PEREZ", "OPERADOR DE MAQUINARIA", "FAENA", date.today(), "ACTIVO"))
        c.execute("INSERT INTO personal VALUES (?,?,?,?,?,?)", ("9.876.543-2", "PEDRO SOTO", "MOTOSIERRISTA", "FAENA", date.today(), "ACTIVO"))

    conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect(DB_NAME)

# ==============================================================================
# 3. MOTOR DE DOCUMENTOS (REPORTLAB PDF)
# ==============================================================================
class PDFGenerator:
    def __init__(self, title, code):
        self.buffer = io.BytesIO()
        self.doc = SimpleDocTemplate(self.buffer, pagesize=letter, topMargin=30, bottomMargin=30)
        self.elements = []
        self.styles = getSampleStyleSheet()
        self.title = title
        self.code = code

    def add_header(self):
        # Logo y Título
        logo = Paragraph("<b>MADERAS GÁLVEZ</b>", self.styles["Normal"])
        if os.path.exists(LOGO_FILE):
            logo = ReportLabImage(LOGO_FILE, width=80, height=40)
        
        data = [[logo, Paragraph(f"SISTEMA DE GESTIÓN SST - DS44<br/><b>{self.title}</b>", self.styles['Title']), 
                 Paragraph(f"CÓDIGO: {self.code}<br/>VER: 01<br/>FECHA: {datetime.now().strftime('%d/%m/%Y')}", self.styles['Normal'])]]
        
        t = Table(data, colWidths=[100, 300, 100])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, G_BLACK), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        self.elements.append(t)
        self.elements.append(Spacer(1, 20))

    def generate_epp(self, data):
        self.add_header()
        # Datos Trabajador
        p = Paragraph(f"<b>NOMBRE:</b> {data['nombre']} | <b>RUT:</b> {data['rut']} | <b>CARGO:</b> {data['cargo']}", self.styles['Normal'])
        self.elements.append(p); self.elements.append(Spacer(1, 10))
        
        # Tabla EPP
        items = eval(data['lista_productos']) # Convertir string a lista
        t_data = [["CANT", "DESCRIPCIÓN EPP", "MOTIVO"]]
        for i in items:
            t_data.append([str(i['cant']), i['prod'], i['motivo']])
            
        t = Table(t_data, colWidths=[50, 300, 150])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), G_CORP), ('TEXTCOLOR', (0,0), (-1,0), G_WHITE),
            ('GRID', (0,0), (-1,-1), 0.5, G_BLACK), ('ALIGN', (0,0), (-1,-1), 'CENTER')
        ]))
        self.elements.append(t); self.elements.append(Spacer(1, 20))
        
        # Legal
        self.elements.append(Paragraph("<b>DECLARACIÓN:</b> Certifico haber recibido los EPP indicados en buen estado (Art. 53 DS 594).", self.styles['Normal']))
        self.elements.append(Spacer(1, 30))
        
        # Firma
        self.add_signature(data['firma_b64'])
        self.doc.build(self.elements)
        return self.buffer.getvalue()

    def generate_riohs(self, data):
        self.add_header()
        self.elements.append(Paragraph(f"<b>NOMBRE:</b> {data['nombre']} | <b>RUT:</b> {data['rut']}", self.styles['Normal']))
        self.elements.append(Spacer(1, 20))
        
        text = """En cumplimiento a lo dispuesto en el Artículo 156 del Código del Trabajo y la Ley 16.744, 
        la empresa hace entrega gratuita del Reglamento Interno de Orden, Higiene y Seguridad (RIOHS).
        <br/><br/>
        El trabajador declara recibir el ejemplar, leerlo y cumplir sus disposiciones."""
        
        self.elements.append(Paragraph(text, self.styles['Normal']))
        self.elements.append(Spacer(1, 20))
        self.elements.append(Paragraph(f"<b>TIPO DE ENTREGA:</b> {data['tipo_entrega']}", self.styles['Normal']))
        self.elements.append(Spacer(1, 40))
        self.add_signature(data['firma_b64'])
        self.doc.build(self.elements)
        return self.buffer.getvalue()

    def generate_irl(self, data, riesgos):
        self.add_header()
        # Datos
        t_data = [["EMPRESA:", "MADERAS GÁLVEZ LTDA", "RUT:", "77.110.060-0"],
                  ["TRABAJADOR:", data['nombre'], "RUT:", data['rut']],
                  ["CARGO:", data['cargo'], "FECHA:", datetime.now().strftime("%d/%m/%Y")]]
        t = Table(t_data, colWidths=[70, 180, 50, 100])
        t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, G_BLACK), ('BACKGROUND', (0,0), (1,-1), colors.whitesmoke)]))
        self.elements.append(t); self.elements.append(Spacer(1, 15))
        
        # Riesgos
        self.elements.append(Paragraph("<b>RIESGOS INHERENTES (ART 21 DS 40):</b>", self.styles['Heading3']))
        r_data = [["PELIGRO/RIESGO", "CONSECUENCIA", "MEDIDA DE CONTROL"]]
        for r in riesgos:
            r_data.append([f"{r[0]}", r[1], r[2]])
            
        rt = Table(r_data, colWidths=[150, 150, 200])
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), G_CORP), ('TEXTCOLOR', (0,0), (-1,0), G_WHITE),
            ('GRID', (0,0), (-1,-1), 0.5, G_BLACK), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('FONTSIZE', (0,0), (-1,-1), 8)
        ]))
        self.elements.append(rt); self.elements.append(Spacer(1, 30))
        
        self.elements.append(Paragraph("Declaro haber sido informado de los riesgos laborales.", self.styles['Normal']))
        self.add_signature(None) # IRL suele firmarse en papel o digital simple
        self.doc.build(self.elements)
        return self.buffer.getvalue()

    def add_signature(self, b64_str):
        if b64_str:
            try:
                img_data = base64.b64decode(b64_str)
                img_io = io.BytesIO(img_data)
                img = ReportLabImage(img_io, width=150, height=60)
                self.elements.append(img)
            except:
                self.elements.append(Paragraph("[Error en imagen de firma]", self.styles['Normal']))
        self.elements.append(Paragraph("__________________________<br/>FIRMA TRABAJADOR", ParagraphStyle('C', alignment=TA_CENTER)))

# ==============================================================================
# 4. FRONTEND (STREAMLIT)
# ==============================================================================
init_db()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# --- LOGIN ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🔐 SGSST ERP")
        u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
        if st.button("Ingresar", use_container_width=True):
            if u == "admin" and p == "1234": 
                st.session_state['logged_in'] = True; st.rerun()
            else: st.error("Credenciales incorrectas")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.image(LOGO_FILE) if os.path.exists(LOGO_FILE) else st.title("MADERAS GÁLVEZ")
    st.info("Usuario: Administrador")
    menu = st.radio("MÓDULOS:", ["👥 Personal", "🦺 Entrega EPP", "📘 Entrega RIOHS", "📄 Generador ODI/IRL", "🎓 Capacitaciones"])
    if st.button("Salir"): st.session_state['logged_in'] = False; st.rerun()

# --- MÓDULO PERSONAL ---
if menu == "👥 Personal":
    st.title("Maestro de Personal")
    conn = get_conn()
    
    tab1, tab2 = st.tabs(["Listado", "Nuevo Trabajador"])
    with tab1:
        df = pd.read_sql("SELECT * FROM personal", conn)
        st.dataframe(df, use_container_width=True)
    with tab2:
        with st.form("new_p"):
            rut = st.text_input("RUT")
            nom = st.text_input("Nombre Completo")
            cargo = st.selectbox("Cargo", list(RIESGOS_DB.keys()))
            cc = st.selectbox("Centro Costo", ["FAENA", "ASERRADERO", "OFICINA"])
            if st.form_submit_button("Guardar"):
                try:
                    conn.execute("INSERT INTO personal VALUES (?,?,?,?,?,?)", (rut, nom, cargo, cc, date.today(), "ACTIVO"))
                    conn.commit(); st.success("Guardado"); st.rerun()
                except Exception as e: st.error(f"Error: {e}")
    conn.close()

# --- MÓDULO EPP ---
elif menu == "🦺 Entrega EPP":
    st.title("Registro de Entrega de EPP (RG-GD-01)")
    conn = get_conn()
    trabajadores = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    
    sel = st.selectbox("Trabajador:", trabajadores['rut'] + " | " + trabajadores['nombre'])
    rut_sel = sel.split(" | ")[0]
    cargo_sel = trabajadores[trabajadores['rut'] == rut_sel]['cargo'].values[0]
    
    if 'cart' not in st.session_state: st.session_state.cart = []
    
    c1, c2, c3 = st.columns(3)
    prod = c1.selectbox("Producto", ["Casco", "Lentes", "Guantes", "Zapatos", "Legionario", "Fonos"])
    cant = c2.number_input("Cantidad", 1, 10, 1)
    mot = c3.selectbox("Motivo", ["Nuevo", "Reposición", "Deterioro"])
    
    if st.button("Agregar a la Lista"):
        st.session_state.cart.append({"prod": prod, "cant": cant, "motivo": mot})
    
    if st.session_state.cart:
        st.table(st.session_state.cart)
        st.write("Firma del Trabajador:")
        canvas = st_canvas(stroke_width=2, height=150, key="epp_sig")
        
        if st.button("Guardar Registro"):
            if canvas.image_data is not None:
                img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
                c = conn.cursor()
                c.execute("INSERT INTO registro_epp (rut_trabajador, nombre_trabajador, cargo, fecha_entrega, lista_productos, firma_b64) VALUES (?,?,?,?,?,?)",
                         (rut_sel, sel.split(" | ")[1], cargo_sel, date.today(), str(st.session_state.cart), img_str))
                conn.commit()
                st.success("Registro Guardado")
                
                # Generar PDF al vuelo
                gen = PDFGenerator("COMPROBANTE DE ENTREGA EPP", "RG-GD-01")
                pdf = gen.generate_epp({'nombre': sel.split(" | ")[1], 'rut': rut_sel, 'cargo': cargo_sel, 'lista_productos': str(st.session_state.cart), 'firma_b64': img_str})
                st.download_button("Descargar PDF Firmado", pdf, "EPP_Firmado.pdf", "application/pdf")
                
                st.session_state.cart = [] # Reset
            else: st.warning("Falta firma")
    conn.close()

# --- MÓDULO RIOHS ---
elif menu == "📘 Entrega RIOHS":
    st.title("Entrega RIOHS (RG-GD-03)")
    conn = get_conn()
    trabajadores = pd.read_sql("SELECT rut, nombre FROM personal", conn)
    sel = st.selectbox("Trabajador:", trabajadores['rut'] + " | " + trabajadores['nombre'])
    
    tipo = st.selectbox("Formato", ["Físico (Papel)", "Digital (Email)"])
    st.write("Firma de Recepción:")
    canvas = st_canvas(stroke_width=2, height=150, key="riohs_sig")
    
    if st.button("Registrar Entrega"):
        if canvas.image_data is not None:
            img = PILImage.fromarray(canvas.image_data.astype('uint8'), 'RGBA'); b = io.BytesIO(); img.save(b, format='PNG'); img_str = base64.b64encode(b.getvalue()).decode()
            rut_sel = sel.split(" | ")[0]
            nombre_sel = sel.split(" | ")[1]
            
            conn.execute("INSERT INTO registro_riohs (rut_trabajador, nombre_trabajador, tipo_entrega, fecha_entrega, firma_b64) VALUES (?,?,?,?,?)",
                        (rut_sel, nombre_sel, tipo, date.today(), img_str))
            conn.commit()
            st.success("RIOHS Entregado")
            
            gen = PDFGenerator("RECEPCIÓN RIOHS", "RG-GD-03")
            pdf = gen.generate_riohs({'nombre': nombre_sel, 'rut': rut_sel, 'tipo_entrega': tipo, 'firma_b64': img_str})
            st.download_button("Descargar Acta RIOHS", pdf, "RIOHS.pdf", "application/pdf")
    conn.close()

# --- MÓDULO ODI/IRL ---
elif menu == "📄 Generador ODI/IRL":
    st.title("Obligación de Informar (RG-GD-04)")
    st.info("Este módulo utiliza la base de conocimiento de riesgos pre-cargada para evitar errores.")
    conn = get_conn()
    trabajadores = pd.read_sql("SELECT rut, nombre, cargo FROM personal", conn)
    
    sel = st.selectbox("Trabajador:", trabajadores['rut'] + " | " + trabajadores['nombre'])
    if sel:
        rut_sel = sel.split(" | ")[0]
        cargo_sel = trabajadores[trabajadores['rut'] == rut_sel]['cargo'].values[0]
        st.write(f"**Cargo Detectado:** {cargo_sel}")
        
        riesgos = RIESGOS_DB.get(cargo_sel, RIESGOS_DB["DEFAULT"])
        st.table(pd.DataFrame(riesgos, columns=["Riesgo", "Consecuencia", "Medida Control"]))
        
        if st.button("Generar Documento ODI"):
            gen = PDFGenerator("OBLIGACIÓN DE INFORMAR", "RG-GD-04")
            data = {'nombre': sel.split(" | ")[1], 'rut': rut_sel, 'cargo': cargo_sel}
            pdf = gen.generate_irl(data, riesgos)
            st.download_button("Descargar ODI para Firma", pdf, f"ODI_{rut_sel}.pdf", "application/pdf")
    conn.close()

# --- MÓDULO CAPACITACIONES ---
elif menu == "🎓 Capacitaciones":
    st.title("Registro Capacitaciones (RG-GD-02)")
    conn = get_conn()
    
    with st.form("cap_form"):
        tema = st.text_input("Tema Capacitación")
        relator = st.text_input("Relator")
        tipo = st.selectbox("Tipo", ["Charla 5 min", "Inducción", "Específica"])
        
        trabajadores = pd.read_sql("SELECT rut, nombre FROM personal", conn)
        asistentes = st.multiselect("Asistentes:", trabajadores['rut'] + " | " + trabajadores['nombre'])
        
        if st.form_submit_button("Registrar Capacitación"):
            c = conn.cursor()
            c.execute("INSERT INTO capacitaciones (fecha, tema, relator, tipo_actividad, estado) VALUES (?,?,?,?,?)",
                     (date.today(), tema, relator, tipo, "EJECUTADA"))
            id_cap = c.lastrowid
            
            for a in asistentes:
                rut = a.split(" | ")[0]
                nom = a.split(" | ")[1]
                c.execute("INSERT INTO asistencia (id_cap, rut_trabajador, nombre_trabajador) VALUES (?,?,?)", (id_cap, rut, nom))
            
            conn.commit()
            st.success(f"Capacitación ID {id_cap} guardada con {len(asistentes)} asistentes.")
            
    # Listado Histórico
    st.subheader("Historial")
    df_cap = pd.read_sql("SELECT * FROM capacitaciones ORDER BY id DESC", conn)
    st.dataframe(df_cap)
    conn.close()
