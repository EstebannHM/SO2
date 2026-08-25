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

**1. ¿Por qué es relevante que `www-data` tenga UID 1003 dentro de ambos contenedores?**
 
Porque `/home/orh` es un *bind mount* del host, y los permisos de archivos en Linux se
resuelven por **número** de UID/GID, no por nombre. El nombre `www-data` solo existe
dentro del contenedor; en el host, ese archivo pertenece al usuario cuyo UID coincide
numéricamente. Si `www-data` no tuviera UID 1003, no podría leer ni escribir en los
archivos que pertenecen a `orh` (1003) en el host, sin importar que el nombre
"coincida" visualmente.
 
**2. ¿Qué ventaja ofrece ajustar el UID/GID en el `entrypoint` en lugar de
incorporarlo como `ARG` de construcción?**
 
Con `ARG` el UID quedaría "quemado" dentro de la imagen: cada vez que cambie el
propietario del volumen en el host habría que reconstruir la imagen. Ajustándolo en el
`entrypoint` (variables `APP_UID`/`APP_GID` leídas en tiempo de ejecución), la misma
imagen genérica sirve para cualquier host o cualquier propietario, solo cambiando el
`.env` y recreando el contenedor — sin reconstruir nada.
 
**3. ¿Qué ocurriría si `web1` utilizara UID 33 y `web2` UID 1003?**
 
Ambas réplicas escriben sobre el mismo volumen compartido, pero con identidades
distintas. Archivos creados por `web1` (UID 33, `www-data` por defecto de Debian)
quedarían inaccesibles o con permisos inconsistentes para `web2` (UID 1003), y
viceversa. Esto generaría errores intermitentes de `Permission denied` según qué
réplica atendiera cada solicitud, un tipo de fallo difícil de diagnosticar por ser
inconsistente.
 
**4. ¿Por qué Redis Object Cache no es, por sí solo, el responsable de mantener el
inicio de sesión nativo de WordPress?**
 
Redis Object Cache acelera consultas y objetos (por ejemplo, resultados de queries a
la base de datos), pero WordPress valida el login mediante una cookie firmada con
`AUTH_KEY`/`LOGGED_IN_KEY` y datos en la tabla `wp_usermeta` de MariaDB, no en Redis.
La sesión de autenticación depende de la base de datos compartida y de las claves
compartidas en `wp-config.php`, no del object cache.
 
**5. ¿Qué datos deben ser idénticos o compartidos para que cualquier réplica valide la
cookie de autenticación?**
 
El mismo `wp-config.php` (con las mismas `AUTH_KEY`, `LOGGED_IN_KEY` y demás *salts*),
la misma base de datos MariaDB, y el mismo `WP_HOME`/`WP_SITEURL`. Como ambos backends
leen literalmente el mismo archivo desde `/home/orh`, esto se cumple automáticamente
en este laboratorio.
 
**6. ¿Qué diferencia existe entre balanceo de carga y alta disponibilidad?**
 
El balanceo de carga distribuye solicitudes entre varios servidores para repartir
trabajo (aquí, `roundrobin`). La alta disponibilidad es la propiedad de que el
servicio siga funcionando aunque falle un componente. En este laboratorio, HAProxy
cumple ambas funciones: reparte tráfico en condiciones normales, y además redirige
todo a la réplica sana cuando la otra falla.
 
**7. ¿Por qué esta solución no es completamente tolerante a fallos?**
 
Porque MariaDB, Redis, HAProxy y el volumen `/home/orh` son puntos únicos de fallo
(SPOF). Solo se duplicaron las réplicas web (`web1`/`web2`); si cae MariaDB, Redis,
HAProxy o el host que aloja `/home/orh`, todo el sitio cae, sin importar cuántas
réplicas web existan.
 
**8. ¿Qué ocurre si falla MariaDB?**
 
Ambas réplicas web dejarían de poder servir contenido dinámico: WordPress mostraría el
error de conexión a la base de datos. Como solo hay una instancia de MariaDB, es un
punto único de fallo total para el sitio completo.
 
**9. ¿Qué ocurre si falla Redis? Distinga entre caché de objetos y sesiones PHP de
plugins.**
 
