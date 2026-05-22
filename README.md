# Costeo de importación (landed cost)

Herramienta interna para calcular el costo total de un embarque importado.
Sube el **pedimento** (PDF) y se autocompletan tipo de cambio, impuestos, IVA de
aduana y factura del proveedor; los costos de logística se eligen de un catálogo
de tarifas o se capturan a mano. El costeo se calcula al instante en pantalla.

## Correr en local

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Luego abre http://localhost:8501

## Estructura

| Archivo | Qué hace |
|---|---|
| `app.py` | Interfaz web (Streamlit) |
| `costeo.py` | Motor de cálculo (fórmulas del landed cost) |
| `pedimento.py` | Extracción de datos del PDF del pedimento |
| `tarifas.py` | Catálogo de tarifas (fletes, maniobras+honorarios) |
