"""
Servidor de monitoreo (servicio persistente para despliegue en Docker).

A diferencia de server.py usado en el experimento del informe (que atiende
un numero fijo de peticiones y termina), este servidor corre de forma
indefinida, tal como lo haria en un despliegue real: entrena el modelo al
arrancar y luego queda escuchando conexiones de cualquier cantidad de
agentes/clientes, atendiendolos concurrentemente con threads.

Variables de entorno:
  HOST            direccion de escucha (default 0.0.0.0)
  PORT            puerto de escucha (default 9099)
  CONTAMINATION   tasa de anomalias esperada por el modelo (default 0.05)
  BOOTSTRAP_N     tamano del lote de entrenamiento inicial (default 600)
"""
import json
import os
import socket
import threading
import time
from datetime import datetime

import numpy as np
from sklearn.ensemble import IsolationForest

from monitor_common import generar_bootstrap_normal, FEATURES

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "9099"))
CONTAMINATION = float(os.environ.get("CONTAMINATION", "0.05"))
BOOTSTRAP_N = int(os.environ.get("BOOTSTRAP_N", "600"))

log_lock = threading.Lock()


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    with log_lock:
        print(f"[{ts}] {msg}", flush=True)


def entrenar_modelo():
    log(f"Entrenando Isolation Forest con {BOOTSTRAP_N} muestras de arranque "
        f"(contaminacion={CONTAMINATION}) ...")
    X = generar_bootstrap_normal(BOOTSTRAP_N)
    modelo = IsolationForest(n_estimators=150, contamination=CONTAMINATION, random_state=42)
    modelo.fit(X)
    log("Modelo entrenado y listo para recibir metricas.")
    return modelo


def atender_cliente(conn, addr, modelo):
    t0 = time.perf_counter()
    try:
        data = conn.recv(4096)
        if not data:
            return
        payload = json.loads(data.decode("utf-8"))
        cliente_id = payload.get("client_id", str(addr))
        x = np.array([[payload[f] for f in FEATURES]])

        pred = modelo.predict(x)[0]
        score = float(modelo.decision_function(x)[0])
        es_anomalia = pred == -1

        respuesta = {"es_anomalia": bool(es_anomalia), "score": round(score, 5)}
        conn.sendall(json.dumps(respuesta).encode("utf-8"))
        latencia_ms = (time.perf_counter() - t0) * 1000

        etiqueta = "ANOMALIA DETECTADA" if es_anomalia else "normal"
        log(
            f"cliente={cliente_id:<14} cpu={payload['cpu_percent']:.1f}% "
            f"mem={payload['mem_percent']:.1f}% proc={payload['proc_count']:.0f} "
            f"net={payload['net_kbps']:.0f}kbps -> {etiqueta} "
            f"(score={score:.4f}, {latencia_ms:.1f} ms)"
        )
    except (ConnectionResetError, json.JSONDecodeError, KeyError) as e:
        log(f"Peticion invalida de {addr}: {e}")
    finally:
        conn.close()


def main():
    modelo = entrenar_modelo()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(128)
    log(f"Servidor de monitoreo escuchando en {HOST}:{PORT}")

    try:
        while True:
            conn, addr = srv.accept()
            hilo = threading.Thread(target=atender_cliente, args=(conn, addr, modelo), daemon=True)
            hilo.start()
    except KeyboardInterrupt:
        log("Apagando servidor...")
    finally:
        srv.close()


if __name__ == "__main__":
    main()
