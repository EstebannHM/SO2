"""
Lector de metricas del contenedor cliente.

Prioriza los contadores de cgroup (v2, con fallback a v1) porque son los
unicos que reportan el consumo REAL del propio contenedor: /proc/stat y
/proc/meminfo, dentro de un contenedor Docker estandar, casi siempre
reflejan al host completo (no estan namespaced), por lo que usarlos
directamente daria lecturas enganosas de "mi" CPU y memoria.
Si el entorno no expone cgroups (por ejemplo, fuera de un contenedor, o en
un entorno restringido), se hace fallback automatico a /proc a nivel de
host, dejando claro en el log cual fuente se esta usando.
"""
import os
import time

_fuente_cpu = None
_fuente_mem = None


def _leer(path):
    with open(path) as f:
        return f.read().strip()


# ---------------------- CPU ----------------------

def _cpu_cgroup_v2(intervalo):
    quota_txt, periodo_txt = _leer("/sys/fs/cgroup/cpu.max").split()
    periodo = int(periodo_txt)
    quota = None if quota_txt == "max" else int(quota_txt)

    def usage_usec():
        for linea in _leer("/sys/fs/cgroup/cpu.stat").splitlines():
            if linea.startswith("usage_usec"):
                return int(linea.split()[1])
        raise ValueError("usage_usec no encontrado")

    u1 = usage_usec()
    time.sleep(intervalo)
    u2 = usage_usec()
    delta_usec = u2 - u1

    capacidad_usec = (quota / periodo if quota else os.cpu_count()) * intervalo * 1e6
    return round(min(100.0, delta_usec / capacidad_usec * 100), 2)


def _cpu_cgroup_v1(intervalo):
    def usage_ns():
        return int(_leer("/sys/fs/cgroup/cpuacct/cpuacct.usage"))

    u1 = usage_ns()
    time.sleep(intervalo)
    u2 = usage_ns()
    delta_ns = u2 - u1
    capacidad_ns = os.cpu_count() * intervalo * 1e9
    return round(min(100.0, delta_ns / capacidad_ns * 100), 2)


def _cpu_proc_stat_host(intervalo):
    def snapshot():
        valores = list(map(int, _leer("/proc/stat").splitlines()[0].split()[1:]))
        return sum(valores), valores[3] + valores[4]

    t1, o1 = snapshot()
    time.sleep(intervalo)
    t2, o2 = snapshot()
    delta_total = t2 - t1
    delta_ocioso = o2 - o1
    if delta_total <= 0:
        return 0.0
    return round((1 - delta_ocioso / delta_total) * 100, 2)


def leer_cpu_percent(intervalo=0.4):
    global _fuente_cpu
    for nombre, fn in (("cgroup_v2", _cpu_cgroup_v2), ("cgroup_v1", _cpu_cgroup_v1),
                        ("proc_stat_host", _cpu_proc_stat_host)):
        try:
            valor = fn(intervalo)
            _fuente_cpu = nombre
            return valor
        except (FileNotFoundError, ValueError, ZeroDivisionError):
            continue
    _fuente_cpu = "no_disponible"
    return 0.0


# ---------------------- Memoria ----------------------

def _mem_cgroup_v2():
    usado = int(_leer("/sys/fs/cgroup/memory.current"))
    limite_txt = _leer("/sys/fs/cgroup/memory.max")
    if limite_txt == "max":
        raise ValueError("sin limite definido")
    limite = int(limite_txt)
    return round(usado / limite * 100, 2)


def _mem_cgroup_v1():
    usado = int(_leer("/sys/fs/cgroup/memory/memory.usage_in_bytes"))
    limite = int(_leer("/sys/fs/cgroup/memory/memory.limit_in_bytes"))
    if limite > 10 ** 15:
        raise ValueError("sin limite definido")
    return round(usado / limite * 100, 2)


def _mem_proc_meminfo_host():
    datos = {}
    for linea in _leer("/proc/meminfo").splitlines():
        clave, resto = linea.split(":", 1)
        datos[clave.strip()] = int(resto.strip().split()[0])
    total = datos["MemTotal"]
    disponible = datos.get("MemAvailable", datos["MemFree"])
    return round((1 - disponible / total) * 100, 2)


def leer_memoria():
    global _fuente_mem
    for nombre, fn in (("cgroup_v2", _mem_cgroup_v2), ("cgroup_v1", _mem_cgroup_v1),
                        ("proc_meminfo_host", _mem_proc_meminfo_host)):
        try:
            valor = fn()
            _fuente_mem = nombre
            return valor
        except (FileNotFoundError, ValueError, ZeroDivisionError, KeyError):
            continue
    _fuente_mem = "no_disponible"
    return 0.0


# ---------------------- Procesos y red ----------------------

def contar_procesos():
    return sum(1 for pid in os.listdir("/proc") if pid.isdigit())


def leer_red_bytes():
    total = 0
    for linea in _leer("/proc/net/dev").splitlines()[2:]:
        campos = linea.split(":")
        if len(campos) == 2:
            valores = campos[1].split()
            total += int(valores[0]) + int(valores[8])
    return total


_ultimo_red_bytes = None
_ultimo_red_t = None


def leer_metricas():
    global _ultimo_red_bytes, _ultimo_red_t

    cpu = leer_cpu_percent()
    mem = leer_memoria()
    proc = contar_procesos()

    ahora_bytes = leer_red_bytes()
    ahora_t = time.time()
    if _ultimo_red_bytes is None:
        net_kbps = 0.0
    else:
        delta_bytes = max(0, ahora_bytes - _ultimo_red_bytes)
        delta_t = max(0.001, ahora_t - _ultimo_red_t)
        net_kbps = round((delta_bytes / 1024) / delta_t, 2)
    _ultimo_red_bytes, _ultimo_red_t = ahora_bytes, ahora_t

    return {
        "cpu_percent": cpu,
        "mem_percent": mem,
        "proc_count": float(proc),
        "net_kbps": net_kbps,
        "_fuente_cpu": _fuente_cpu,
        "_fuente_mem": _fuente_mem,
    }
