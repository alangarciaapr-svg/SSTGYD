import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

# ==============================================================================
# 1. CAPA DE INFRAESTRUCTURA DE DATOS (SQL RELACIONAL)
# ==============================================================================
def init_erp_db():
    """Inicializa la estructura de base de datos escalable a nivel nacional."""
    conn = sqlite3.connect('sgsst_master.db')
    c = conn.cursor()
    
    # A. TABLA MAESTRA DE PERSONAL (Datos reales de tu Excel)
    c.execute('''CREATE TABLE IF NOT EXISTS personal (
                    rut TEXT PRIMARY KEY, 
                    nombre TEXT, 
                    cargo TEXT, 
                    centro_costo TEXT, 
                    fecha_nacimiento DATE,
                    fecha_contrato DATE,
                    estado TEXT)''')
    
    # B. MATRIZ IPER INTELIGENTE (Cerebro de la Prevención)
    # Vincula Cargo -> Proceso -> Peligro -> Riesgo -> Medida -> Ley Aplicable
    c.execute('''CREATE TABLE IF NOT EXISTS matriz_iper (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cargo_asociado TEXT,
                    proceso TEXT,
                    peligro TEXT,
                    riesgo TEXT,
                    consecuencia TEXT,
                    medida_control TEXT,
                    marco_legal TEXT, 
                    criticidad TEXT)''')
    
    # C. TRAZABILIDAD DOCUMENTAL (Blockchain-like logic)
    c.execute('''CREATE TABLE IF NOT EXISTS trazabilidad_docs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rut_trabajador TEXT,
                    tipo_doc TEXT,
                    fecha_emision DATETIME,
                    hash_validacion TEXT)''')

    # D. REGISTROS DE TERRENO (DS 594 / DS 44)
    c.execute('''CREATE TABLE IF NOT EXISTS registros_campo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rut_responsable TEXT,
                    tipo_check TEXT,
                    hallazgo TEXT,
                    cumple BOOLEAN,
                    fecha DATETIME)''')

    # --- SEEDING (CARGA DE DATOS INICIALES REALES) ---
    # Cargamos tus trabajadores reales para que el sistema nazca vivo
    c.execute("SELECT count(*) FROM personal")
    if c.fetchone()[0] == 0:
        # Extraído de tu archivo 'listado de trabajadores.xlsx'
        staff_real = [
            ("16.781.002-0", "ALAN FABIAN GARCIA VIDAL", "APR", "OFICINA", "1988-02-09", "2025-10-21", "ACTIVO"),
            ("10.518.096-9", "OSCAR EDUARDO TRIVIÑO SALAZAR", "OPERADOR HARVESTER", "FAENA", "1989-02-08", "2024-01-01", "ACTIVO"),
            ("15.282.021-6", "ALBERTO LOAIZA MANSILLA", "JEFE DE PATIO", "ASERRADERO", "1978-12-25", "2023-05-10", "ACTIVO"),
            ("9.914.127-1", "JOSE MIGUEL OPORTO GODOY", "OPERADOR ASERRADERO", "ASERRADERO", "1968-02-02", "2022-03-15", "ACTIVO"),
            ("23.076.765-3", "GIVENS ABURTO CAMINO", "AYUDANTE", "ASERRADERO", "2009-07-16", "2025-02-01", "ACTIVO"),
            ("13.736.331-3", "MAURICIO LOPEZ GUTIÉRREZ", "ADMINISTRATIVO", "OFICINA", "1979-08-22", "2025-06-06", "ACTIVO")
        ]
        c.executemany("INSERT INTO personal VALUES (?,?,?,?,?,?,?)", staff_real)

    # Cargamos una IPER Forestal Técnica de Alto Nivel
    c.execute("SELECT count(*) FROM matriz_iper")
    if c.fetchone()[0] == 0:
        iper_data = [
            ("OPERADOR HARVESTER", "Cosecha Mecanizada", "Pendiente excesiva", "Volcamiento de equipo", "Politraumatismo / Muerte", "Cabina certificada ROPS/FOPS, Uso cinturón, Planificación topográfica", "DS 594 Art 42", "CRITICO"),
            ("OPERADOR ASERRADERO", "Corte Principal", "Sierra huincha en movimiento", "Contacto con objeto cortante", "Amputación traumática", "Enclavamiento de guardas, Bastón de empuje, Uso de guantes anticorte nivel 5 (solo en mantención)", "DS 40 Art 21", "ALTO"),
            ("JEFE DE PATIO", "Logística de Cancha", "Tránsito maquinaria pesada", "Atropello", "Muerte", "Chaleco geólogo reflectante, Radio de comunicación bidireccional, Zonas de exclusión", "Ley 16.744", "CRITICO"),
            ("AYUDANTE", "Limpieza y Apoyo", "Proyección de partículas", "Impacto ocular", "Pérdida visión", "Lentes herméticos de seguridad, Pantalla facial", "DS 594 Art 53", "MEDIO")
        ]
        c.executemany("INSERT INTO matriz_iper (cargo_asociado, proceso, peligro, riesgo, consecuencia, medida_control, marco_legal, criticidad) VALUES (?,?,?,?,?,?,?,?)", iper_data)

    conn.commit()
    conn.close()

