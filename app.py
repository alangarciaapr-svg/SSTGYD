# --- 2. GESTIÓN NÓMINA ---
elif menu == "👥 Nómina (Base Excel)":
    st.title("Base de Datos Maestra de Personal")
    st.markdown("Datos cargados desde 'listado de trabajadores.xlsx'.")
    
    conn = sqlite3.connect('sgsst_master.db')
    
    # --- BOTÓN DE PLANTILLA CON INSTRUCCIONES DETALLADAS ---
    col_plantilla, col_upload = st.columns([1, 2])
    with col_plantilla:
        st.info("¿Necesitas el formato?")
        
        def generar_plantilla_excel_detallada():
            output = io.BytesIO()
            
            # 1. Definimos datos de ejemplo que sirven de guía visual
            data = {
                'NOMBRE': ['JUAN PEREZ (EJEMPLO)', 'MARIA SOTO (EJEMPLO)'],
                'RUT': ['11.222.333-K', '12.345.678-9'],  # Formato correcto
                'CARGO': ['OPERADOR ASERRADERO', 'AYUDANTE'],
                'LUGAR DE TRABAJO': ['ASERRADERO', 'FAENA'], # Lugares válidos
                'F. CONTRATO': ['2025-01-01', '01-03-2024'], # Formatos de fecha
                'DIRECCION': ['CALLE 1, OSORNO', 'AVENIDA 2'],
                'ESTADO CIVIL': ['SOLTERO', 'CASADA'],
                'SALUD': ['FONASA', 'ISAPRE'],
                'AFP': ['MODELO', 'CAPITAL'],
                'CORREO': ['ejemplo@gyd.cl', ''],
                'TELEFONO': ['912345678', '']
            }
            df_template = pd.DataFrame(data)
            
            # 2. Escribimos el Excel usando las 2 primeras filas para instrucciones
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # FILA 1: Título de advertencia
                instruccion_1 = pd.DataFrame(["GUÍA DE FORMATO OBLIGATORIO - LEA ANTES DE LLENAR - LOS DATOS COMIENZAN EN LA FILA 4"])
                instruccion_1.to_excel(writer, startrow=0, startcol=0, index=False, header=False)
                
                # FILA 2: Instrucciones técnicas específicas
                instruccion_2 = pd.DataFrame(["RUT: Con puntos y guion (Ej: 11.222.333-K) | FECHAS: DD-MM-AAAA o AAAA-MM-DD | LUGAR: Use solo 'ASERRADERO', 'FAENA', 'OFICINA' | NO BORRAR ENCABEZADOS DE LA FILA 3"])
                instruccion_2.to_excel(writer, startrow=1, startcol=0, index=False, header=False)
                
                # FILA 3: Los encabezados reales (que lee el sistema)
                # FILA 4+: Los datos de ejemplo
                df_template.to_excel(writer, startrow=2, index=False, sheet_name='Plantilla')
                
                # Ajuste visual (auto-ancho simulado para columnas críticas)
                workbook = writer.book
                worksheet = writer.sheets['Plantilla']
                worksheet.column_dimensions['A'].width = 30 # Nombre
                worksheet.column_dimensions['B'].width = 15 # Rut
                worksheet.column_dimensions['D'].width = 20 # Lugar
                
            return output.getvalue()

        plantilla_data = generar_plantilla_excel_detallada()
        
        st.download_button(
            label="📥 Bajar Plantilla Instructiva", 
            data=plantilla_data, 
            file_name="plantilla_carga_nomina_v2.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # --- CARGA DEL ARCHIVO (Lógica intacta) ---
    uploaded_file = st.file_uploader("📂 Actualizar Nómina (Subir Excel Completo)", type=['xlsx', 'csv'])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'): 
                df_new = pd.read_csv(uploaded_file, header=2) # Lee desde fila 3
            else: 
                df_new = pd.read_excel(uploaded_file, header=2) # Lee desde fila 3
            
            df_new.columns = df_new.columns.str.strip().str.upper()
            
            if 'RUT' in df_new.columns and 'NOMBRE' in df_new.columns:
                c = conn.cursor()
                count = 0
                for index, row in df_new.iterrows():
                    rut = str(row['RUT']).strip()
                    nombre = str(row['NOMBRE']).strip()
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
                st.error("Error: El archivo no contiene las columnas RUT y NOMBRE en la fila 3 (recuerde no borrar los encabezados).")
        except Exception as e:
            st.error(f"Error técnico: {e}")

    df = pd.read_sql("SELECT * FROM personal", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()
