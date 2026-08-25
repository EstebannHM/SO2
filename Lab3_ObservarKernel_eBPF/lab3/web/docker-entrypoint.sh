#!/usr/bin/env bash
set -Eeuo pipefail

APP_UID="${APP_UID:-33}"
APP_GID="${APP_GID:-33}"

error() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

case "${APP_UID}" in
    ''|*[!0-9]*)
        error "APP_UID debe ser un entero positivo."
        ;;
esac

case "${APP_GID}" in
    ''|*[!0-9]*)
        error "APP_GID debe ser un entero positivo."
        ;;
esac

if [ "$(id -u)" -ne 0 ]; then
    error "El contenedor debe iniciar como root para ajustar www-data."
fi

if ! id www-data >/dev/null 2>&1; then
    error "No existe el usuario interno www-data."
fi

current_uid="$(id -u www-data)"
current_gid="$(id -g www-data)"

uid_owner="$(
    getent passwd "${APP_UID}" |
    cut -d: -f1 ||
    true
)"

gid_owner="$(
    getent group "${APP_GID}" |
    cut -d: -f1 ||
    true
)"

if [ -n "${uid_owner}" ] && [ "${uid_owner}" != "www-data" ]; then
    error "El UID ${APP_UID} ya pertenece a ${uid_owner} dentro del contenedor."
fi

if [ -n "${gid_owner}" ] && [ "${gid_owner}" != "www-data" ]; then
    error "El GID ${APP_GID} ya pertenece al grupo ${gid_owner} dentro del contenedor."
fi

if [ "${current_gid}" != "${APP_GID}" ]; then
    groupmod --gid "${APP_GID}" www-data
fi

if [ "${current_uid}" != "${APP_UID}" ] || \
   [ "${current_gid}" != "${APP_GID}" ]; then
    usermod \
        --uid "${APP_UID}" \
        --gid "${APP_GID}" \
        www-data
fi

# Solo se preparan directorios internos de ejecución.
# No se cambia recursivamente la propiedad de /var/www/html.
install -d \
    -o www-data \
    -g www-data \
    -m 0755 \
    /var/run/apache2 \
    /var/lock/apache2

printf \
    'Iniciando Apache: www-data usa UID=%s GID=%s\n' \
    "$(id -u www-data)" \
    "$(id -g www-data)"

exec docker-php-entrypoint "$@"
