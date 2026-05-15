# Dashboard de coach y equipo

## Objetivo

Documentar `PPH-18`: vista consolidada para coach/admin con progreso del
equipo, pendientes, alertas y drill-down por atleta.

## Vista

La vista `Admin` muestra:

- cantidad de usuarios del equipo cargados en la sesion;
- adherencia semanal promedio;
- check-ins registrados hoy;
- lista de atletas con adherencia, planes cargados y estado diario;
- filtros de `Todos`, `Pendientes` y `Alertas`;
- drill-down del atleta seleccionado.

## Metricas

### Adherencia semanal

Se calcula como:

```text
check-ins unicos de la semana / 7
```

Para el equipo se promedia la adherencia de los atletas visibles.

### Planes cargados

Cada atleta puede tener hasta tres planes activos en el MVP:

- nutricion;
- entrenamiento;
- wellness.

El dashboard muestra cuantos estan cargados.

### Pendientes

Un atleta queda pendiente si no tiene check-in del dia.

### Alertas

El dashboard marca alerta si detecta:

- check-in pendiente hoy;
- baja adherencia semanal;
- planes incompletos;
- palabras de fatiga/recuperacion en notas recientes.

Esta logica es inicial y local al frontend. En una iteracion posterior puede
moverse a `ai_insights` para generar alertas persistidas por IA.

## Drill-down

Al tocar un atleta, la vista muestra:

- adherencia semanal;
- resumen de planes;
- alertas activas;
- ultimos check-ins.

## Permisos

El frontend solo visualiza los perfiles cargados/hidratados del equipo actual.
La proteccion fuerte por equipo debe completarse con politicas RLS y endpoints
dedicados de coach/admin en historias posteriores.
