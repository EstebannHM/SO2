package main

import (
	"fmt"
	"io"
	"log"
	"net"
	"strings"
	"sync"
	"time"
)

var (
	servers = []string{
		"server1:8080",
		"server2:8080",
		"server3:8080",
	}

	currentServer = 0

	serverMu sync.Mutex

	cache   = make(map[string][]byte)
	cacheMu sync.RWMutex

	totalRequests int64
	cacheHits     int64
	cacheMisses   int64

	totalResponseTime time.Duration
	maxResponseTime   time.Duration

	statsMu sync.Mutex
)

const (
	maxRequestSize    = 8192
	connectionTimeout = 1 * time.Second
	serverTimeout = 1 * time.Second
)

func getServer() string {
	serverMu.Lock()
	defer serverMu.Unlock()

	server := servers[currentServer]

	currentServer = (currentServer + 1) % len(servers)

	return server
}

// failover automatico
func connectToServer() (net.Conn, string, error) {
	serverMu.Lock()

	start := currentServer

	serverMu.Unlock()

	for i := 0; i < len(servers); i++ {

		serverMu.Lock()

		index := (start + i) % len(servers)
		serverAddress := servers[index]

		currentServer = (index + 1) % len(servers)

		serverMu.Unlock()

		log.Printf("Intentando conectar a %s", serverAddress)

		server, err := net.DialTimeout(
			"tcp",
			serverAddress,
			serverTimeout,
		)

		if err == nil {
			log.Printf("Servidor disponible: %s", serverAddress)
			return server, serverAddress, nil
		}

		log.Printf(
			"Servidor no disponible: %s - %v",
			serverAddress,
			err,
		)
	}

	return nil, "", fmt.Errorf("ningún servidor backend disponible")
}

func recordResponseTime(duration time.Duration) {
	statsMu.Lock()
	defer statsMu.Unlock()

	totalResponseTime += duration

	if duration > maxResponseTime {
		maxResponseTime = duration
	}
}

func handleClient(client net.Conn) {

	defer client.Close()

	start := time.Now()

	buffer := make([]byte, maxRequestSize)

	//evita que un cliente pueda mantener un conexion abierto indefinidamente
	client.SetReadDeadline(time.Now().Add(connectionTimeout))

	n, err := client.Read(buffer)

	if err != nil {
		log.Println("Error leyendo solicitud:", err)
		return
	}

	request := string(buffer[:n])

	lines := strings.Split(request, "\r\n")

	if len(lines) == 0 {
		return
	}

	parts := strings.Split(lines[0], " ")

	if len(parts) < 2 {
		return
	}

	method := parts[0]
	path := parts[1]

	//proxy solo permite metodo get
	if method != "GET" {
		response := "HTTP/1.1 405 Method Not Allowed\r\n" +
			"Content-Type: text/plain\r\n" +
			"Connection: close\r\n" +
			"\r\n" +
			"Método HTTP no permitido"

		client.Write([]byte(response))

		log.Printf("Método rechazado: %s %s", method, path)

		return
	}

	//proteccion rutas grandes
	if len(path) > 2048 {
		response := "HTTP/1.1 414 URI Too Long\r\n" +
			"Content-Type: text/plain\r\n" +
			"Connection: close\r\n" +
			"\r\n" +
			"URI demasiado larga"

		client.Write([]byte(response))

		log.Printf("URI rechazada por tamaño: %d bytes", len(path))

		return
	}

	// /stats no cuenta como solicitud HTTP cacheable.
	if path == "/stats" {
		showStats(client)
		return
	}

	statsMu.Lock()
	totalRequests++
	statsMu.Unlock()

	// Solo cacheamos solicitudes GET.
	if method == "GET" {

		cacheMu.RLock()

		cachedResponse, found := cache[path]

		cacheMu.RUnlock()

		if found {

			statsMu.Lock()
			cacheHits++
			statsMu.Unlock()

			log.Printf("CACHE HIT: %s", path)

			client.Write(cachedResponse)

			recordResponseTime(time.Since(start))

			return
		}

		statsMu.Lock()
		cacheMisses++
		statsMu.Unlock()

		log.Printf("CACHE MISS: %s", path)
	}

	// Seleccionar servidor mediante round-robin.
	server, _, err := connectToServer()

	if err != nil {
		log.Println("ERROR:", err)

		response := "HTTP/1.1 503 Service Unavailable\r\n" +
			"Content-Type: text/plain\r\n" +
			"Connection: close\r\n" +
			"\r\n" +
			"No hay servidores disponibles"

		client.Write([]byte(response))
		return
	}

	defer server.Close()

	// Cerramos la conexión después de la respuesta.
	request = strings.Replace(
		request,
		"\r\n\r\n",
		"\r\nConnection: close\r\n\r\n",
		1,
	)

	_, err = server.Write([]byte(request))

	if err != nil {
		log.Println("Error enviando solicitud:", err)
		return
	}

	response, err := io.ReadAll(server)

	if err != nil {
		log.Println("Error leyendo respuesta:", err)
		return
	}

	// Guardar únicamente respuestas GET.
	if method == "GET" {

		cacheMu.Lock()

		cache[path] = response

		cacheMu.Unlock()

		log.Printf(
			"Respuesta guardada en cache: %s",
			path,
		)
	}

	_, err = client.Write(response)

	if err != nil {
		log.Println("Error enviando respuesta:", err)
	}

	recordResponseTime(time.Since(start))
}

func showStats(client net.Conn) {

	statsMu.Lock()

	total := totalRequests
	hits := cacheHits
	misses := cacheMisses
	totalTime := totalResponseTime
	maxTime := maxResponseTime

	statsMu.Unlock()

	hitRate := 0.0
	missRate := 0.0
	averageTime := 0.0

	if total > 0 {

		hitRate =
			float64(hits) /
				float64(total) *
				100

		missRate =
			float64(misses) /
				float64(total) *
				100

		averageTime =
			totalTime.Seconds() /
				float64(total) *
				1000
	}

	response := fmt.Sprintf(
		"HTTP/1.1 200 OK\r\n"+
			"Content-Type: text/html; charset=utf-8\r\n"+
			"X-Content-Type-Options: nosniff\r\n"+
			"X-Frame-Options: DENY\r\n"+
			"Referrer-Policy: no-referrer\r\n"+
			"Connection: close\r\n"+
			"\r\n"+
			"<html>"+
			"<head>"+
			"<title>Proxy Stats</title>"+
			"</head>"+
			"<body>"+
			"<h1>Estadísticas del Proxy</h1>"+
			"<p>Solicitudes totales: %d</p>"+
			"<p>Cache HIT: %d</p>"+
			"<p>Cache MISS: %d</p>"+
			"<p>Hit Rate: %.2f%%</p>"+
			"<p>Miss Rate: %.2f%%</p>"+
			"<p>Tiempo promedio: %.3f ms</p>"+
			"<p>Tiempo máximo: %.3f ms</p>"+
			"</body>"+
			"</html>",
		total,
		hits,
		misses,
		hitRate,
		missRate,
		averageTime,
		float64(maxTime.Microseconds())/1000,
	)

	client.Write([]byte(response))
}

func main() {

	listener, err := net.Listen(
		"tcp",
		":9000",
	)

	if err != nil {
		log.Fatal(err)
	}

	defer listener.Close()

	log.Println(
		"Proxy HTTP con cache escuchando en :9000",
	)

	for {

		client, err := listener.Accept()

		if err != nil {
			log.Println(
				"Error aceptando conexión:",
				err,
			)

			continue
		}

		go handleClient(client)
	}
}
