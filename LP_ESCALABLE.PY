import pandas as pd
import gurobipy as gp
from gurobipy import GRB

def resolver_lp_escalable_automatico(sistema_8_barras_escalable):
    print(f"Leyendo topología desde: {sistema_8_barras_escalable}...")
    
    # 1. CARGAR DATOS DESDE EXCEL
    df_nodos = pd.read_excel(sistema_8_barras_escalable, sheet_name='Nodos')
    df_lineas = pd.read_excel(sistema_8_barras_escalable, sheet_name='Lineas_Existentes')
    df_corredores = pd.read_excel(sistema_8_barras_escalable, sheet_name='Corredores_Candidatos')
    
    # 2. ESTRUCTURAR DATOS DINÁMICOS
    # Inyecciones Netas
    inyeccion = {int(row['Nodo']): row['Inyeccion_Neta_pu'] for _, row in df_nodos.iterrows()}
    
    # Nodo de Referencia
    ref_node_row = df_nodos[df_nodos['es_referencia'] == 1]
    ref_node = int(ref_node_row['Nodo'].iloc[0]) if not ref_node_row.empty else int(df_nodos['Nodo'].iloc[0])
    
    # Líneas Existentes (Lista dinámica para poder agregarle líneas iteración tras iteración)
    # Formato: (origen, destino, reactancia_pu, capacidad_pu)
    existing_lines = []
    for _, row in df_lineas.iterrows():
        existing_lines.append((int(row['Origen']), int(row['Destino']), row['Reactancia_pu'], row['Capacidad_pu']))
        
    # Corredores Candidatos
    # Llave: (origen, destino) -> Valor: (costo, x_pu, cap_pu, n_max)
    candidates = {}
    lineas_agregadas = {}
    for _, row in df_corredores.iterrows():
        i, j = int(row['Origen']), int(row['Destino'])
        candidates[(i, j)] = (row['Costo_Inversion'], row['Reactancia_pu'], row['Capacidad_pu'], int(row['N_Max']))
        lineas_agregadas[(i, j)] = 0
        
    iteracion = 1
    
    print("\n" + "="*50)
    print(" 🚀 INICIANDO ALGORITMO LP ITERATIVO ESCALABLE")
    print("="*50)

    # 3. BUCLE ITERATIVO PRINCIPAL
    while True:
        m = gp.Model(f"LP_Iter_{iteracion}")
        m.Params.OutputFlag = 0 # Silenciar salida del solver
        
        # Variables: Ángulos
        theta = {}
        for n in inyeccion.keys():
            theta[n] = m.addVar(lb=-GRB.INFINITY, ub=GRB.INFINITY, name=f"theta_{n}")
        m.addConstr(theta[ref_node] == 0, name="ref_angle")
        
        # Variables: Flujos en líneas existentes (reales, dependen de Kirchhoff)
        f_ex = {}
        for idx, (i, j, x, cap) in enumerate(existing_lines):
            f_ex[idx] = m.addVar(lb=-cap, ub=cap, name=f"fex_{idx}_{i}_{j}")
            m.addConstr(f_ex[idx] == (1/x) * (theta[i] - theta[j]), name=f"kirchhoff_{idx}")
            
        # Variables: Flujos ficticios de transporte (positivos y negativos)
        pd_plus = {}
        pd_minus = {}
        for (i, j) in candidates.keys():
            pd_plus[i, j] = m.addVar(lb=0, ub=GRB.INFINITY, name=f"pd_plus_{i}_{j}")
            pd_minus[i, j] = m.addVar(lb=0, ub=GRB.INFINITY, name=f"pd_minus_{i}_{j}")
            
        # Balance Nodal
        for n in inyeccion.keys():
            out_ex = gp.quicksum(f_ex[idx] for idx, (i, j, _, _) in enumerate(existing_lines) if i == n)
            in_ex = gp.quicksum(f_ex[idx] for idx, (i, j, _, _) in enumerate(existing_lines) if j == n)
            
            out_cand = gp.quicksum((pd_plus[i, j] - pd_minus[i, j]) for (i, j) in candidates.keys() if i == n)
            in_cand = gp.quicksum((pd_plus[i, j] - pd_minus[i, j]) for (i, j) in candidates.keys() if j == n)
            
            m.addConstr((out_ex + out_cand) - (in_ex + in_cand) == inyeccion[n], name=f"bal_{n}")
            
        # Función Objetivo: Minimizar el costo ficticio total
        obj = gp.quicksum(cost * (pd_plus[i, j] + pd_minus[i, j]) for (i, j), (cost, _, _, _) in candidates.items())
        m.setObjective(obj, GRB.MINIMIZE)
        
        # Resolver iteración
        m.optimize()
        
        # Verificación de infactibilidad 
        if m.status != GRB.OPTIMAL:
            print(f"\n❌ ITERACIÓN {iteracion}: El modelo se volvió infactible.")
            break
            
        # CONDICIÓN DE PARADA: Costo objetivo ~ 0 (No hay flujos ficticios)
        if m.ObjVal < 1e-4:
            print(f"\n✅ ITERACIÓN {iteracion}: ¡ÓPTIMO ALCANZADO!")
            print("Costo Ficticio = 0. La red actual soporta la demanda sin congestión.")
            break
            
        # Analizar resultados de la iteración actual
        print(f"\n--- ITERACIÓN {iteracion} ---")
        print(f"Costo Ficticio (Penalización): {m.ObjVal:.2f}")
        
        max_flow = -1
        max_corr = None
        
        for (i, j) in candidates.keys():
            flujo_neto = abs(pd_plus[i, j].X - pd_minus[i, j].X)
            if flujo_neto > 0.001:
                print(f"  ► Corredor candidato {i}-{j}: {flujo_neto:.2f} pu")
            
            if flujo_neto > max_flow:
                max_flow = flujo_neto
                max_corr = (i, j)
                
        # ACCIÓN: Agregar la línea más congestionada al sistema
        # Si hemos alcanzado el límite constructivo del corredor (N_Max), deberíamos detenernos o saltar a la siguiente.
        costo, x, cap, n_max = candidates[max_corr]
        
        if lineas_agregadas[max_corr] < n_max:
            existing_lines.append((max_corr[0], max_corr[1], x, cap))
            lineas_agregadas[max_corr] += 1
            print(f"⚡ ACCIÓN: Construyendo 1 línea en corredor {max_corr[0]}-{max_corr[1]} (Flujo detectado: {max_flow:.2f} pu)")
        else:
            print(f"⚠️ ALERTA: El corredor {max_corr[0]}-{max_corr[1]} requiere refuerzo, pero ya alcanzó su límite máximo de líneas ({n_max}).")
            print("El algoritmo interactivo no puede solucionar la congestión bajo estas restricciones constructivas.")
            break
            
        iteracion += 1

    # 4. RESUMEN FINAL
    print("\n" + "="*50)
    print(" 🏆 PLAN DE EXPANSIÓN FINAL (MÉTODO LP ESCALABLE)")
    print("="*50)
    
    costo_total_real = 0
    for (i, j), (costo, _, _, _) in candidates.items():
        num_lineas = lineas_agregadas[(i, j)]
        if num_lineas > 0:
            print(f"📍 Corredor {i}-{j}: {num_lineas} nueva(s) línea(s)")
            costo_total_real += num_lineas * costo
            
    print(f"\n💰 Costo Total de Inversión Real: {costo_total_real:.2f} pu")

if __name__ == "__main__":
    # Puedes usar 'sistema_8_barras_distancias.xlsx' u otro excel que hayas generado
    archivo = "sistema_8_barras_escalable.xlsx" 
    try:
        resolver_lp_escalable_automatico(archivo)
    except FileNotFoundError:
        print(f"No se encontró el archivo '{archivo}'. Asegúrate de tenerlo en el mismo directorio.")