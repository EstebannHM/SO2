# Monitor inteligente de sistema con detección de anomalías

Proyecto de investigación — BISOFT-34 Sistemas Operativos II, Universidad Latina de Costa Rica.
Estudiante: Santiago Osejo Lobo.

Sistema distribuido de monitoreo de métricas del sistema operativo (CPU, memoria, procesos y red),
con detección de comportamientos anómalos mediante un modelo de aprendizaje automático no
supervisado (Isolation Forest). El informe académico completo, con el marco teórico y el análisis
de resultados, está en `docs/`.

## Arquitectura

```
┌────────────────────┐        TCP / JSON        ┌──────────────────────┐
│  Cliente(s)         │ ────────────────────────▶│  Servidor             │
│  (lee /proc o       │                           │  Isolation Forest     │
│   cgroups reales     │◀──────────────────────── │  entrenado al arrancar│
│   del contenedor)    │   {es_anomalia, score}    │  (scikit-learn)       │
└────────────────────┘                           └──────────────────────┘
```

- **Servidor** (`server/`): entrena el modelo al arrancar y queda escuchando en un socket TCP,
  atendiendo cada conexión en un hilo (`threading`). Es un servicio persistente pensado para
  correr indefinidamente.
- **Cliente** (`client/`): lee métricas reales del contenedor donde corre (CPU y memoria vía
  cgroups, con fallback automático a `/proc` a nivel de host si no hay cgroups disponibles) y las
  envía periódicamente al servidor. Incluye un **modo de carga** que genera trabajo real (procesos
  de CPU intensiva + reserva de memoria) para demostrar la detección con una anomalía genuina, no
  simulada.
- **`experimento/`**: los scripts usados para el experimento controlado del informe académico
  (Semana 14), con datos sintéticos etiquetados para poder calcular precisión/recall de forma
  objetiva. Son independientes del despliegue en Docker.

## Ejecución con Docker

Requiere Docker y Docker Compose.

```bash
docker compose up --build
```

Esto levanta tres contenedores en una red interna (`monitor-net`):

| Servicio         | Rol                                                              |
|------------------|-------------------------------------------------------------------|
| `server`         | Servidor de monitoreo, expuesto también en `localhost:9099`       |
| `client-normal`  | Cliente que reporta su estado real en reposo                      |
| `client-carga`   | Cliente que genera carga real de CPU y memoria dentro de sí mismo |

En los logs del servidor (`docker compose logs -f server`) se debería ver `client-normal`
clasificado como `normal` y `client-carga` clasificado como `ANOMALIA DETECTADA` una vez que su
carga real se refleje en sus métricas de cgroup. Cada contenedor cliente tiene un límite de
memoria de 128 MB (`mem_limit`, ver `docker-compose.yml`) para que el porcentaje de uso de memoria
leído por cgroups sea significativo y comparable entre ambos.

Para apagar todo:

```bash
docker compose down
```

### Nota sobre las métricas dentro de contenedores

`/proc/stat` y `/proc/meminfo` no están aislados por namespace en Docker por defecto: dentro de un
contenedor suelen reflejar al **host completo**, no al contenedor en sí. Por eso `client/lector_proc.py`
primero intenta leer los contadores de **cgroup** (`cpu.stat`/`cpu.max` y `memory.current`/`memory.max`
en cgroup v2, con fallback a cgroup v1), que sí son específicos del contenedor, y solo si no están
disponibles cae de vuelta a `/proc` a nivel de host. El conteo de procesos y el tráfico de red sí se
leen de `/proc` porque esos sí están correctamente aislados por namespace en Docker (PID namespace y
network namespace).

Esto se validó localmente fuera de Docker (ver `docs/validacion_local.md`): con cgroup v1 disponible,
el modo de carga generó un pico real de CPU medido en 100 %, y el modelo lo marcó correctamente como
anomalía. El conteo de procesos en esa prueba salió inflado porque el entorno de prueba no aísla el
namespace de PID como sí lo hace un contenedor Docker real; al correr con `docker compose up`, ese
número debería verse bajo y estable para los clientes normales.

## Ejecución sin Docker (para desarrollo)

```bash
# Terminal 1
cd server && pip install -r requirements.txt && python server.py

# Terminal 2
cd client && SERVER_HOST=127.0.0.1 SERVER_PORT=9099 MODO=normal python cliente.py

# Terminal 3 (opcional, para ver la detección de anomalías en vivo)
cd client && SERVER_HOST=127.0.0.1 SERVER_PORT=9099 CLIENT_ID=carga MODO=carga python cliente.py
```

## Reproducir el experimento del informe

```bash
cd experimento
pip install -r requirements.txt
python cliente_experimento.py
```

Esto entrena el modelo, lanza 20 clientes concurrentes simulados con un flujo de 400 métricas
sintéticas (5 % de anomalías etiquetadas) y una prueba de caída del servidor, imprimiendo las
mismas métricas reportadas en el informe (throughput, latencia, precisión, recall, F1, tiempo de
detección de caída). Los resultados exactos pueden variar levemente de una corrida a otra por la
naturaleza concurrente del experimento; el informe documenta una corrida de referencia.

## Estructura del repositorio

```
.
├── server/            # Servicio persistente del servidor (Docker)
├── client/            # Cliente de monitoreo (Docker)
├── experimento/        # Scripts del experimento controlado del informe
├── docs/               # Informe académico y notas de validación
├── docker-compose.yml
└── LICENSE
```

## Mejoras futuras

En línea con el objetivo específico 5 del proyecto, y con lo discutido en la sección de análisis
del informe:

- Usar conexiones TCP persistentes (o un servidor asíncrono con `asyncio`) en lugar de abrir una
  conexión nueva por cada métrica enviada, para reducir la latencia observada en el experimento.
- Confirmar una anomalía con varias lecturas consecutivas antes de alertar, en lugar de decidir con
  una sola muestra, para reducir falsos positivos.
- Añadir cifrado TLS en la comunicación cliente-servidor (mencionado como opcional en el enunciado).
- Reentrenar o actualizar el modelo periódicamente con una ventana deslizante de datos reales, en
  lugar de un único entrenamiento de arranque.

## Licencia

Este proyecto se publica bajo la licencia MIT — ver [`LICENSE`](./LICENSE).
