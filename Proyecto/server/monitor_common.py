"""
Modulo compartido: generacion de metricas de arranque (bootstrap) para
entrenar el modelo, y utilidades comunes de features.
Se usa tanto en el servidor (para el entrenamiento inicial) como para
mantener consistencia en el orden de las features.
"""
import numpy as np

FEATURES = ["cpu_percent", "mem_percent", "proc_count", "net_kbps"]


def generar_bootstrap_normal(n_muestras=600, seed=1):
    """
    Genera un lote de metricas 'normales' para entrenar el modelo al
    arrancar el servidor. Calibrado a partir de lecturas reales de
    client-normal corriendo en Docker (ver docs/validacion_local.md):
    un contenedor Python en reposo, con memory_limit=128m, reporta en la
    practica cpu~0%, mem~8%, 1 proceso (PID namespace aislado) y trafico
    de red minimo (solo el envio periodico de metricas). La calibracion
    anterior (basada en una estimacion generica de "servidor liviano")
    quedaba demasiado lejos de estos valores reales y el modelo
    terminaba marcando al cliente normal como anomalia.
    """
    rng = np.random.default_rng(seed)
    cpu = np.clip(rng.normal(1.0, 1.2, n_muestras), 0, 100)
    mem = np.clip(rng.normal(9, 2.5, n_muestras), 0, 100)
    proc = np.clip(rng.poisson(0.4, n_muestras) + 1, 1, None)
    net = np.clip(rng.normal(1.0, 1.0, n_muestras), 0, None)
    return np.column_stack([cpu, mem, proc, net])
