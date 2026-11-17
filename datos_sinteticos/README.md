# Datos sintéticos

Aquí van los Modelos y bases de datos **ficticios** para probar las herramientas. Nunca datos reales de proyectos.

Pendiente de construir. Sugerencia de contenido:

- `modelo_minimo/`: copia de `referencia/plantillas_V4/` con un polígono general, un polígono específico y unas pocas
  actividades (Corte, Trinchera, Recolección superficial), una tabla de unidades y un Metadato diligenciado.
  Registro ficticio `R0000A00` (polígono `R0000A000001`).
- `modelo_con_errores/`: el mismo, con un error sembrado por cada regla del verificador (ID mal formado, valor fuera
  de dominio, texto > bytes, punto fuera de su actividad, FECHA_INI > FECHA_FIN, ortoplano faltante, etc.), y un
  `esperado.json` con los hallazgos que debe producir.
- `bd_materiales.xlsx` + `config.json`: BD con hojas por material, etiquetas de actividad con variantes
  («Corte 1», «corte  1», «Trinchera 9» inexistente, fila sin actividad), estratos RS / vacíos, profundidades en
  rango y en dos columnas, textos largos con tildes.
