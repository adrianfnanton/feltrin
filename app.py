import pandas as pd
import re

# --- CONFIGURACIÓN ---
archivo_proveedor = 'Lista GSG 62.xlsx' 
archivo_mis_skus = 'skus.xlsx'
# ---------------------

print("⏳ Procesando... Limpiando precios y cruzando datos...")

try:
    xls_proveedor = pd.read_excel(archivo_proveedor, sheet_name=None, header=None)
except FileNotFoundError:
    print("❌ ERROR: No encuentro los archivos. Súbelos al panel izquierdo.")
    xls_proveedor = {}

base_datos = []

# Función para convertir "$ 1.500,00" a numero 1500.00
def limpiar_precio(valor):
    if pd.isna(valor) or str(valor).strip() in ["-", "", "nan"]:
        return None
    
    # Convertimos a texto
    s = str(valor).strip()
    
    # Quitamos el signo $ y espacios
    s = s.replace('$', '').replace(' ', '')
    
    try:
        # Formato Argentino: 1.000,50 -> Quitamos punto de mil, cambiamos coma por punto
        if ',' in s and '.' in s: # Caso completo: 1.500,50
             s = s.replace('.', '').replace(',', '.')
        elif ',' in s: # Caso decimal simple: 50,50
             s = s.replace(',', '.')
        elif '.' in s and len(s.split('.')[-1]) == 3: # Caso mil sin decimal: 1.000
             s = s.replace('.', '')
        
        return float(s)
    except:
        return valor # Si dice "Consultar" u otra cosa, lo devolvemos tal cual

if xls_proveedor:
    for nombre_hoja, df_raw in xls_proveedor.items():
        # 1. Buscar encabezado
        fila_header = -1
        for i, row in df_raw.head(20).iterrows():
            row_str = row.astype(str).str.upper()
            if row_str.str.contains("CODIGO").any():
                fila_header = i
                break
        
        if fila_header != -1:
            # 2. Preparar hoja
            df_hoja = df_raw.iloc[fila_header+1:].copy()
            df_hoja.columns = df_raw.iloc[fila_header]
            
            col_sku = None
            col_precio = None
            
            for col in df_hoja.columns:
                col_upper = str(col).upper()
                if "CODIGO" in col_upper: col_sku = col
                if "PRECIO" in col_upper:
                    if col_precio is None: col_precio = col
                    elif "<" in col_upper: col_precio = col
            
            if col_sku and col_precio:
                # --- LÓGICA DE COLA ---
                cola_precios = []
                ultimo_precio_valido = None
                
                for idx, row in df_hoja.iterrows():
                    raw_sku = str(row[col_sku])
                    # Obtenemos el valor crudo del precio
                    raw_precio = str(row[col_precio]) if pd.notna(row[col_precio]) else ""
                    
                    skus_en_celda = [s.strip().split()[0] for s in raw_sku.split('\n') if s.strip()]
                    precios_en_celda = [p.strip() for p in raw_precio.split('\n') if p.strip()]
                    
                    # Rellenamos la cola si hay precios nuevos
                    if precios_en_celda:
                        cola_precios = list(precios_en_celda)
                        ultimo_precio_valido = precios_en_celda[-1] 
                    
                    for s in skus_en_celda:
                        if len(s) > 3:
                            precio_str = "-"
                            
                            if len(cola_precios) > 0:
                                precio_str = cola_precios.pop(0)
                            elif ultimo_precio_valido:
                                precio_str = ultimo_precio_valido
                            
                            # AQUI LA LIMPIEZA
                            precio_num = limpiar_precio(precio_str)
                            
                            base_datos.append({
                                'sku': s, 
                                'hoja': nombre_hoja, 
                                'precio': precio_num
                            })

print(f"✅ Se procesaron {len(base_datos)} productos correctamente.")

# --- CRUCE ---
print("🚀 Cruzando datos...")
df_mis_skus = pd.read_excel(archivo_mis_skus)
mis_codigos = df_mis_skus.iloc[:, 0].dropna().astype(str).tolist()

resultados = []
patrones_db = [item for item in base_datos if 'X' in item['sku'].upper()]

def es_compatible(buscado, base):
    if len(buscado) != len(base): return False
    for cb, cbase in zip(buscado, base):
        if cbase == 'X': continue
        if cb != cbase: return False
    return True

for buscado in mis_codigos:
    buscado_clean = buscado.strip()
    buscado_upper = buscado_clean.upper()
    encontrado = False
    
    # 1. Exacto
    for item in base_datos:
        if item['sku'].upper() == buscado_upper:
            resultados.append({
                'Mi SKU': buscado_clean,
                'Encontrado en': item['hoja'],
                'SKU Lista': item['sku'],
                'Precio': item['precio'], # Ya es número
                'Tipo': 'Exacto'
            })
            encontrado = True
            break
    
    # 2. Patrón
    if not encontrado:
        for item in patrones_db:
            if es_compatible(buscado_upper, item['sku'].upper()):
                resultados.append({
                    'Mi SKU': buscado_clean,
                    'Encontrado en': item['hoja'],
                    'SKU Lista': item['sku'],
                    'Precio': item['precio'], # Ya es número
                    'Tipo': 'Patrón'
                })
                encontrado = True
                break
    
    if not encontrado:
        resultados.append({'Mi SKU': buscado_clean, 'Encontrado en': '-', 'Precio': 0, 'Tipo': '-'})

df_final = pd.DataFrame(resultados)
df_final.to_excel('resultado_numerico_final.xlsx', index=False)
print("🎉 ¡Listo! Ahora sí puedes sumar la columna 'Precio' en el archivo: resultado_numerico_final.xlsx")
