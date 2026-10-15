import pandas as pd

# CONSTANTES DEL CONDUCTOR (Basadas en el sistema de Garver 1970)
REACTANCIA_POR_MILLA = 0.01  # pu por cada milla
COSTO_POR_MILLA = 5.0        # Unidades monetarias por cada milla

# 1. Datos de los Nodos (Inyección Neta suma 0)
nodos_data = {
    'Nodo': [1, 2, 3, 4, 5, 6, 7, 8],
    'es_referencia': [1, 0, 0, 0, 0, 0, 0, 0],
    'PG_MW': [100, 0, 200, 0, 0, 300, 0, 150],
    'PL_MW': [50, 150, 50, 100, 120, 0, 130, 150],
    'Inyeccion_Neta_pu': [0.5, -1.5, 1.5, -1.0, -1.2, 3.0, -1.3, 0.0] 
}

# 2. Datos de las Líneas Existentes (Definimos solo la distancia física)
lineas_ex_data = {
    'Origen': [1, 1, 2, 3, 4, 5, 6, 7],
    'Destino': [2, 3, 4, 4, 5, 6, 7, 8],
    'Distancia_millas': [20, 40, 20, 30, 20, 20, 30, 20],
    'Capacidad_pu': [1.0, 1.0, 1.0, 1.0, 1.5, 2.0, 1.5, 1.0]
}

# 3. Datos de los Corredores Candidatos (Definimos solo la distancia física)
corredores_cand_data = {
    'Origen': [1, 2, 3, 4, 5],
    'Destino': [4, 5, 6, 7, 8],
    'Distancia_millas': [40, 30, 50, 40, 30],
    'N_Max': [2, 3, 2, 2, 3],
    'Capacidad_pu': [1.0, 1.5, 2.0, 1.5, 1.5]
}

# Crear DataFrames iniciales
df_nodos = pd.DataFrame(nodos_data)
df_lineas = pd.DataFrame(lineas_ex_data)
df_corredores = pd.DataFrame(corredores_cand_data)

# =========================================================
# ⚙️ CÁLCULOS AUTOMÁTICOS BASADOS EN LA DISTANCIA
# =========================================================

# Para las líneas existentes (solo calculamos reactancia)
df_lineas['Reactancia_pu'] = df_lineas['Distancia_millas'] * REACTANCIA_POR_MILLA

# Para los corredores candidatos (calculamos reactancia y costo)
df_corredores['Reactancia_pu'] = df_corredores['Distancia_millas'] * REACTANCIA_POR_MILLA
df_corredores['Costo_Inversion'] = df_corredores['Distancia_millas'] * COSTO_POR_MILLA

# Ordenar las columnas para que el Excel quede bien estructurado
cols_lineas = ['Origen', 'Destino', 'Distancia_millas', 'Reactancia_pu', 'Capacidad_pu']
df_lineas = df_lineas[cols_lineas]

cols_corredores = ['Origen', 'Destino', 'Distancia_millas', 'Reactancia_pu', 'Capacidad_pu', 'Costo_Inversion', 'N_Max']
df_corredores = df_corredores[cols_corredores]

# 4. Exportar al archivo de Excel
nombre_archivo = 'sistema_8_barras_escalable.xlsx'
with pd.ExcelWriter(nombre_archivo) as writer:
    df_nodos.to_excel(writer, sheet_name='Nodos', index=False)
    df_lineas.to_excel(writer, sheet_name='Lineas_Existentes', index=False)
    df_corredores.to_excel(writer, sheet_name='Corredores_Candidatos', index=False)

print(f"✅ Archivo '{nombre_archivo}' generado con éxito.")
print("La Reactancia (pu) y el Costo de Inversión han sido calculados en función de la distancia.")