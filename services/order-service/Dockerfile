FROM golang:1.21-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git protobuf-dev

COPY go.mod go.sum* ./

RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o order-service .

FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /root/

COPY --from=builder /app/order-service .

EXPOSE 50053 8003

CMD ["./order-service"]
