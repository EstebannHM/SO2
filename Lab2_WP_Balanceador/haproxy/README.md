# Guía rápida de despliegue — Laboratorio WordPress HA

Todos los archivos de esta carpeta ya están armados según el taller.
Solo debes copiarlos a tu WSL y seguir estos pasos EN ORDEN.

## 0. Ubicación en tu WSL

Copia esta carpeta completa (menos README.md y mu-plugins/, ver paso 6) a:

    /home/cmendez/grafana/grafana/redis/web/haproxy

Estructura esperada:
    haproxy/
    ├── .env
    ├── compose.yaml
    ├── haproxy/haproxy.cfg
    └── web/
        ├── Dockerfile
        ├── docker-entrypoint.sh
        └── redis-session.ini

## 1. Verificar prerrequisitos

    docker --version
    docker compose version
    docker info
    getent passwd orh
    id orh
    sudo stat -c '%U:%G %u:%g %a %n' /home/orh

orh debe existir con UID:GID 1003:1003, dueño de /home/orh.

## 2. Proteger el .env

    cd /home/cmendez/grafana/grafana/redis/web/haproxy
    chmod 600 .env

## 3. Descargar WordPress como orh

    sudo chown -R orh:orh /home/orh
    sudo chmod 750 /home/orh
    sudo -u orh bash -c '
      curl -fsSL https://wordpress.org/latest.tar.gz |
      tar -xz --strip-components=1 -C /home/orh
    '
    sudo chown -R orh:orh /home/orh
    sudo find /home/orh -type d -exec chmod 750 {} \;
    sudo find /home/orh -type f -exec chmod 640 {} \;

## 4. Validar la configuración

    docker compose config
    docker run --rm \
      -v "$PWD/haproxy/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro" \
      haproxy:3.2-alpine \
      haproxy -c -f /usr/local/etc/haproxy/haproxy.cfg

## 5. Construir y levantar

    docker compose build --no-cache web1 web2
    docker compose up -d
    docker compose ps      # espera a que todo esté healthy

## 6. Instalar WordPress

Abre http://localhost:803 y completa el asistente con:
- Base de datos: mi_base_de_datos
- Usuario: usuario
- Contraseña: password
- Servidor: mariadb (NO localhost)

Luego protege wp-config.php:

    sudo chown orh:orh /home/orh/wp-config.php
    sudo chmod 600 /home/orh/wp-config.php

Y agrega antes de "That's all, stop editing!" las líneas de WP_HOME,
WP_SITEURL y Redis que están en la sección 18 del documento original.

## 7. Instalar Redis Object Cache

Desde wp-admin → Plugins → Añadir plugin → "Redis Object Cache" →
instalar y activar → Ajustes → Redis → Enable Object Cache.

## 8. Copiar el plugin indicador de backend

    sudo install -d -o orh -g orh -m 0750 /home/orh/wp-content/mu-plugins
    sudo cp mu-plugins/backend-indicator.php \
      /home/orh/wp-content/mu-plugins/backend-indicator.php
    sudo chown orh:orh /home/orh/wp-content/mu-plugins/backend-indicator.php
    sudo chmod 640 /home/orh/wp-content/mu-plugins/backend-indicator.php

## 9. Probar balanceo

    for i in $(seq 1 10); do
        printf "Solicitud %02d: " "$i"
        curl -sI -H 'Connection: close' "http://localhost:803/?probe=$i" \
        | awk -F': ' 'tolower($1)=="x-backend"{gsub("\r","",$2); print $2}'
    done

## 10. Probar tolerancia a fallos

    docker compose stop web1
    curl -sI http://localhost:803/ | grep -i x-backend   # debe ser web2
    docker compose start web1

    docker compose stop web2
    curl -sI http://localhost:803/ | grep -i x-backend   # debe ser web1
    docker compose start web2

## 11. Evidencias a capturar (sección 31 del documento)

Revisa la lista completa en el documento original: docker compose ps,
id www-data en ambos backends, propiedad de archivos, las 10 solicitudes
alternadas, capturas de HAProxy stats, Redis conectado, pruebas de fallo
de cada réplica y respuestas a las 16 preguntas de análisis (sección 32).
