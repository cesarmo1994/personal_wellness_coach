# Analisis y creacion de planes con OpenAI

## Objetivo

Documentar el flujo robusto de carga, analisis y creacion de planes correspondiente a `PPH-15`.

## Capacidades

La app soporta dos caminos:

- Crear plan desde archivo.
- Crear plan por conversacion con IA.

Tipos de plan:

- Nutricion.
- Entrenamiento.
- Wellness.

## Formatos soportados

### PDF

Los PDFs se envian a OpenAI mediante Files API y se analizan junto con la descripcion/contexto escrito por el usuario.

### Word

Formato soportado:

```text
.docx
```

El backend extrae texto localmente y envia el contenido a OpenAI como texto.

### Excel

Formato soportado:

```text
.xlsx
```

El backend extrae texto localmente desde las hojas principales y envia el contenido a OpenAI como texto.

### Texto y tablas simples

Formatos soportados:

```text
.csv
.tsv
.txt
.md
```

El backend lee el contenido como texto.

## Formatos no soportados

Formatos antiguos como `.doc` o `.xls` no se procesan directamente.

Accion recomendada:

- Guardar como `.docx`, `.xlsx`, `.csv`, `.txt` o PDF.

## Limite de archivo

Limite por archivo:

```text
25 MB
```

## Flujo de analisis por archivo

1. Usuario selecciona tipo de plan.
2. Usuario sube archivo.
3. Usuario agrega descripcion/contexto.
4. Backend valida extension y tamano.
5. Backend guarda copia temporal local.
6. Si es PDF, backend sube el archivo a OpenAI Files API.
7. Si es DOCX/XLSX/CSV/TXT/MD, backend extrae texto localmente.
8. Backend envia archivo/texto + descripcion en una sola solicitud a OpenAI.
9. OpenAI devuelve resumen accionable.
10. Backend guarda el plan como `active` en Supabase.
11. Backend archiva planes activos previos del mismo usuario y tipo.
12. Si hay archivo, backend lo guarda en `plan-files` y registra metadata en `plan_files`.

## Flujo de creacion por conversacion

1. Usuario escribe objetivo, restricciones y contexto.
2. Backend envia contexto reciente a OpenAI.
3. OpenAI devuelve un plan claro y accionable.
4. Backend guarda el plan como `active` en Supabase.
5. Backend archiva planes activos previos del mismo usuario y tipo.

## Persistencia

Tabla principal:

```text
plans
```

Campos clave:

- `profile_id`
- `plan_type`
- `status`
- `source`
- `title`
- `user_notes`
- `summary`
- `structured_plan`
- `activated_at`

Archivos:

```text
plan_files
```

El archivo real vive en:

```text
Supabase Storage / plan-files
```

## Plan activo

Regla:

- Solo un plan activo por usuario y tipo.

Cuando se crea un nuevo plan activo, el backend archiva el plan activo anterior del mismo tipo.

## Errores accionables

El backend intenta devolver mensajes claros para:

- Archivo muy grande.
- Extension no soportada.
- Word/Excel corrupto o no legible.
- Falta de API key.
- Error de OpenAI.
- Error de Supabase.

## Validacion para cierre de PPH-15

Probar:

- PDF + descripcion.
- DOCX + descripcion.
- XLSX o CSV + descripcion.
- Creacion por conversacion.
- Confirmar en Supabase que el plan queda `active`.
- Confirmar que el plan activo anterior queda `archived`.
- Confirmar que errores de formato no soportado son entendibles.
