"""Extracción de datos del PDF de la factura del flete marítimo (CFDI).

Lee el CFDI emitido por el forwarder (Henco Global, etc.) y devuelve:
    - flete_subtotal: subtotal en la moneda de la factura (USD típicamente).
      Es el monto que va al campo "Flete marítimo" del costeo (lo que sumó
      Marisa en su Excel para esta partida).
    - moneda: USD/MXN según la factura.
    - orden: folio interno tipo CM###-## (a veces aparece como "P.O. Reference").
    - total: total con IVA en la moneda de la factura (informativo).
"""

import re

import pdfplumber


def extraer(archivo):
    """archivo: ruta o file-like (PDF). Devuelve un dict con los campos."""
    if hasattr(archivo, "seek"):
        archivo.seek(0)
    with pdfplumber.open(archivo) as doc:
        paginas = len(doc.pages)
        texto = "\n".join((p.extract_text() or "") for p in doc.pages)

    d = {"_paginas": paginas, "_texto": texto}

    # Subtotal en la moneda de la factura: "Subtotal (USD): 3,125.00"
    m = re.search(r"Subtotal\s*\(([A-Z]{3})\)\s*:\s*([\d,]+\.\d{2})", texto)
    if m:
        d["moneda"] = m.group(1)
        d["flete_subtotal"] = float(m.group(2).replace(",", ""))
    else:
        d["moneda"] = None
        d["flete_subtotal"] = None

    # Total con IVA (informativo): "Total (USD): 3,143.40"
    m = re.search(r"Total\s*\([A-Z]{3}\)\s*:\s*([\d,]+\.\d{2})", texto)
    d["total"] = float(m.group(1).replace(",", "")) if m else None

    # Órdenes internas (folios CM###-## o CM###-##-#). Una factura puede traer
    # VARIAS órdenes; se capturan todas, en orden y sin duplicados. El patrón
    # excluye el texto sobrante (ej. "（part of）") y el sello digital (sin guion).
    ordenes = []
    for m in re.findall(r"CM\d{2,4}-\d{2}(?:-\d{1,2})?", texto):
        if m not in ordenes:
            ordenes.append(m)
    d["ordenes"] = ordenes
    d["orden"] = ordenes[0] if ordenes else None  # compatibilidad

    return d


if __name__ == "__main__":
    import sys

    for ruta in sys.argv[1:]:
        print("=" * 70)
        print(ruta.split("/")[-1])
        d = extraer(ruta)
        for k, v in d.items():
            if not k.startswith("_"):
                print(f"  {k:18} = {v}")
        print(f"  (paginas: {d['_paginas']})")