Como caché de objetos, WordPress está diseñado para degradarse con elegancia: si
Redis no responde, WordPress vuelve a consultar MariaDB directamente (más lento, pero
funcional). Como almacén de sesiones PHP (base lógica 1, para plugins que llaman
`session_start()`), un fallo de Redis sí interrumpiría esas sesiones específicas de
plugin, pero no afecta el login nativo de WordPress, que depende de cookies y de la
base de datos, no de sesiones PHP.
 
**10. ¿Qué limitación presenta `/home/orh` si las réplicas se trasladan a hosts
distintos?**
 
`/home/orh` es un directorio local del host: solo funciona porque `web1` y `web2`
corren en el mismo host y montan el mismo volumen. Si se trasladan a hosts diferentes,
cada uno vería un `/home/orh` distinto o vacío, rompiendo la consistencia de archivos.
Se necesitaría almacenamiento compartido en red (NFS, un *volume driver* distribuido,
o almacenamiento de objetos) en lugar de un *bind mount* local.
 
**11. ¿Qué función cumplen `fall 1` y `rise 2` en HAProxy?**
 
`fall 1` indica cuántos chequeos de salud fallidos consecutivos se necesitan para
marcar un servidor como `DOWN` (aquí, basta 1 fallo). `rise 2` indica cuántos
chequeos exitosos consecutivos se necesitan para volver a marcarlo como `UP` (aquí,
2 éxitos seguidos). Esto crea una asimetría intencional: se reacciona rápido ante
fallos, pero se exige más confirmación antes de reincorporar un servidor, evitando
reincorporarlo prematuramente si sigue inestable.
 
**12. ¿Por qué no se expone MariaDB ni Redis mediante `ports`?**
 
Porque ambos solo necesitan ser accesibles dentro de la red interna `webnet` por
`web1` y `web2`. Publicarlos con `ports` los expondría también en la interfaz de red
del host, aumentando la superficie de ataque sin ningún beneficio funcional.
 
**13. ¿Qué riesgo representa que un usuario pertenezca al grupo `docker`?**
 
Pertenecer al grupo `docker` equivale, en la práctica, a tener privilegios de root
sobre el host: cualquier usuario en ese grupo puede montar cualquier ruta del sistema
de archivos (por ejemplo, `/`) dentro de un contenedor y modificarla libremente, sin
pasar por `sudo`. Es un mecanismo de escalamiento de privilegios si no se controla
cuidadosamente quién pertenece a ese grupo.
 
**14. ¿Por qué una solicitud que estaba en ejecución podría fallar aunque exista otra
réplica?**
 
Porque HAProxy solo puede redirigir nuevas solicitudes al backend sano. Una solicitud
que ya estaba en curso hacia el backend que falló se pierde junto con esa conexión
TCP; no hay forma de "reanudarla" en otro servidor sin lógica adicional de reintento
en el cliente.
 
**15. ¿Qué componentes deberían duplicarse para eliminar los puntos únicos de
fallo?**
 
MariaDB (con replicación maestro-réplica o un clúster tipo Galera), Redis (con Redis
Sentinel o Redis Cluster), y el propio HAProxy (con un mecanismo de *failover*, como
Keepalived más una IP virtual, para que no sea en sí mismo un punto único de fallo).
También el almacenamiento de `/home/orh` debería pasar de un *bind mount* local a un
sistema de archivos distribuido.
 
**16. ¿Cómo cambiaría este laboratorio al implementarlo en Docker Swarm o
Kubernetes?**
 
En vez de comandos manuales (`docker compose exec`/`stop`/`start`), el propio
orquestador detectaría fallos de contenedor mediante *health checks* nativos y
recrearía automáticamente las réplicas caídas, sin intervención manual. El volumen
`/home/orh` tendría que convertirse en almacenamiento distribuido (por ejemplo, un
`PersistentVolume` respaldado por NFS o almacenamiento en la nube), y el balanceo
pasaría de HAProxy manual a un `Service`/`Ingress` de Kubernetes o al *routing mesh*
nativo de Swarm, que ya manejan el descubrimiento de servicios automáticamente.
