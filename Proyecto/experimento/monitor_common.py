"""
Modulo compartido: generacion sintetica de metricas de sistema operativo
(simulando lecturas de /proc) con inyeccion de anomalias etiquetadas,
para poder evaluar objetivamente el detector de anomalias.
"""
import numpy as np

FEATURES = ["cpu_percent", "mem_percent", "proc_count", "net_kbps"]

def generar_metricas(n_muestras, tasa_anomalias=0.05, seed=None):
    """
    Genera n_muestras de metricas tipo /proc (cpu, memoria, procesos, red).
    Devuelve (X, y) donde y=1 indica anomalia inyectada (ground truth).
    """
    rng = np.random.default_rng(seed)
    n_anom = max(1, int(n_muestras * tasa_anomalias))
    n_norm = n_muestras - n_anom

    # Comportamiento normal del sistema (carga habitual de un servidor)
    cpu_n = np.clip(rng.normal(35, 8, n_norm), 1, 100)
    mem_n = np.clip(rng.normal(50, 10, n_norm), 1, 100)
    proc_n = np.clip(rng.poisson(120, n_norm), 40, None)
    net_n = np.clip(rng.normal(500, 150, n_norm), 10, None)

    # Anomalias: picos de CPU, fugas de memoria, explosion de procesos
    # o trafico de red anomalo (simulando ataques o procesos fuera de control)
    tipo = rng.integers(0, 4, n_anom)
    cpu_a = np.where(tipo == 0, rng.normal(93, 4, n_anom), rng.normal(35, 8, n_anom))
    mem_a = np.where(tipo == 1, rng.normal(95, 3, n_anom), rng.normal(50, 10, n_anom))
    proc_a = np.where(tipo == 2, rng.normal(420, 35, n_anom), rng.poisson(120, n_anom))
    net_a = np.where(tipo == 3, rng.normal(3200, 400, n_anom), rng.normal(500, 150, n_anom))

    cpu = np.concatenate([cpu_n, np.clip(cpu_a, 1, 100)])
    mem = np.concatenate([mem_n, np.clip(mem_a, 1, 100)])
    proc = np.concatenate([proc_n, np.clip(proc_a, 40, None)])
    net = np.concatenate([net_n, np.clip(net_a, 10, None)])
    y = np.concatenate([np.zeros(n_norm, dtype=int), np.ones(n_anom, dtype=int)])

    X = np.column_stack([cpu, mem, proc, net])
    idx = rng.permutation(n_muestras)
    return X[idx], y[idx]
