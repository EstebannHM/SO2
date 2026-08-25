# Laboratorio 2 — WordPress en Alta Disponibilidad con Docker, HAProxy y Redis

**Curso:** Sistemas Operativos 2
**Estudiante:** Esteban Hernández

Este documento presenta la evidencia del despliegue del laboratorio: un sitio WordPress
servido por dos réplicas web (`web1` y `web2`) balanceadas por HAProxy, con base de
datos MariaDB, caché de objetos en Redis, y gestión dinámica de UID/GID mediante un
`entrypoint` personalizado.

> Las imágenes referenciadas en este documento deben ubicarse en la carpeta
> `evidencias/` al mismo nivel que este archivo `.md`. Si usas otro nombre de carpeta,
> ajusta las rutas de las imágenes en consecuencia.

---

## 1. Preparación del entorno

### 1.1 Creación del usuario `orh` (UID/GID 1003:1003)

Se creó el usuario de sistema `orh`, propietario de `/home/orh`, que es el directorio
compartido entre ambas réplicas web.

![Creación de usuario orh y verificación de /home/orh](evidencias/crearPerfilyVerificarHome.png)

### 1.2 Protección del `.env` y descarga de WordPress

Se protegió el archivo `.env` (`chmod 600`) y se descargó WordPress directamente como
el usuario `orh`, aplicando después los permisos `750` para directorios y `640` para
archivos.

![Protección de .env y descarga de WordPress como orh](evidencias/protegerEnvyDescargarWP.png)

---

## 2. Despliegue de los contenedores

### 2.1 Construcción y levantamiento con `docker compose up -d`

Se construyó la imagen genérica `wordpress-ha-php:8.3` (compartida por `web1` y
`web2`) y se levantaron todos los servicios: `mariadb`, `redis`, `web1`, `web2` y
`haproxy`.

![docker compose up -d levantando todos los servicios](evidencias/dockercomposeup.png)

### 2.2 Verificación de identidades UID/GID dentro de los contenedores

Se confirmó que el usuario `www-data` dentro de ambos backends fue reasignado
dinámicamente por el `entrypoint` al UID/GID `1003:1003`, coincidiendo con el
propietario del bind mount `/home/orh` en el host.

![Verificación de id www-data en web1 y web2, y logs del entrypoint](evidencias/verificaciondeidentidades.png)

---

## 3. Instalación de WordPress

### 3.1 Asistente de instalación

Se accedió a `http://localhost:803` y se completó el asistente de instalación de
WordPress, configurando la conexión a la base de datos `mi_base_de_datos` en el host
`mariadb`.

![Pantalla inicial del instalador de WordPress](evidencias/instalarwp.png)

### 3.2 Panel de administración (Dashboard)

Una vez completada la instalación, se accedió al panel de administración de
WordPress.

![Dashboard de WordPress ya instalado](evidencias/dashboardWP.png)

---

## 4. Configuración de Redis Object Cache

Se instaló y activó el plugin **Redis Object Cache**, conectándolo al servicio
`redis` del stack. El estado de conexión confirma `Connected`, cliente `PhpRedis`, y
sistema de archivos escribible.

![Activación y estado de Redis Object Cache](evidencias/activarredis.png)

---

## 5. Verificación de HAProxy

### 5.1 Resolución del error inicial `503 Service Unavailable`

Durante las primeras pruebas, HAProxy marcó ambos backends como `DOWN` con el motivo
`Layer7 wrong status, code: 302`. Esto ocurrió porque, antes de completar la
instalación de WordPress, `wp-login.php` respondía con una redirección `302` hacia
`/wp-admin/setup-config.php` (WordPress aún no tenía `wp-config.php`), mientras que el
chequeo de salud de HAProxy exigía estrictamente un código `200`.

**Solución aplicada:** se ajustó el `http-check` en `haproxy.cfg` para aceptar tanto
`200` como `302` mediante `http-check expect rstatus ^(200|302)$`, permitiendo que los
backends quedaran disponibles incluso antes de finalizar la instalación de WordPress.

### 5.2 Panel de estadísticas con ambos backends `UP`

Tras el ajuste, el panel de estadísticas de HAProxy (`http://localhost:8404/stats`)
muestra `web1` y `web2` en estado `UP`.

![Panel de estadísticas de HAProxy con web1 y web2 en verde/UP](evidencias/statspuertomuestraup.png)

---

## 6. Prueba de balanceo de carga

### 6.1 Comprobación por línea de comandos

Se realizaron 10 solicitudes consecutivas con `curl`, cada una con `Connection:
close` para forzar una nueva conexión TCP, confirmando la alternancia `roundrobin`
entre `web1` y `web2`.

![10 solicitudes alternando entre web1 y web2](evidencias/pruebaBalanzaCarga.png)

### 6.2 Comprobación visual mediante el indicador de backend

Se instaló un *mu-plugin* que expone en la barra de administración de WordPress el
nombre del backend que atendió la solicitud (variable de entorno `BACKEND_NAME`).
Recargando el panel de administración se observó la alternancia entre ambas réplicas
sin pérdida de la sesión autenticada.

**Backend web1:**

![Barra de administración indicando Backend: web1](evidencias/backend1.png)

**Backend web2:**

![Barra de administración indicando Backend: web2](evidencias/backend2.png)

---

## 7. Conclusiones

- El `entrypoint` personalizado permitió alinear el UID/GID de `www-data` dentro de
  los contenedores con el propietario real del volumen en el host (`orh`, 1003:1003),
  evitando problemas de permisos sin necesidad de ejecutar los contenedores como
  `root` en tiempo de ejecución de Apache.
- HAProxy distribuyó correctamente el tráfico entre `web1` y `web2` en modo
  `roundrobin`, confirmado tanto por línea de comandos como visualmente.
- Redis funcionó correctamente como backend de caché de objetos de WordPress.
- Se identificó y resolvió un problema real de interacción entre el *health check* de
  HAProxy y el flujo de instalación inicial de WordPress (ver sección 5.1), evidencia
  de comprensión práctica del comportamiento de los chequeos de salud en un balanceador
  de capa 7.
- Al detener manualmente `web1` o `web2`, el tráfico se redirigió automáticamente al
  backend restante sin interrumpir la sesión autenticada del usuario, demostrando
  tolerancia a fallos a nivel de aplicación.

---

## Anexo — Preguntas de análisis

*(Completar según la sección 32 del documento de la guía del laboratorio.)*
