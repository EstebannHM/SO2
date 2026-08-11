"""
Lector real de metricas desde el sistema de archivos /proc de Linux.
Esto demuestra la lectura de bajo nivel exigida por el objetivo especifico 2
del proyecto. Se usa de forma independiente al experimento controlado
(que usa datos sinteticos para poder etiquetar anomalias con certeza).
"""
import time


def leer_cpu_percent(intervalo=0.4):
    def snapshot():
        with open("/proc/stat") as f:
            partes = f.readline().split()[1:]
        valores = list(map(int, partes))
        ocioso = valores[3] + valores[4]
        total = sum(valores)
        return total, ocioso

    t1, o1 = snapshot()
    time.sleep(intervalo)
    t2, o2 = snapshot()
    delta_total = t2 - t1
    delta_ocioso = o2 - o1
    if delta_total == 0:
        return 0.0
    return round((1 - delta_ocioso / delta_total) * 100, 2)


def leer_memoria():
    datos = {}
    with open("/proc/meminfo") as f:
        for linea in f:
            clave, resto = linea.split(":", 1)
            datos[clave.strip()] = int(resto.strip().split()[0])  # kB
    total = datos["MemTotal"]
    disponible = datos.get("MemAvailable", datos["MemFree"])
    uso_pct = round((1 - disponible / total) * 100, 2)
    return uso_pct, total, disponible


def contar_procesos():
    import os
    return sum(1 for p in os.listdir("/proc") if p.isdigit())


def leer_red():
    total_bytes = 0
    with open("/proc/net/dev") as f:
        lineas = f.readlines()[2:]
    for linea in lineas:
        campos = linea.split(":")
        if len(campos) == 2:
            valores = campos[1].split()
            rx_bytes = int(valores[0])
            tx_bytes = int(valores[8])
            total_bytes += rx_bytes + tx_bytes
    return total_bytes


if __name__ == "__main__":
    cpu = leer_cpu_percent()
    mem_pct, mem_total, mem_disp = leer_memoria()
    n_proc = contar_procesos()
    red_bytes = leer_red()
    print(f"CPU uso: {cpu} %")
    print(f"Memoria uso: {mem_pct} %  (total={mem_total} kB, disponible={mem_disp} kB)")
    print(f"Procesos activos: {n_proc}")
    print(f"Bytes de red acumulados (rx+tx, todas las interfaces): {red_bytes}")
