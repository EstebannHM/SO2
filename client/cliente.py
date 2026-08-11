"""
Cliente de monitoreo (para despliegue en Docker).

Lee metricas reales del propio contenedor (via lector_proc.py) cada
INTERVALO segundos y las envia al servidor por socket TCP.

Variables de entorno:
  SERVER_HOST   host del servidor (default "server", nombre del servicio
                en docker-compose.yml)
  SERVER_PORT   puerto del servidor (default 9099)
  CLIENT_ID     identificador que se muestra en los logs del servidor
  INTERVALO     segundos entre envios (default 3)
  MODO          "normal" (default) o "carga": en modo carga, el cliente
                genera trabajo real (CPU, memoria, subprocesos) para
                demostrar que el servidor detecta la anomalia con datos
                reales, no simulados.
"""
import json
import multiprocessing
import os
import socket
import time

from lector_proc import leer_metricas

SERVER_HOST = os.environ.get("SERVER_HOST", "server")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "9099"))
CLIENT_ID = os.environ.get("CLIENT_ID", socket.gethostname())
INTERVALO = float(os.environ.get("INTERVALO", "3"))
MODO = os.environ.get("MODO", "normal")


def _trabajo_cpu_intensivo():
    """Bucle ocupado que consume CPU real hasta que el proceso se termina."""
    x = 0.0001
    while True:
        for _ in range(200000):
            x = (x * 1.0000001) ** 1.0000001


def iniciar_carga():
    """
    Lanza varios subprocesos de trabajo (visibles como procesos reales en
    /proc dentro del contenedor) y reserva memoria real, para que las
    metricas leidas reflejen una anomalia genuina y no una etiqueta falsa.
    """
    n_workers = max(1, (os.cpu_count() or 2))
    procesos = []
    for _ in range(n_workers * 2):
        proc = multiprocessing.Process(target=_trabajo_cpu_intensivo, daemon=True)
        proc.start()
        procesos.append(proc)

    # Reserva de memoria real (se mantiene referenciada para que no se libere)
    global _bloque_memoria
    try:
        _bloque_memoria = bytearray(80 * 1024 * 1024)  # ~80 MB
        for i in range(0, len(_bloque_memoria), 4096):
            _bloque_memoria[i] = 1  # forzar paginas reales, no solo reservadas
    except MemoryError:
        _bloque_memoria = bytearray(10 * 1024 * 1024)

    print(f"[{CLIENT_ID}] Modo CARGA activo: {len(procesos)} procesos de trabajo "
          f"+ ~{len(_bloque_memoria)//(1024*1024)} MB reservados.", flush=True)
    return procesos


def enviar(metricas):
    payload = {"client_id": CLIENT_ID, **{k: v for k, v in metricas.items() if not k.startswith("_")}}
    try:
        with socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=3.0) as s:
            s.sendall(json.dumps(payload).encode("utf-8"))
            data = s.recv(4096)
            return json.loads(data.decode("utf-8"))
    except OSError as e:
        return {"error": str(e)}


def main():
    print(f"[{CLIENT_ID}] Iniciando cliente en modo '{MODO}', "
          f"enviando a {SERVER_HOST}:{SERVER_PORT} cada {INTERVALO}s", flush=True)

    if MODO == "carga":
        iniciar_carga()

    # Primera lectura de red se descarta (establece la linea base del contador)
    leer_metricas()
    time.sleep(1)

    while True:
        m = leer_metricas()
        resp = enviar(m)
        estado = "ERROR" if "error" in resp else ("ANOMALIA" if resp.get("es_anomalia") else "normal")
        print(
            f"[{CLIENT_ID}] cpu={m['cpu_percent']:.1f}% mem={m['mem_percent']:.1f}% "
            f"proc={m['proc_count']:.0f} net={m['net_kbps']:.1f}kbps "
            f"(fuente cpu={m['_fuente_cpu']}, mem={m['_fuente_mem']}) -> {estado} "
            f"{resp if 'error' in resp else ''}",
            flush=True,
        )
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
