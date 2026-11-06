# -*- coding: utf-8 -*-
"""
APROBAR O RECHAZAR UNA CARGA
============================
Después de revisar el reporte que generó actualizar_desde_excel.py:

    python aprobar_carga.py AGROCACAY aprobar  "Nombre"  "comentario opcional"
    python aprobar_carga.py KAHAI     rechazar "Nombre"  "motivo"

- APROBAR: la versión leída del Excel pasa a ser la vigente (la que ve el dashboard).
           Los cambios quedan guardados en el historial con quién y cuándo aprobó.
- RECHAZAR: se descarta la lectura; la versión vigente no cambia.
            Corrija el Excel y vuelva a correr actualizar_desde_excel.py.

Cada empresa se aprueba por separado.
"""
import sys
from datetime import datetime

import pandas as pd

import config as C
from actualizar_desde_excel import conectar, leer_tabla, comparar


def decidir(empresa, accion, responsable, comentario=""):
    t = C.EMPRESAS[empresa]["tabla"]
    con = conectar()
    pend = con.execute("SELECT id FROM historial_cargas WHERE empresa=? AND estado='pendiente' "
                       "ORDER BY id DESC LIMIT 1", (empresa,)).fetchone()
    if not pend:
        print(f"No hay ninguna carga pendiente de {empresa}. Corra primero actualizar_desde_excel.py")
        return
    carga_id = pend[0]
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")

    if accion == "aprobar":
        nuevo = leer_tabla(con, f"{t}_pendiente")
        vigente = leer_tabla(con, f"{t}_vigente")
        nuevas, borradas = comparar(nuevo, vigente)
        # Guardar el detalle de lo que cambió (historial de cambios por carga)
        cols = ["fila_excel"] + C.COLUMNAS_ESTANDAR + ["periodo", "naturaleza", "huella", "cambio"]
        cambios = pd.concat([nuevas[cols], borradas[cols]])
        cambios.insert(0, "carga_id", carga_id)
        cambios.to_sql(f"{t}_cambios", con, if_exists="append", index=False)
        # La versión leída pasa a ser la vigente
        nuevo.to_sql(f"{t}_vigente", con, if_exists="replace", index=False)
        con.execute(f"DROP TABLE IF EXISTS {t}_pendiente")
        estado = "aprobada"
        print(f"{empresa}: carga aprobada. {len(nuevas):,} filas nuevas/modificadas, "
              f"{len(borradas):,} borradas. Ya se ve en el dashboard.")
    else:
        con.execute(f"DROP TABLE IF EXISTS {t}_pendiente")
        estado = "rechazada"
        print(f"{empresa}: carga rechazada. La versión vigente no cambió.")

    con.execute("UPDATE historial_cargas SET estado=?, responsable=?, fecha_decision=?, comentario=? "
                "WHERE id=?", (estado, responsable, ahora, comentario, carga_id))
    con.commit()
    con.close()

    # Al aprobar, se recalcula el costo unitario de las empresas que lo tienen
    if estado == "aprobada" and empresa in C.EMPRESAS_COSTO_UNITARIO:
        print("\nRecalculando costo unitario...")
        try:
            import motor_costo_unitario
            motor_costo_unitario.correr()
        except Exception as e:
            print(f"Aviso: no se pudo recalcular el costo unitario ({e}). "
                  "Corra después:  python motor_costo_unitario.py")

    # Al aprobar, lo aprobado se sube a la nube (si ya está configurada)
    if estado == "aprobada":
        from subir_a_nube import subir_si_esta_configurada
        subir_si_esta_configurada()


if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[2].lower() not in ("aprobar", "rechazar") \
            or sys.argv[1].upper() not in C.EMPRESAS:
        print(__doc__)
        sys.exit(1)
    decidir(sys.argv[1].upper(), sys.argv[2].lower(), sys.argv[3],
            sys.argv[4] if len(sys.argv) > 4 else "")
