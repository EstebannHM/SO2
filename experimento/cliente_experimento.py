"""
Orquesta el experimento completo:
1. Levanta el servidor (hilo) con el modelo Isolation Forest ya entrenado.
2. Lanza N clientes concurrentes (hilos) que envian metricas reales
   (sinteticas, con anomalias etiquetadas) via TCP.
3. Mide tiempo de respuesta por peticion (lado cliente) y throughput.
4. Compara predicciones del modelo contra las etiquetas reales
   (precision, recall, F1, exactitud).
5. Prueba adicional de tolerancia a fallos: se detiene el servidor a la
   mitad de una tanda de peticiones y se mide cuantas fallan / el tiempo
   de inactividad percibido por los clientes.
"""
import json
import socket
import threading
import time
import statistics as stats
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score

from monitor_common import generar_metricas, FEATURES
import server_experimento as srv_mod

HOST, PORT = srv_mod.HOST, srv_mod.PORT
N_CLIENTES = 20            # conexiones concurrentes simuladas
N_MUESTRAS = 400           # metricas totales a enviar
TASA_ANOMALIAS = 0.05


def enviar_metrica(client_id, seq, x_row, y_true, resultados):
    payload = {
        "client_id": client_id,
        "seq": seq,
        "y_true": int(y_true),
        **{f: float(v) for f, v in zip(FEATURES, x_row)},
    }
    t0 = time.perf_counter()
    try:
        with socket.create_connection((HOST, PORT), timeout=2.0) as s:
            s.sendall(json.dumps(payload).encode("utf-8"))
            data = s.recv(4096)
            t1 = time.perf_counter()
            resp = json.loads(data.decode("utf-8"))
            resultados.append({
                "ok": True,
                "y_true": int(y_true),
                "y_pred": resp["es_anomalia"],
                "latencia_ms": (t1 - t0) * 1000,
            })
    except (ConnectionRefusedError, socket.timeout, OSError):
        resultados.append({"ok": False, "y_true": int(y_true), "y_pred": None, "latencia_ms": None})


def experimento_concurrencia():
    X, y = generar_metricas(N_MUESTRAS, tasa_anomalias=TASA_ANOMALIAS, seed=7)

    listo_evt = threading.Event()
    detener_evt = threading.Event()
    hilo_srv = threading.Thread(
        target=srv_mod.iniciar_servidor, args=(N_MUESTRAS, listo_evt, detener_evt)
    )
    hilo_srv.start()
    listo_evt.wait(timeout=5)

    resultados = []
    lote = np.array_split(np.arange(N_MUESTRAS), N_CLIENTES)

    t_inicio = time.perf_counter()
    hilos = []
    for cid, indices in enumerate(lote):
        for seq in indices:
            h = threading.Thread(
                target=enviar_metrica,
                args=(cid, int(seq), X[seq], y[seq], resultados),
            )
            hilos.append(h)

    # Se lanzan en oleadas de N_CLIENTES para simular concurrencia real
    for i in range(0, len(hilos), N_CLIENTES):
        tanda = hilos[i:i + N_CLIENTES]
        for h in tanda:
            h.start()
        for h in tanda:
            h.join()
    t_fin = time.perf_counter()

    hilo_srv.join(timeout=10)

    duracion_total = t_fin - t_inicio
    exitosas = [r for r in resultados if r["ok"]]
    fallidas = [r for r in resultados if not r["ok"]]

    latencias = [r["latencia_ms"] for r in exitosas]
    y_true_arr = [r["y_true"] for r in exitosas]
    y_pred_arr = [r["y_pred"] for r in exitosas]

    reporte = {
        "peticiones_totales": len(resultados),
        "peticiones_exitosas": len(exitosas),
        "peticiones_fallidas": len(fallidas),
        "duracion_total_s": round(duracion_total, 4),
        "throughput_req_s": round(len(exitosas) / duracion_total, 2),
        "latencia_prom_ms": round(stats.mean(latencias), 4),
        "latencia_mediana_ms": round(stats.median(latencias), 4),
        "latencia_p95_ms": round(np.percentile(latencias, 95), 4),
        "latencia_max_ms": round(max(latencias), 4),
        "precision": round(precision_score(y_true_arr, y_pred_arr, zero_division=0), 4),
        "recall": round(recall_score(y_true_arr, y_pred_arr, zero_division=0), 4),
        "f1": round(f1_score(y_true_arr, y_pred_arr, zero_division=0), 4),
        "exactitud": round(accuracy_score(y_true_arr, y_pred_arr), 4),
        "n_clientes_concurrentes": N_CLIENTES,
    }
    return reporte


def experimento_tolerancia_fallos():
    """
    Mide el 'tiempo de inactividad' percibido: se levanta el servidor,
    se apaga a mitad de una tanda de peticiones, y se mide cuanto tardan
    los clientes en volver a recibir respuesta tras reiniciarlo.
    """
    listo_evt = threading.Event()
    detener_evt = threading.Event()
    hilo_srv = threading.Thread(
        target=srv_mod.iniciar_servidor, args=(10_000, listo_evt, detener_evt)
    )
    hilo_srv.start()
    listo_evt.wait(timeout=5)

    X, y = generar_metricas(10, tasa_anomalias=0.0, seed=3)
    resultados = []
    enviar_metrica("A", 0, X[0], y[0], resultados)

    t_caida = time.perf_counter()
    detener_evt.set()
    hilo_srv.join(timeout=5)

    # Intentos de reconexion mientras el servidor esta caido
    intentos_fallidos = 0
    while True:
        r = []
        enviar_metrica("A", 1, X[1], y[1], r)
        if r[0]["ok"]:
            break
        intentos_fallidos += 1
        if intentos_fallidos > 5:
            break
        time.sleep(0.3)
    t_deteccion_caida = time.perf_counter() - t_caida

    return {
        "intentos_fallidos_antes_de_detectar_caida": intentos_fallidos,
        "tiempo_hasta_fallo_detectado_s": round(t_deteccion_caida, 4),
    }


if __name__ == "__main__":
    print("=== Experimento 1: concurrencia, latencia y deteccion ===")
    r1 = experimento_concurrencia()
    for k, v in r1.items():
        print(f"{k}: {v}")

    print("\n=== Experimento 2: tolerancia a fallos / caida del servidor ===")
    r2 = experimento_tolerancia_fallos()
    for k, v in r2.items():
        print(f"{k}: {v}")
