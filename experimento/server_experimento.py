"""
Servidor de monitoreo (prototipo).
- Fase de entrenamiento: recibe un lote inicial (bootstrap) de metricas
  consideradas normales y ajusta un modelo Isolation Forest.
- Fase de deteccion: por cada conexion de cliente, recibe una metrica
  (JSON), la evalua con el modelo y responde con el veredicto
  (normal/anomalo) y el score de anomalia.
Se registra el tiempo de respuesta de cada peticion en server_log.csv
"""
import json
import socket
import threading
import time
import csv
import numpy as np
from sklearn.ensemble import IsolationForest
from monitor_common import generar_metricas, FEATURES

HOST, PORT = "127.0.0.1", 9099
BOOTSTRAP_N = 600          # tamano del lote de entrenamiento (asumido normal)
CONTAMINATION = 0.05        # tasa de anomalias esperada

log_lock = threading.Lock()
log_rows = []


def entrenar_modelo():
    X_bootstrap, _ = generar_metricas(BOOTSTRAP_N, tasa_anomalias=0.0, seed=1)
    modelo = IsolationForest(
        n_estimators=150,
        contamination=CONTAMINATION,
        random_state=42,
    )
    modelo.fit(X_bootstrap)
    return modelo


def atender_cliente(conn, addr, modelo):
    t_recibido = time.perf_counter()
    try:
        data = conn.recv(4096)
        if not data:
            return
        payload = json.loads(data.decode("utf-8"))
        x = np.array([[payload[f] for f in FEATURES]])

        pred = modelo.predict(x)[0]          # -1 = anomalia, 1 = normal
        score = float(modelo.decision_function(x)[0])
        es_anomalia = 1 if pred == -1 else 0

        respuesta = {
            "es_anomalia": es_anomalia,
            "score": round(score, 5),
        }
        conn.sendall(json.dumps(respuesta).encode("utf-8"))
        t_respondido = time.perf_counter()

        with log_lock:
            log_rows.append({
                "client_id": payload.get("client_id"),
                "seq": payload.get("seq"),
                "y_true": payload.get("y_true"),
                "es_anomalia_pred": es_anomalia,
                "score": score,
                "tiempo_respuesta_ms": round((t_respondido - t_recibido) * 1000, 4),
            })
    except (ConnectionResetError, json.JSONDecodeError):
        pass
    finally:
        conn.close()


def iniciar_servidor(n_peticiones_esperadas, listo_evt, detener_evt):
    modelo = entrenar_modelo()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(128)
    srv.settimeout(0.5)
    listo_evt.set()

    atendidas = 0
    while atendidas < n_peticiones_esperadas and not detener_evt.is_set():
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            continue
        hilo = threading.Thread(target=atender_cliente, args=(conn, addr, modelo))
        hilo.start()
        atendidas += 1

    time.sleep(1.0)  # margen para que terminen los hilos en vuelo
    srv.close()

    with open("server_log.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "client_id", "seq", "y_true", "es_anomalia_pred", "score", "tiempo_respuesta_ms"
        ])
        writer.writeheader()
        for row in log_rows:
            writer.writerow(row)
