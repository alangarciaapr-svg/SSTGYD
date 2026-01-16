# --- 2. GESTIÓN NÓMINA ---
elif menu == "👥 Nómina (Base Excel)":
    st.title("Base de Datos Maestra de Personal")
    st.markdown("Gestión de trabajadores y carga masiva.")
    
    conn = sqlite3.connect('sgsst_master.db')

    # --- NUEVO: BOTÓN PARA DESCARGAR PLANTILLA DE EJEMPLO ---
    col_plantilla, col_upload = st.columns([1, 2])
    
    with col_plantilla:
        st.info("¿Necesitas el formato?")
        def generar_plantilla_excel():
            output = io.BytesIO()
            # Datos de ejemplo con la estructura exacta que lee tu código (header=2)
            data = {
                'NOMBRE': ['JUAN PEREZ EJEMPLO', 'MARIA GONZALEZ EJEMPLO'],
                'RUT': ['11.111.111-1', '22.222.222-2'],
                'FECHA NAC.': ['1990-01-01', '1995-05-05'], # Opcional pero útil
                'DIRECCION': ['CALLE FALSA 123', 'AVENIDA SIEMPRE VIVA'],
                'ESTADO CIVIL': ['SOLTERO', 'CASADA'],
                'SALUD': ['FONASA', 'ISAPRE'],
                'AFP': ['MODELO', 'PROVIDA'],
                'CARGO': ['AYUDANTE', 'OPERADOR ASERRADERO'],
                'CORREO': ['correo@ejemplo.com', 'otro@ejemplo.com'],
                'TELEFONO': ['912345678', '987654321'],
                'LUGAR DE TRABAJO': ['FAENA', 'ASERRADERO'], # Clave para el sistema
                'CONTRATO': ['INDEFINIDO', 'FIJO'],
                'F. CONTRATO': ['2025-01-01', '2024-03-15'], # Clave para alertas
                'ANTIGÜEDAD': ['', ''],
                'IRL': ['', ''],
                'RIOHS': ['', ''],
                'R. EPP': ['', ''],
                'LICENCIA CONDUCIR': ['', '']
            }
            df_template = pd.DataFrame(data)
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Escribimos filas vacías o títulos en las primeras 2 filas para respetar el header=2
                pd.DataFrame(["PLANTILLA DE CARGA MASIVA - NO BORRAR ESTAS 2 PRIMERAS FILAS"]).to_excel(writer, startrow=0, startcol=0, index=False, header=False)
                pd.DataFrame(["Complete los datos desde la fila 4"]).to_excel(writer, startrow=1, startcol=0, index=False, header=False)
                # Los encabezados reales quedan en la fila 3 (índice 2 de Excel)
                df_template.to_excel(writer, startrow=2, index=False, sheet_name='Plantilla')
            return output.getvalue()

        plantilla_data = generar_plantilla_excel()
        st.download_button(
            label="📥 Descargar Excel de Ejemplo",
            data=plantilla_data,
            file_name="plantilla_carga_nomina.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # --- CARGA DEL ARCHIVO (Mantenido igual) ---
    uploaded_file = st.file_uploader("📂 Subir Excel con Nómina Real", type=['xlsx', 'csv'])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'): 
                df_new = pd.read_csv(uploaded_file, header=2)
            else: 
                df_new = pd.read_excel(uploaded_file, header=2)
            
            df_new.columns = df_new.columns.str.strip().str.upper()
            
            # Buscamos columnas clave
            if 'RUT' in df_new.columns and 'NOMBRE' in df_new.columns:
                c = conn.cursor()
                count = 0
                for index, row in df_new.iterrows():
                    rut = str(row['RUT']).strip()
                    nombre = str(row['NOMBRE']).strip()
                    # Mapeo de columnas tolerante a fallos
                    cargo = str(row.get('CARGO', 'SIN CARGO')).strip()
                    lugar = str(row.get('LUGAR DE TRABAJO', 'FAENA')).strip()
                    
                    try: 
                        f_contrato = pd.to_datetime(row.get('F. CONTRATO', date.today())).date()
                    except: 
                        f_contrato = date.today()

                    if len(rut) > 5 and nombre.lower() != "nan":
                        c.execute("INSERT OR REPLACE INTO personal (rut, nombre, cargo, centro_costo, fecha_contrato, estado) VALUES (?,?,?,?,?,?)", 
                                  (rut, nombre, cargo, lugar, f_contrato, "ACTIVO"))
                        count += 1
                conn.commit()
                st.success(f"✅ Éxito: {count} trabajadores procesados/actualizados.")
                st.rerun()
            else:
                st.error("Error: El archivo no contiene las columnas RUT y NOMBRE en la fila 3.")
        except Exception as e:
            st.error(f"Error técnico: {e}")

    # Visualización tabla
    df = pd.read_sql("SELECT * FROM personal", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()