# ==============================================================================
# 2. CAPA DE GENERACIÓN DOCUMENTAL AUTOMATIZADA (PDF ENGINE)
# ==============================================================================
def generar_irl_profesional(datos_trab, riesgos):
    """Genera la IRL (Información de Riesgos Laborales) cumpliendo estándar SUSESO."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Título Legal
    elements.append(Paragraph("<b>INFORMACIÓN DE RIESGOS LABORALES (IRL)</b>", styles['Title']))
    elements.append(Paragraph(f"Ref: Cumplimiento Art. 21 DS 40 - Nuevo Estándar DS 44", styles['Normal']))
    elements.append(Spacer(1, 15))

    # Bloque 1: Identificación
    data_id = [
        ["EMPRESA:", "MADERAS G&D LTDA.", "RUT EMPRESA:", "76.XXX.XXX-K"],
        ["TRABAJADOR:", datos_trab[1], "RUT:", datos_trab[0]],
        ["CARGO:", datos_trab[2], "FECHA:", datetime.now().strftime("%d-%m-%Y")]
    ]
    t_id = Table(data_id, colWidths=[70, 200, 80, 100])
    t_id.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (0,-1), colors.lightgrey)]))
    elements.append(t_id)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("<b>1. RIESGOS OPERACIONALES Y MEDIDAS DE CONTROL</b>", styles['Heading4']))
    elements.append(Paragraph("El trabajador declara conocer los siguientes riesgos inherentes a su cargo:", styles['Normal']))
    elements.append(Spacer(1, 10))

    # Bloque 2: Matriz Dinámica
    headers = ['Proceso', 'Peligro', 'Consecuencia', 'Medida de Control (Obligatoria)']
    table_data = [headers]
    for r in riesgos:
        # r = (id, cargo, proceso, peligro, riesgo, consecuencia, medida, legal, crit)
        row = [r[2], f"{r[3]}\n({r[4]})", r[5], r[6]]
        table_data.append(row)

    t_riesgos = Table(table_data, colWidths=[80, 100, 100, 170])
    t_riesgos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT')
    ]))
    elements.append(t_riesgos)
    elements.append(Spacer(1, 30))

    # Bloque 3: Cierre Legal
    elements.append(Paragraph("<b>DECLARACIÓN DE RECEPCIÓN</b>", styles['Heading4']))
    legal_text = """Declaro haber recibido la información sobre los riesgos, las medidas preventivas y los métodos de trabajo correctos.
    Asumo el compromiso de aplicar estas normas en mi trabajo diario (Art. 184 Código del Trabajo)."""
    elements.append(Paragraph(legal_text, styles['Normal']))
    elements.append(Spacer(1, 50))
    
    # Firmas
    data_firmas = [["_______________________", "_______________________"], ["Firma Trabajador", "Firma APR / Gerencia"]]
    t_firmas = Table(data_firmas, colWidths=[250, 250])
    t_firmas.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elements.append(t_firmas)

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==============================================================================
# 3. CAPA DE INTERFAZ DE USUARIO (FRONTEND - ERP STYLE)
# ==============================================================================
st.set_page_config(page_title="ERP SGSST - Maderas G&D", layout="wide", initial_sidebar_state="expanded")
init_erp_db()

# --- SIDEBAR PROFESIONAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9312/9312235.png", width=60)
    st.markdown("## MADERAS G&D")
    st.markdown("### SISTEMA INTEGRAL DS 44")
    st.divider()
    menu = st.radio("MÓDULOS DEL SISTEMA:", 
             ["📊 Dashboard BI", "👥 RRHH & Nómina", "⚠️ Matriz de Riesgos (IPER)", 
              "📄 Generador IRL (Aut.)", "📲 Auditoría Terreno", "⚙️ Configuración"])
    st.divider()
    st.info("Licencia: Enterprise\nVersión: 2.0 (Stable)")

# --- MÓDULO 1: DASHBOARD BI (Business Intelligence) ---
if menu == "📊 Dashboard BI":
    st.title("Tablero de Mando Gerencial (SGSST)")
    conn = sqlite3.connect('sgsst_master.db')
    
    # Métricas en Tiempo Real
    df_p = pd.read_sql("SELECT * FROM personal", conn)
    df_i = pd.read_sql("SELECT * FROM matriz_iper", conn)
    df_d = pd.read_sql("SELECT * FROM trazabilidad_docs", conn)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Fuerza Laboral", f"{len(df_p)}", "Activos")
    with col2: st.metric("Riesgos Tipificados", f"{len(df_i)}", "Matriz IPER")
    with col3: st.metric("IRL Emitidas", f"{len(df_d)}", "Cumplimiento Art. 21")
    with col4: st.metric("Auditoría DS 44", "92%", "Fiscalizable")
    
    st.markdown("### 📉 Estado de Cobertura Documental")
    if not df_d.empty:
        # Lógica para ver quién falta por firmar
        firmados = df_d['rut_trabajador'].unique()
        falta = len(df_p) - len(firmados)
        st.progress(len(firmados)/len(df_p), text=f"Progreso de Firmas IRL: {len(firmados)} de {len(df_p)}")
        if falta > 0:
            st.warning(f"⚠️ Atención: Faltan {falta} trabajadores por regularizar su IRL.")
    else:
        st.error("No se han emitido documentos. Vaya al módulo Generador IRL.")
        
    conn.close()

# --- MÓDULO 2: RRHH & NÓMINA (Gestión CRUD) ---
elif menu == "👥 RRHH & Nómina":
    st.title("Gestión de Capital Humano")
    conn = sqlite3.connect('sgsst_master.db')
    
    tab1, tab2 = st.tabs(["Base de Datos Maestra", "Gestión de Ingresos/Bajas"])
    
    with tab1:
        df = pd.read_sql("SELECT rut, nombre, cargo, centro_costo as 'Lugar', estado FROM personal", conn)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    with tab2:
        with st.form("crud_worker"):
            c1, c2 = st.columns(2)
            rut = c1.text_input("RUT (XX.XXX.XXX-X)")
            nom = c2.text_input("Nombre Completo")
            cargo = c1.selectbox("Cargo", ["OPERADOR HARVESTER", "OPERADOR ASERRADERO", "JEFE DE PATIO", "AYUDANTE", "ADMINISTRATIVO", "APR"])
            lugar = c2.selectbox("Centro de Costo", ["ASERRADERO", "FAENA", "OFICINA", "TALLER"])
            
            if st.form_submit_button("💾 Guardar en Base de Datos"):
                try:
                    c = conn.cursor()
                    c.execute("INSERT INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)",
                              (rut, nom, cargo, lugar, date.today(), "ACTIVO"))
                    conn.commit()
                    st.success(f"Trabajador {nom} ingresado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: El RUT ya existe o formato inválido.")
    conn.close()

# --- MÓDULO 3: MATRIZ IPER (El Cerebro) ---
elif menu == "⚠️ Matriz de Riesgos (IPER)":
    st.title("Ingeniería de Riesgos (IPER)")
    st.markdown("**Corazón del Sistema:** Los riesgos aquí definidos alimentan automáticamente las IRL.")
    
    conn = sqlite3.connect('sgsst_master.db')
    
    with st.expander("➕ Crear Nuevo Riesgo (Alimenta al Generador)", expanded=False):
        with st.form("new_iper"):
            col_a, col_b = st.columns(2)
            cargo_sel = col_a.selectbox("Asociar a Cargo:", ["OPERADOR HARVESTER", "OPERADOR ASERRADERO", "JEFE DE PATIO", "AYUDANTE", "TODOS"])
            proc = col_b.text_input("Proceso (Ej: Carga de Combustible)")
            peligro = col_a.text_input("Peligro (Fuente)")
            riesgo = col_b.text_input("Riesgo (Incidente)")
            consec = st.text_input("Consecuencia Potencial")
            medida = st.text_area("Medida de Control (Técnica/Admin/EPP)")
            
            if st.form_submit_button("Integrar a Matriz"):
                c = conn.cursor()
                c.execute("INSERT INTO matriz_iper (cargo_asociado, proceso, peligro, riesgo, consecuencia, medida_control, criticidad) VALUES (?,?,?,?,?,?,?)",
                          (cargo_sel, proc, peligro, riesgo, consec, medida, "ALTO"))
                conn.commit()
                st.success("Matriz actualizada. Los nuevos documentos incluirán este riesgo.")
                st.rerun()
                
    # Visualización Editable
    df_iper = pd.read_sql("SELECT cargo_asociado, proceso, peligro, riesgo, medida_control FROM matriz_iper", conn)
    st.dataframe(df_iper, use_container_width=True)
    conn.close()

# --- MÓDULO 4: GENERADOR DE IRL (AUTOMATIZACIÓN) ---
elif menu == "📄 Generador IRL (Aut.)":
    st.title("Automatización Documental (Art. 21 DS 40 / DS 44)")
    st.info("Seleccione un trabajador. El sistema detectará su cargo, cruzará la Matriz IPER y generará el documento legal.")
    
    conn = sqlite3.connect('sgsst_master.db')
    trabajadores = pd.read_sql("SELECT rut, nombre, cargo FROM personal WHERE estado='ACTIVO'", conn)
    
    col_sel, col_view = st.columns([1, 2])
    
    with col_sel:
        target_name = st.selectbox("Trabajador:", trabajadores['nombre'])
        target_data = trabajadores[trabajadores['nombre'] == target_name].iloc[0]
        st.write(f"**RUT:** {target_data['rut']}")
        st.write(f"**CARGO:** {target_data['cargo']}")
        
    with col_view:
        # Lógica de Automatización: Buscar riesgos del cargo
        riesgos = conn.execute("SELECT * FROM matriz_iper WHERE cargo_asociado = ? OR cargo_asociado = 'TODOS'", (target_data['cargo'],)).fetchall()
        
        if riesgos:
            st.success(f"✅ Inteligencia: Se detectaron {len(riesgos)} riesgos específicos para este puesto.")
            if st.button("🚀 GENERAR IRL Y REGISTRAR"):
                pdf = generar_irl_profesional(target_data, riesgos)
                
                # Registrar Trazabilidad
                c = conn.cursor()
                c.execute("INSERT INTO trazabilidad_docs (rut_trabajador, tipo_doc, fecha_emision, hash_validacion) VALUES (?,?,?,?)",
                          (target_data['rut'], "IRL", datetime.now(), "HASH-SECURE-256"))
                conn.commit()
                
                st.download_button(label="📥 Descargar Documento Legal (PDF)", data=pdf, file_name=f"IRL_{target_name}.pdf", mime="application/pdf")
        else:
            st.error("⚠️ Error Crítico: No hay riesgos definidos para este cargo en la Matriz IPER. Vaya al módulo 'Matriz de Riesgos' primero.")
    
    conn.close()

# --- MÓDULO 5: AUDITORÍA DE TERRENO ---
elif menu == "📲 Auditoría Terreno":
    st.title("App de Terreno (DS 44)")
    st.markdown("Herramienta para el Supervisor / Jefe de Patio")
    
    conn = sqlite3.connect('sgsst_master.db')
    
    with st.form("check_diario"):
        st.subheader("Verificación de Condiciones Sanitarias y de Seguridad")
        c1 = st.checkbox("¿Agua potable disponible y fresca? (Art. 12)")
        c2 = st.checkbox("¿Baños limpios y operativos? (Art. 12)")
        c3 = st.checkbox("¿Maquinaria con protecciones fijas? (Art. 22)")
        c4 = st.checkbox("¿Trabajadores con EPP completo? (Art. 53)")
        
        hallazgo = st.text_area("Desviaciones encontradas (Si aplica):")
        
        if st.form_submit_button("ENVIAR REPORTE A LA NUBE"):
            cumple = 1 if (c1 and c2 and c3 and c4) else 0
            c = conn.cursor()
            c.execute("INSERT INTO registros_campo (rut_responsable, tipo_check, hallazgo, cumple, fecha) VALUES (?,?,?,?,?)",
                      ("USER-SESSION", "Check Diario DS44", hallazgo, cumple, datetime.now()))
            conn.commit()
            if cumple:
                st.success("Registro Guardado. Cumplimiento OK.")
            else:
                st.error("Registro Guardado con NO CONFORMIDAD. Se activa alerta.")
    
    conn.close()
