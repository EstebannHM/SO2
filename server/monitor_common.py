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
    arrancar el servidor. Los valores estan calibrados para representar
    un contenedor Python liviano en reposo (no un servidor fisico
    completo), ya que los clientes reales de este despliegue son
    contenedores Docker con limite de memoria acotado (ver
    docker-compose.yml): CPU baja, memoria en torno a 10-20% de un
    limite de ~128 MB, pocos procesos (el propio interprete y quizas
    algun hilo/subproceso auxiliar) y trafico de red minimo (solo el
    envio periodico de metricas).
    """
    rng = np.random.default_rng(seed)
    cpu = np.clip(rng.normal(5, 3, n_muestras), 0, 100)
    mem = np.clip(rng.normal(15, 6, n_muestras), 0, 100)
    proc = np.clip(rng.poisson(4, n_muestras) + 1, 1, None)
    net = np.clip(rng.normal(3, 2, n_muestras), 0, None)
    return np.column_stack([cpu, mem, proc, net])
