import streamlit as st
import pandas as pd
import io

# Configuración de página
st.set_page_config(page_title="Buscador GSG", layout="wide")

st.title("🔎 Herramienta de Precios GSG")
st.markdown("---")

# --- SECCIÓN LATERAL DE CARGA ---
with st.sidebar:
    st.header("1. Cargar Archivos")
    st.write("Sube aquí tus archivos para empezar.")
    
    # Botones de carga
    archivo_proveedor = st.file_uploader("📂 Lista del Proveedor (Excel 40 hojas)", type=['xlsx'])
    archivo_skus = st.file_uploader("📂 Tu Lista de SKUs", type=['xlsx', 'csv'])
    
    boton_procesar = st.button("🚀 Procesar Ahora", type="primary")

# --- FUNCIÓN DE LIMPIEZA ---
def limpiar_precio(valor):
    if pd.isna(valor) or str(valor).strip() in ["-", "", "nan"]:
        return None
    s = str(valor).strip().replace('$', '').replace(' ', '')
    try:
        # Formato 1.000,00 -> 1000.00
        if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
        elif ',' in s: s = s.replace(',', '.')
        elif '.' in s and len(s.split('.')[-1]) == 3: s = s.replace('.', '')
        return float(s)
    except:
        return valor

# --- LÓGICA PRINCIPAL ---
if boton_procesar:
    if archivo_proveedor is not None and archivo_skus is not None:
        
        # Barra de progreso
        barra = st.progress(0)
        status = st.empty()
        
        try:
            # 1. LEER PROVEEDOR
            status.text("⏳ Leyendo el archivo gigante del proveedor (esto toma unos segundos)...")
            archivo_proveedor.seek(0)
            xls_proveedor = pd.read_excel(archivo_proveedor, sheet_name=None, header=None, engine='openpyxl')
            barra.progress(20)

            # 2. LEER SKUS
            status.text("⏳ Leyendo tus SKUs...")
            archivo_skus.seek(0)
            if archivo_skus.name.endswith('.csv'):
                df_mis_skus = pd.read_csv(archivo_skus)
            else:
                df_mis_skus = pd.read_excel(archivo_skus, engine='openpyxl')
            
            # Asumimos columna 0
            mis_codigos = df_mis_skus.iloc[:, 0].dropna().astype(str).tolist()
            barra.progress(30)

            # 3. CREAR BASE DE DATOS
            status.text("⚙️ Indexando las 40 hojas...")
            base_datos = []
            
            for nombre_hoja, df_raw in xls_proveedor.items():
                # Buscar encabezado dinámicamente
                fila_header = -1
                for i, row in df_raw.head(20).iterrows():
                    if row.astype(str).str.upper().str.contains("CODIGO").any():
                        fila_header = i
                        break
                
                if fila_header != -1:
                    df_hoja = df_raw.iloc[fila_header+1:].copy()
                    df_hoja.columns = df_raw.iloc[fila_header]
                    
                    col_sku = None
                    col_precio = None
                    for col in df_hoja.columns:
                        c_up = str(col).upper()
                        if "CODIGO" in c_up: col_sku = col
                        if "PRECIO" in c_up:
                            if col_precio is None or "<" in c_up: col_precio = col
                    
                    if col_sku and col_precio:
                        cola_precios = []
                        ultimo_precio = None
                        
                        for idx, row in df_hoja.iterrows():
                            raw_sku = str(row[col_sku])
                            raw_precio = str(row[col_precio]) if pd.notna(row[col_precio]) else ""
                            
                            skus_cell = [s.strip().split()[0] for s in raw_sku.split('\n') if s.strip()]
                            prices_cell = [p.strip() for p in raw_precio.split('\n') if p.strip()]
                            
                            if prices_cell:
                                cola_precios = list(prices_cell)
                                ultimo_precio = prices_cell[-1]
                            
                            for s in skus_cell:
                                if len(s) > 3:
                                    p_str = "-"
                                    if cola_precios: p_str = cola_precios.pop(0)
                                    elif ultimo_precio: p_str = ultimo_precio
                                    
                                    base_datos.append({
                                        'sku': s, 
                                        'hoja': nombre_hoja, 
                                        'precio': limpiar_precio(p_str)
                                    })
            
            barra.progress(60)
            status.text(f"✅ Base de datos lista ({len(base_datos)} productos). Cruzando información...")

            # 4. CRUCE
            resultados = []
            patrones_db = [x for x in base_datos if 'X' in str(x['sku']).upper()]

            def es_compatible(buscado, base):
                if len(buscado) != len(base): return False
                for cb, cbase in zip(buscado, base):
                    if cbase == 'X': continue
                    if cb != cbase: return False
                return True

            total_skus = len(mis_codigos)
            
            for i, buscado in enumerate(mis_codigos):
                buscado_clean = buscado.strip()
                buscado_upper = buscado_clean.upper()
                encontrado = False
                
                # Exacto
                for item in base_datos:
                    if str(item['sku']).upper() == buscado_upper:
                        resultados.append({'Mi SKU': buscado_clean, 'Encontrado en': item['hoja'], 'SKU Lista': item['sku'], 'Precio': item['precio'], 'Tipo': 'Exacto'})
                        encontrado = True
                        break
                # Patrón
                if not encontrado:
                    for item in patrones_db:
                        if es_compatible(buscado_upper, str(item['sku']).upper()):
                            resultados.append({'Mi SKU': buscado_clean, 'Encontrado en': item['hoja'], 'SKU Lista': item['sku'], 'Precio': item['precio'], 'Tipo': 'Patrón'})
                            encontrado = True
                            break
                if not encontrado:
                    resultados.append({'Mi SKU': buscado_clean, 'Encontrado en': '-', 'SKU Lista': '-', 'Precio': 0, 'Tipo': '-'})
                
                # Actualizar barra suavemente
                if i % 10 == 0:
                    progreso_actual = 60 + int((i / total_skus) * 40)
                    barra.progress(min(progreso_actual, 100))

            barra.progress(100)
            status.success("¡Proceso Terminado!")

            # 5. RESULTADO
            df_final = pd.DataFrame(resultados)
            
            # Métricas rápidas
            col1, col2, col3 = st.columns(3)
            col1.metric("SKUs Buscados", len(df_final))
            col2.metric("Encontrados", len(df_final[df_final['Tipo'] != '-']))
            col3.metric("No Encontrados", len(df_final[df_final['Tipo'] == '-']))

            # Descarga
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_final.to_excel(writer, index=False)
                
            st.download_button(
                label="📥 DESCARGAR RESULTADO FINAL",
                data=buffer,
                file_name="resultado_gsg_final.xlsx",
                mime="application/vnd.ms-excel",
                type="primary"
            )

        except Exception as e:
            st.error(f"Ocurrió un error: {e}")
            st.warning("Verifica que los archivos sean correctos.")
    else:
        st.error("⚠️ Faltan archivos. Por favor carga AMBOS archivos en la barra lateral izquierda.")
else:
    st.info("👈 Carga los archivos en el menú de la izquierda y presiona 'Procesar Ahora'")
