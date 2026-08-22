# Validación local (fuera de Docker)

Antes de dar por buenos `server.py` y `cliente.py`, se corrieron localmente (sin contenedores,
en el entorno de desarrollo) para verificar que la arquitectura cliente-servidor y la lectura de
métricas funcionan de punta a punta. Esta no reemplaza la prueba con `docker compose up`, pero
sirvió para detectar errores antes de construir las imágenes.

## Prueba 1 — cliente en modo normal

```
[cliente-normal] Iniciando cliente en modo 'normal', enviando a 127.0.0.1:9199 cada 1.5s
[cliente-normal] cpu=0.1% mem=9.4% proc=50 net=0.0kbps (fuente cpu=cgroup_v1, mem=proc_meminfo_host) -> ANOMALIA
```

```
[00:27:46] cliente=cliente-normal cpu=0.1% mem=9.4% proc=50 net=0kbps -> ANOMALIA DETECTADA (score=-0.0920, 27.4 ms)
```

El cliente se conectó, el servidor lo evaluó y respondió correctamente. Se marcó como anomalía
porque `proc=50` está muy por encima de lo esperado (el modelo se entrenó asumiendo pocos
procesos, típico de un contenedor liviano). Esto es un artefacto esperado del entorno de prueba:
al no estar dentro de un contenedor Docker con namespace de PID aislado, `/proc` lista **todos**
los procesos del sistema compartido, no solo los del "cliente". Dentro de un contenedor Docker
real, este número sería bajo y estable, como se espera para un cliente normal.

## Prueba 2 — cliente en modo carga

```
[cliente-carga] Iniciando cliente en modo 'carga', enviando a 127.0.0.1:9198 cada 1.5s
[cliente-carga] Modo CARGA activo: 2 procesos de trabajo + ~80 MB reservados.
[cliente-carga] cpu=100.0% mem=11.6% proc=53 net=0.0kbps (fuente cpu=cgroup_v1, mem=proc_meminfo_host) -> ANOMALIA
```

```
[00:28:03] cliente=cliente-carga  cpu=100.0% mem=11.6% proc=53 net=0kbps -> ANOMALIA DETECTADA (score=-0.1333, 75.6 ms)
```

Aquí sí se validó lo importante: el entorno de prueba expone cgroup v1, y el lector de métricas lo
usó automáticamente (`fuente cpu=cgroup_v1`) en lugar de `/proc/stat` a nivel de host. El modo de
carga generó procesos reales de cómputo intensivo, y el cgroup midió correctamente **100 % de uso
de CPU real** — no un valor simulado — y el modelo lo clasificó como anomalía. Esto confirma que la
cadena completa (generar carga real → medirla vía cgroup → enviarla por socket → evaluarla con el
modelo → responder) funciona correctamente.

## Corrección posterior: falso positivo en client-normal dentro de Docker

Al correr `docker compose up --build` de verdad (algo que este entorno de desarrollo no pudo hacer
por no tener el daemon de Docker disponible), `client-normal` salía marcado como `ANOMALIA` en
**todas** las lecturas, igual que `client-carga`. El log real fue:

```
cliente=cliente-normal cpu=0.1% mem=8.0% proc=1 net=1kbps -> ANOMALIA DETECTADA (score=-0.0411, 2.9 ms)
cliente=cliente-carga  cpu=97.1% mem=78.8% proc=7 net=1kbps -> ANOMALIA DETECTADA (score=-0.1252, 4.5 ms)
```

**Causa:** el lote de entrenamiento (`generar_bootstrap_normal`) se había calibrado con una
estimación genérica de "servidor liviano" (cpu≈5%, mem≈15%, ≈5 procesos, red≈3 kbps), pero un
contenedor Python real en reposo, con `mem_limit: 128m` y PID namespace aislado, resultó ser aún
más liviano de lo estimado: cpu≈0%, mem≈8%, **1 solo proceso**, red≈0.5 kbps. Como las cuatro
métricas del cliente normal caían simultáneamente en la cola baja de la distribución de
entrenamiento, Isolation Forest las aislaba con pocos cortes y las clasificaba como anómalas —un
falso positivo por desajuste de calibración, no un error de arquitectura.

**Corrección:** se recalibró `generar_bootstrap_normal` en `server/monitor_common.py` usando estos
valores reales como centro de la distribución normal (cpu~N(1.0, 1.2), mem~N(9, 2.5), procesos
mayormente 1, red~N(1.0, 1.0)). Se verificó con el propio `server.py` y los valores exactos del log:

```
cliente=cliente-normal cpu=0.1% mem=8.0% proc=1 net=1kbps -> normal (score=0.1452, 21.2 ms)
cliente=cliente-carga  cpu=100.0% mem=81.6% proc=7 net=0kbps -> ANOMALIA DETECTADA (score=-0.1870, 27.7 ms)
```

Este episodio también es un buen ejemplo de una limitación real de Isolation Forest entrenado con
un solo lote de arranque: si la distribución "normal" asumida no coincide con el entorno real de
despliegue, el modelo produce falsos positivos sistemáticos hasta que se recalibra o se reentrena
con datos reales — algo que vale la pena mencionar en la sección de análisis del informe si se
actualiza más adelante.

## Pendiente de validar con Docker real

No fue posible construir ni correr las imágenes de Docker dentro de este entorno de desarrollo
(no tiene el daemon de Docker disponible). Los Dockerfiles y el `docker-compose.yml` siguen
prácticas estándar y se probaron en su lógica equivalente en Python puro, pero se recomienda
correr `docker compose up --build` en una máquina con Docker antes de considerar la entrega
completa, y revisar especialmente:

- Que `client-normal` se reporte con un conteo de procesos bajo y estable (a diferencia de la
  prueba local de arriba).
- Que las rutas de cgroup (`/sys/fs/cgroup/...`) existan dentro del contenedor; en cgroup v2
  (por defecto en Docker moderno) deberían estar en `/sys/fs/cgroup/cpu.max`, `cpu.stat`,
  `memory.current` y `memory.max` directamente.
