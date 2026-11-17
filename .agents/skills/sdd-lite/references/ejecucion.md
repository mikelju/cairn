# Ejecución de incrementos

Para el ejecutor con un encargo de implementación o corrección.

1. Comprueba rama y carpeta contra "Dónde" del brief; trabaja contra los incrementos y criterios copiados en tu brief y los archivos de código indicados en "Contexto" (no leas `plan.md` ni planes de fases anteriores).
2. Implementa un incremento cada vez; el producto queda funcionando al cerrar cada uno.
3. Reproduce los fallos antes de corregirlos, en el recorrido real del usuario; añade la regresión cuando aporte valor.
4. Al cerrar cada incremento: `npm run --silent check:puerta` en verde (el `npm run check` completo lo ejecuta el supervisor antes de la entrega; nunca lo dejes corriendo en segundo plano), haz commit en la rama de trabajo y devuelve en tu informe la evidencia concisa (hash del commit, comando o recorrido y resultado observado) para que el supervisor marque `plan.md`. No edites `plan.md`.
   Si notas que tu contexto se agota, haz commit del trabajo en curso en la rama, aunque la comprobación esté en rojo, y devuelve `Estado: fallido` con lo hecho y lo que falta.
   Nunca dejes trabajo solo en el árbol.
5. Lo que cambie criterios congelados no lo resuelves: devuelve `necesita decisión` para que el supervisor abra una desviación.
6. Defectos ajenos al encargo: anótalos en Pendientes de tu informe, no los arregles.
7. Tras cualquier corrección, la evidencia anterior de los criterios afectados deja de valer: obténla de nuevo.
