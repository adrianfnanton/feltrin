import streamlit as st
import pandas as pd
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Buscador GSG", page_icon="🔎")

st.title("🔎 Buscador de Precios GSG")
st.markdown("""
Esta herramienta cruza tu lista de SKUs con la lista de precios del proveedor (40 hojas).
**Instrucciones:**
1. Sube la lista de precios (Excel).
2. Sube tu archivo de SKUs.
3. Descarga el resultado.
""")

# --- BOTONES DE CARGA ---
archivo_proveedor = st.file_uploader("1. Sube la Lista de Precios (Excel con 40 hojas)", type=['xlsx'])
archivo_skus = st.file_uploader("2. Sube tu lista de SKUs a buscar", type=['xlsx', 'csv'])

# --- FUNCIÓN DE LIMPIEZA DE PRECIOS ---
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

# --- BOTÓN DE PROCESAR ---
if st.button("🚀 Procesar Archivos"):
    if archivo_proveedor and archivo_skus:
        with st.spinner('⏳ Leyendo archivos... por favor espera...'):
            try:
                # 1. LEER ARCHIVO DEL PROVEEDOR
                # Usamos engine='openpyxl' explícitamente para Streamlit
                xls_proveedor = pd.read_excel(archivo_proveedor, sheet_name=None, header=None, engine='openpyxl')
                
                # 2. LEER MIS SKUS
                # Rebobinamos el archivo por seguridad
                archivo_skus.seek(0)
                if archivo_skus.name.lower().endswith('.csv'):
                    df_mis_skus = pd.read_csv(archivo_skus)
                else:
                    df_mis_skus = pd.read_excel(archivo_skus, engine='openpyxl')
                
                # Asumimos que los códigos están en la primera columna
                mis_codigos = df_mis_skus.iloc[:, 0].dropna().astype(str).tolist()

                # 3. CREAR BASE DE DATOS (Mismo motor que en Colab)
                base_datos = []
                
                # Barra de progreso para dar feedback visual
                progreso_texto = st.empty()
                progreso_texto.text("Analizando las 40 hojas del proveedor...")
                
                for nombre_hoja, df_raw in xls_proveedor.items():
                    # Buscar encabezado
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

                st.success(f"✅ Base de datos cargada con {len(base_datos)} productos.")

                # 4. CRUCE DE DATOS
                progreso_texto.text("Cruzando con tus SKUs...")
                resultados = []
                # Pre-filtramos los patrones para que sea más rápido
                patrones_db = [x for x in base_datos if 'X' in str(x['sku']).upper()]

                def es_compatible(buscado, base):
                    if len(buscado) != len(base): return False
                    for cb, cbase in zip(buscado, base):
                        if cbase == 'X': continue
                        if cb != cbase: return False
                    return True

                # Barra de carga visual
                bar = st.progress(0)
                total = len(mis_codigos)
                
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
                    
                    # Actualizar barra cada 5 items para no alentar
                    if i % 5 == 0:
                        bar.progress(min((i + 1) / total, 1.0))
                
                bar.progress(100)
                progreso_texto.empty()

                # 5. DESCARGAR RESULTADO
                df_final = pd.DataFrame(resultados)
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_final.to_excel(writer, index=False)
                
                st.balloons() # ¡Efecto de celebración!
                st.success("¡Proceso Terminado! Descarga tu archivo aquí abajo:")
                
                st.download_button(
                    label="📥 Descargar Resultado Excel",
                    data=buffer,
                    file_name="resultado_precios_final.xlsx",
                    mime="application/vnd.ms-excel"
                )

            except Exception as e:
                st.error(f"Ocurrió un error: {e}")
                st.info("Tip: Verifica que el archivo de precios sea el Excel correcto y que tu lista de SKUs tenga los códigos en la primera columna.")
    else:
        st.warning("⚠️ Por favor carga AMBOS archivos antes de presionar el botón.")
