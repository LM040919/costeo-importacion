"""Generación del archivo Excel del costeo (botón de descarga).

Replica el layout de la plantilla "COSTEO ESTIMADO" de Marisa (mismas filas y
columnas), pero con **fórmulas** en lugar de valores hardcodeados — así el
archivo descargado sigue siendo editable y se recalcula solo si tocan algún
campo. Al final agrega un bloque con el detalle de las extracciones del
pedimento (DTA / PRV / IGI / IVA / IVA-PRV) y las tarifas elegidas del catálogo.
"""

from datetime import date
from io import BytesIO

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill


TITULO = Font(bold=True, size=14)
NEGRITA = Font(bold=True)
ITALICA = Font(italic=True, size=10, color="595959")
FONDO_HEADER = PatternFill("solid", start_color="DDEBF7")
FORMATO_MXN = "$#,##0.00"


def generar_xlsx(inp, r, detalle_pedimento=None, mh_label=None, ft_label=None):
    """Construye el .xlsx del costeo y devuelve sus bytes.

    Args:
        inp: CosteoInputs con los valores capturados.
        r: CosteoResultado (los totales se recalculan con fórmulas en el Excel).
        detalle_pedimento: dict opcional con dta/prv/igi/iva/iva_prv/ieps...
        mh_label: etiqueta del selector de maniobras (ej. "WISE ($20,640.00)").
        ft_label: etiqueta del selector de flete terrestre.

    Returns:
        bytes: contenido del archivo .xlsx listo para descargar.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "COSTEO"

    # --- Encabezado ---
    ws["A1"] = "ELABORÓ:"
    ws["A1"].font = NEGRITA
    ws["B1"] = "Costeo App (Marvel)"
    ws["D1"] = "FECHA:"
    ws["D1"].font = NEGRITA
    ws["E1"] = date.today()
    ws["E1"].number_format = "yyyy-mm-dd"

    ws["B2"] = "NO. PEDIMENTO"
    ws["B2"].font = NEGRITA
    ws["C2"] = inp.no_pedimento or ""
    ws["D2"] = "T.C."
    ws["D2"].font = NEGRITA
    ws["E2"] = float(inp.tipo_cambio or 0)
    ws["E2"].number_format = "0.0000"

    ws.merge_cells("B3:D3")
    ws["B3"] = "COSTEO ESTIMADO"
    ws["B3"].font = TITULO
    ws["B3"].alignment = Alignment(horizontal="center")

    ws["A6"] = "ORDEN"
    ws["A6"].font = NEGRITA
    ws["B6"] = inp.orden or ""

    ws.merge_cells("B9:E9")
    ws["B9"] = inp.proveedor or ""
    ws["B9"].font = NEGRITA
    ws["B9"].alignment = Alignment(horizontal="center")

    # --- Cuenta de gastos ---
    ws["D12"] = "IVA"
    ws["E12"] = "VALOR SIN IVA"
    ws["D12"].font = NEGRITA
    ws["E12"].font = NEGRITA
    ws["D12"].fill = FONDO_HEADER
    ws["E12"].fill = FONDO_HEADER

    ws["B13"] = "IMPUESTOS"
    ws["E13"] = float(inp.impuestos or 0)
    ws["B14"] = "IVA"
    ws["D14"] = float(inp.iva_aduana or 0)

    ws["B15"] = "MANIOBRAS Y HONORARIOS"
    ws["E15"] = float(inp.maniobras or 0)
    ws["B16"] = "IVA"
    ws["D16"] = "=E15*0.16"

    ws["B17"] = "HONORARIOS"
    ws["E17"] = float(inp.honorarios or 0)
    ws["B18"] = "IVA"
    ws["D18"] = "=E17*0.16"

    ws["B19"] = "DEMORAS (si aplica)"
    ws["E19"] = float(inp.otros_demoras or 0)
    ws["F19"] = "=E15"
    ws["G19"] = "Este es el valor que va en la partida de gastos de importacion en LC"
    ws["G19"].font = ITALICA
    ws["B20"] = "IVA"
    ws["D20"] = "=E19*0.16"

    ws["B21"] = "ALMACENAJE (si aplica)"
    ws["E21"] = float(inp.almacenajes or 0)
    ws["B22"] = "IVA"
    ws["D22"] = "=E21*0.16"

    ws["B23"] = "FLETE MARITIMO"
    ws["F23"] = float(inp.flete_maritimo_usd or 0)
    ws["E23"] = "=F23*E2"
    ws["B24"] = "IVA"

    ws["B25"] = "FLETE LOCAL"
    ws["E25"] = float(inp.flete_local or 0)
    ws["F25"] = "=E25"
    ws["G25"] = "Cuando es consolidado este flete terrestre entra como gasto de importacion."
    ws["G25"].font = ITALICA
    ws["B26"] = "IVA"
    ws["D26"] = "=E25*0.16"

    ws["B27"] = "POS. EN FALSO"
    ws["E27"] = float(inp.falsos or 0)
    ws["B28"] = "IVA"

    ws["B29"] = "TOTAL GASTOS"
    ws["B29"].font = NEGRITA
    ws["D29"] = "=SUM(D13:D28)"
    ws["E29"] = "=SUM(E13:E28)"
    ws["D29"].font = NEGRITA
    ws["E29"].font = NEGRITA

    ws["D31"] = "TOTAL CUENTA DE GASTOS"
    ws["D31"].font = NEGRITA
    ws["E31"] = "=D29+E29"
    ws["E31"].font = NEGRITA

    # --- Costo del embarque ---
    ws["D34"] = "TIPO DE CAMBIO"
    ws["D34"].font = NEGRITA
    ws["E34"] = "=E2"
    ws["E34"].number_format = "0.0000"

    ws["D35"] = "PESOS"
    ws["E35"] = "DOLARES"
    ws["D35"].font = NEGRITA
    ws["E35"].font = NEGRITA
    ws["D35"].fill = FONDO_HEADER
    ws["E35"].fill = FONDO_HEADER

    ws["B36"] = "FAC. PROVEEDOR"
    ws["E36"] = float(inp.factura_proveedor_usd or 0)
    ws["D36"] = "=E2*E36"

    ws["B37"] = "CARGOS POR SERVICIOS DE TRANSFERENCIA"
    ws["E37"] = float(inp.cargos_transferencia_usd or 0)
    ws["D37"] = "=E37*E34"

    ws["B38"] = "PRORRATEO GTOS. MEX. MN"
    ws["D38"] = "=E29+D37"

    ws["B41"] = "TOTAL DE EMBARQUE"
    ws["B41"].font = Font(bold=True, size=12)
    ws["D41"] = "=SUM(D36:D38)"
    ws["D41"].font = Font(bold=True, size=12)

    ws["B43"] = "% GASTO CONTRA LA FACTURA"
    ws["B43"].font = NEGRITA
    ws["C43"] = "=D38/D36"
    ws["C43"].number_format = "0.00%"
    ws["C43"].font = NEGRITA

    # Formato de moneda para todas las celdas con dinero
    for c in ("E13 D14 E15 D16 E17 D18 E19 F19 D20 E21 D22 E23 F23 "
              "E25 F25 D26 E27 D29 E29 E31 D36 E36 D37 E37 D38 D41").split():
        ws[c].number_format = FORMATO_MXN

    # --- Bloque inferior: detalle de extracciones y selecciones ---
    ws["A46"] = "Detalle de extracciones y selecciones"
    ws["A46"].font = Font(bold=True, size=12, italic=True)
    ws.merge_cells("A46:E46")

    fila = 48
    if detalle_pedimento:
        ws[f"A{fila}"] = "Contribuciones extraídas del pedimento:"
        ws[f"A{fila}"].font = NEGRITA
        ws.merge_cells(f"A{fila}:C{fila}")
        fila += 1
        for label, key in [("DTA", "dta"), ("PRV", "prv"), ("IGI", "igi"),
                           ("IEPS", "ieps"), ("IVA", "iva"),
                           ("IVA/PRV", "iva_prv"), ("IEPS/IVA", "ieps_iva")]:
            val = detalle_pedimento.get(key, 0) or 0
            if val:
                ws[f"B{fila}"] = label
                ws[f"C{fila}"] = float(val)
                ws[f"C{fila}"].number_format = FORMATO_MXN
                fila += 1
        fila += 1

    if mh_label:
        ws[f"A{fila}"] = "Maniobras y honorarios (catálogo):"
        ws[f"A{fila}"].font = NEGRITA
        ws[f"D{fila}"] = mh_label
        fila += 1

    if ft_label:
        ws[f"A{fila}"] = "Flete local / terrestre (catálogo):"
        ws[f"A{fila}"].font = NEGRITA
        ws[f"D{fila}"] = ft_label
        fila += 1

    # Anchos de columna
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 38
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 14
    ws.column_dimensions["G"].width = 50

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
