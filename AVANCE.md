# Avance — Herramienta de costeo de importación

**Fecha:** 2026-05-22 · **Responsable:** Luis · **Estado:** v1 funcional (local)

## Resumen

Se aterrizaron los costos de los fletes terrestres de los proveedores con los que
se opera actualmente, y con eso se construyó una primera versión funcional de una
herramienta web que **automatiza el costeo de importación (landed cost)** que hoy
se hace a mano en Excel. La herramienta toma el pedimento, calcula el costo total
del embarque y lo muestra al instante.

## Qué se construyó

1. **Motor de cálculo** que reproduce *exactamente* las fórmulas de la plantilla
   "COSTEO ESTIMADO". Verificado contra el caso real **CM357-25-4**: total de
   embarque **$849,763.23** y % de gasto **12.68%**, idénticos al Excel.
2. **Interfaz web** (Streamlit) que recalcula en vivo y muestra el desglose de
   gastos y el costo del embarque.
3. **Selectores de tarifas** para los costos estandarizados:
   - **Flete terrestre:** Henco (Sencillo $24,250 / Full $37,500), RTC (Full
     $37,000), GISAP (Sencillo $24,800) — montos sin IVA.
   - **Maniobras + honorarios** (van juntos): WISE $20,640 / WOODWARD $18,192.50
     — sin IVA.
   - Cada selector tiene la opción "Otro (capturar monto)".
4. **Extracción automática del pedimento (PDF):** al subirlo se autocompletan el
   tipo de cambio, los impuestos, el IVA de aduana y la factura del proveedor.

## Cómo funciona el flujo

Subes el pedimento → se llenan solos los datos fiscales → eliges/capturas los
costos de logística → ves el costo total del embarque.

## Hallazgo clave (descifrado del pedimento)

Las fórmulas "raras" del Excel correspondían a campos del **cuadro de liquidación**
del pedimento:

- **Impuestos** (al costo) = DTA + PRV + IGI + IEPS
- **IVA de aduana** (recuperable) = IVA + IVA/PRV + IEPS/IVA

Cuando un concepto aparece con varias formas de pago (FP 0 y FP 15), se suman
todos los renglones.
- **Factura del proveedor (USD)** = VAL. DOLARES de la línea del proveedor

Regla financiera respetada: el **IVA es recuperable y no se carga al costo**; solo
los gastos netos (sin IVA) se prorratean sobre la mercancía.

## Verificación

| Pedimento | Tipo cambio | Impuestos | IVA aduana | Factura (USD) |
|---|---|---|---|---|
| 6004925 *(ejemplo)* | 17.2520 | 6,699 | 128,455 | 43,713.00 |
| 6004912 | 17.2928 | 6,943 | 22,750 | 44,819.07 |
| 6004904 | 17.2928 | 1,895 | 53 | 8,874.00 |
| 6004907 | 17.2928 | 1,978 | 53 | 9,480.00 |

Los 4 pedimentos son PDF de texto (no escaneados), por lo que la lectura es
confiable y no requiere OCR.

## Pendientes / dudas para Compras (Isabel)

- **Cargos por transferencia:** Isabel no los usa en su proceso, pero le va a
  pedir a sus compañeras que revisen si el doble conteo de la plantilla del
  Excel original es correcto o un error.
- **Flete local de $26,500** que aparece en CM009-26: no calza con las tarifas
  conocidas (Henco / RTC / GISAP). ¿De qué transportista y tipo es esta tarifa?
- **Catálogos de tarifas:** ¿están completos? ¿hay más proveedores de flete
  terrestre o más agentes aduanales además de WISE/WOODWARD?

### Resuelto

- **Ajuste de 925.44** al IVA del flete local: Luis confirmó que era un
  **error** de la plantilla original; ya removido del cálculo (2026-06-04).
  Confirmado adicionalmente al ver el costeo de CM009-26: D26 = E25 × 16%
  sin la resta.
- **Forma de pago 15 (OTROS) en el pedimento:** Marisa la incluye al costo
  (sumada con FP=0). El extractor ya lo hace así. Verificado con CM009-26.

## Pendientes técnicos

- **Extracción de la factura del flete marítimo:** Luis quiere subir el PDF de
  la factura del forwarder y que se autorelleno el campo de flete marítimo.
  Bloqueado hasta tener una factura de muestra.

## Próximos pasos posibles

- Descargar el resultado en Excel con el formato actual de la plantilla.
- Agregar más tarifas al catálogo conforme las confirme Compras.
