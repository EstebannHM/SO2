FROM golang:1.24-alpine AS builder

WORKDIR /app

COPY go.mod ./

COPY server ./server
COPY proxy ./proxy

RUN go build -o server ./server
RUN go build -o proxy ./proxy


FROM alpine:latest

WORKDIR /app

COPY --from=builder /app/server .
COPY --from=builder /app/proxy .

EXPOSE 8080
EXPOSE 9000
