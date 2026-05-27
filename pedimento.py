"""Extracción de datos del PDF del pedimento.

Lee el texto del pedimento (formato SAT/ANAM, texto seleccionable) y devuelve
los campos que alimentan el costeo:
    - no_pedimento
    - tipo_cambio
    - impuestos   = DTA + PRV            (contribuciones distintas al IVA)
    - iva_aduana  = IVA + IVA/PRV
    - factura_proveedor_usd             (VAL. DOLARES de la(s) factura(s))

Los gastos de logística (fletes, maniobras, almacenajes) NO vienen en el
pedimento; esos se capturan aparte (selector/manual).
"""

import re

import pdfplumber

INCOTERMS = "FOB|CIF|CFR|EXW|DDP|FCA|CPT|CIP|DAP|DPU|FAS|DDU"


def _num(s):
    if s is None:
        return None
    return float(s.replace(",", "").strip())


def _proveedor(doc):
    """Reconstruye el nombre del proveedor usando posiciones (columna NOMBRE).

    El texto plano mezcla las columnas (nombre/domicilio); por eso usamos las
    coordenadas de cada palabra para quedarnos solo con la columna del nombre.
    """
    for page in doc.pages:
        words = page.extract_words()
        hdr = next((w for w in words if w["text"].startswith("NOMBRE,DENOMINACION")), None)
        if not hdr:
            continue
        nx0 = hdr["x0"]
        # La fila "NUM. FACTURA" marca el fin del bloque del nombre/domicilio.
        fac = next((w for w in words if w["text"] == "FACTURA" and w["top"] > hdr["top"]), None)
        top_max = fac["top"] if fac else hdr["top"] + 80
        col = [
            w for w in words
            if hdr["top"] + 2 < w["top"] < top_max - 1 and nx0 - 6 <= w["x0"] <= nx0 + 188
        ]
        col.sort(key=lambda w: (round(w["top"]), w["x0"]))
        nombre = " ".join(w["text"] for w in col).strip()
        return nombre or None
    return None


def extraer(archivo):
    """archivo: ruta o file-like (PDF). Devuelve un dict con los campos."""
    if hasattr(archivo, "seek"):
        archivo.seek(0)
    with pdfplumber.open(archivo) as doc:
        paginas = len(doc.pages)
        texto = "\n".join((p.extract_text() or "") for p in doc.pages)
        proveedor = _proveedor(doc)

    d = {"_paginas": paginas, "_texto": texto, "proveedor": proveedor}

    m = re.search(r"NUM\.?\s*PEDIMENTO:?\s*(\d{2}\s+\d{2}\s+\d{4}\s+\d{7})", texto)
    d["no_pedimento"] = re.sub(r"\s+", " ", m.group(1)).strip() if m else None

    # Orden interna (folio tipo CM###-##-#): NO siempre aparece en el pedimento.
    m = re.search(r"CM\d{2,4}-\d{2}-\d{1,2}", texto)
    d["orden"] = m.group(0) if m else None

    m = re.search(r"TIPO\s*CAMBIO:?\s*(\d+\.\d+)", texto)
    d["tipo_cambio"] = _num(m.group(1)) if m else None

    # Aislar el "CUADRO DE LIQUIDACION" para no confundir importes con las tasas.
    liq = texto
    if "CUADRO DE LIQUIDACION" in texto:
        liq = texto.split("CUADRO DE LIQUIDACION", 1)[1]
        liq = re.split(r"DEP[ÓO]SITO REFERENCIADO|\*\*\*\s*PAGO", liq)[0]

    def importe(concepto):
        m = re.search(concepto + r"\s+\d+\s+([\d,]+)", liq)
        return _num(m.group(1)) if m else 0.0

    dta = importe(r"(?<![A-Z/])DTA")
    prv = importe(r"(?<![A-Z/])PRV")
    iva = importe(r"(?<![A-Z/])IVA(?![/A-Z])")
    iva_prv = importe(r"IVA/PRV")

    d["dta"], d["prv"], d["iva"], d["iva_prv"] = dta, prv, iva, iva_prv
    d["impuestos"] = dta + prv
    d["iva_aduana"] = iva + iva_prv

    # Factura(s) del proveedor: tomar VAL. DOLARES (último número de la línea).
    facturas = re.findall(
        r"\b(?:" + INCOTERMS + r")\s+[A-Z]{3}\s+[\d,]+\.\d{2}\s+[\d.]+\s+([\d,]+\.\d{2})",
        texto,
    )
    d["factura_proveedor_usd"] = sum(_num(x) for x in facturas) if facturas else None

    return d


if __name__ == "__main__":
    import sys

    for ruta in sys.argv[1:]:
        print("=" * 70)
        print(ruta.split("/")[-1])
        d = extraer(ruta)
        for k, v in d.items():
            if not k.startswith("_"):
                print(f"  {k:24} = {v}")
        print(f"  (paginas: {d['_paginas']})")
