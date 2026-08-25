package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

func main() {
	serverName := os.Getenv("SERVER_NAME")

	if serverName == "" {
		serverName = "Servidor"
	}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {

		w.Header().Set("Content-Type", "text/html; charset=utf-8")

		fmt.Fprintf(w, `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>HTTP Proxy Cache</title>

<style>

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: Arial, Helvetica, sans-serif;
    min-height: 100vh;
    background: linear-gradient(135deg, #0f172a, #1e3a8a);
    color: white;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 30px;
}

.container {
    width: 100%%;
    max-width: 1000px;
}

.header {
    text-align: center;
    margin-bottom: 30px;
}

.header h1 {
    font-size: 38px;
    margin-bottom: 10px;
}

.header p {
    color: #cbd5e1;
    font-size: 17px;
}

.card {
    background: rgba(255,255,255,0.96);
    color: #1e293b;
    border-radius: 20px;
    padding: 35px;
    box-shadow: 0 20px 50px rgba(0,0,0,0.35);
}

.status {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 30px;
    font-weight: bold;
}

.dot {
    width: 14px;
    height: 14px;
    background: #22c55e;
    border-radius: 50%%;
    box-shadow: 0 0 12px #22c55e;
}

.grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-bottom: 30px;
}

.info {
    background: #f1f5f9;
    border-radius: 15px;
    padding: 25px;
    text-align: center;
    border: 1px solid #e2e8f0;
}

.info h3 {
    color: #64748b;
    font-size: 14px;
    text-transform: uppercase;
    margin-bottom: 10px;
}

.info .value {
    font-size: 27px;
    font-weight: bold;
    color: #1e3a8a;
}

.section {
    margin-top: 25px;
}

.section h2 {
    font-size: 20px;
    margin-bottom: 15px;
    color: #0f172a;
}

.features {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}

.feature {
    background: #eff6ff;
    border-left: 5px solid #2563eb;
    padding: 15px;
    border-radius: 8px;
}

.footer {
    text-align: center;
    margin-top: 25px;
    color: #64748b;
    font-size: 13px;
}

.badge {
    display: inline-block;
    padding: 8px 15px;
    border-radius: 20px;
    background: #dbeafe;
    color: #1d4ed8;
    font-weight: bold;
}

@media(max-width: 700px) {

    .grid {
        grid-template-columns: 1fr;
    }

    .features {
        grid-template-columns: 1fr;
    }

    .header h1 {
        font-size: 28px;
    }

    .card {
        padding: 25px;
    }
}

</style>

</head>

<body>

<div class="container">

    <div class="header">

        <h1>HTTP Proxy con Caché</h1>

        <p>
            Sistema de intermediación, balanceo y almacenamiento temporal
            de respuestas HTTP
        </p>

    </div>

    <div class="card">

        <div class="status">

            <span class="dot"></span>

            Sistema operativo

            <span class="badge">
                HTTP / TCP
            </span>

        </div>

        <div class="grid">

            <div class="info">

                <h3>Servidor Backend</h3>

                <div class="value">
                    %s
                </div>

            </div>

            <div class="info">

                <h3>Ruta solicitada</h3>

                <div class="value" style="font-size:20px;">
                    %s
                </div>

            </div>

            <div class="info">

                <h3>Estado</h3>

                <div class="value" style="color:#16a34a;">
                    ONLINE
                </div>

            </div>

        </div>

        <div class="section">

            <h2>Componentes del proyecto</h2>

            <div class="features">

                <div class="feature">
                    <strong>Proxy HTTP</strong><br>
                    Recibe y procesa las solicitudes de los clientes.
                </div>

                <div class="feature">
                    <strong>Caché</strong><br>
                    Almacena respuestas para reducir solicitudes al backend.
                </div>

                <div class="feature">
                    <strong>Round Robin</strong><br>
                    Distribuye las solicitudes entre los servidores disponibles.
                </div>

                <div class="feature">
                    <strong>Failover</strong><br>
                    Busca automáticamente otro servidor cuando uno no está disponible.
                </div>

                <div class="feature">
                    <strong>Concurrencia</strong><br>
                    Atiende múltiples clientes utilizando goroutines de Go.
                </div>

                <div class="feature">
                    <strong>Estadísticas</strong><br>
                    Permite consultar HIT, MISS y tiempos de respuesta.
                </div>

            </div>

        </div>

        <div class="section">

            <h2>Información de la solicitud</h2>

            <p>
                <strong>Método:</strong> %s
            </p>

            <p style="margin-top:8px;">
                <strong>Hora:</strong> %s
            </p>

        </div>

        <div class="footer">

            Proyecto académico — Proxy HTTP con Caché

        </div>

    </div>

</div>

</body>
</html>`,
			serverName,
			r.URL.Path,
			r.Method,
			time.Now().Format("02/01/2006 15:04:05"),
		)
	})

	log.Printf("Servidor %s escuchando en :8080", serverName)

	log.Fatal(http.ListenAndServe(":8080", nil))
}
