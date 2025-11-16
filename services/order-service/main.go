package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/segmentio/kafka-go"
	_ "github.com/lib/pq"
	"google.golang.org/grpc"
)

// Metrics
var (
	orderCreated = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "orders_created_total",
			Help: "Total orders created",
		},
		[]string{"user_id"},
	)
	orderLatency = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name: "order_latency_seconds",
			Help: "Order processing latency",
		},
		[]string{"operation"},
	)
	kafkaEventsPublished = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "kafka_events_published_total",
			Help: "Total Kafka events published",
		},
		[]string{"topic", "status"},
	)
)

func init() {
	prometheus.MustRegister(orderCreated)
	prometheus.MustRegister(orderLatency)
	prometheus.MustRegister(kafkaEventsPublished)
}

// Models
type OrderItem struct {
	ProductID string  `json:"product_id"`
	Quantity  int     `json:"quantity"`
	UnitPrice float64 `json:"unit_price"`
}

type ShippingAddress struct {
	Street  string `json:"street"`
	City    string `json:"city"`
	State   string `json:"state"`
	Zip     string `json:"zip"`
	Country string `json:"country"`
}

type Order struct {
	ID              string           `json:"id"`
	UserID          string           `json:"user_id"`
	Items           []OrderItem      `json:"items"`
	TotalAmount     float64          `json:"total_amount"`
	Status          string           `json:"status"`
	PaymentStatus   string           `json:"payment_status"`
	ShippingAddress ShippingAddress  `json:"shipping_address"`
	CreatedAt       time.Time        `json:"created_at"`
	UpdatedAt       time.Time        `json:"updated_at"`
}

type CreateOrderRequest struct {
	UserID           string           `json:"user_id"`
	Items            []OrderItem      `json:"items"`
	ShippingAddress  ShippingAddress  `json:"shipping_address"`
	PaymentMethod    string           `json:"payment_method"`
}

type OrderService struct {
	db          *sql.DB
	kafkaWriter *kafka.Writer
}

// Main
func main() {
	// Database connection
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://admin:password@localhost:5432/ecommerce?sslmode=disable"
	}

	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	if err := db.Ping(); err != nil {
		log.Fatalf("Failed to ping database: %v", err)
	}

	// Create tables
	if err := createTables(db); err != nil {
		log.Fatalf("Failed to create tables: %v", err)
	}

	// Kafka writer
	kafkaBootstrapServers := os.Getenv("KAFKA_BOOTSTRAP_SERVERS")
	if kafkaBootstrapServers == "" {
		kafkaBootstrapServers = "localhost:9092"
	}

	kafkaWriter := kafka.NewWriter(kafka.WriterConfig{
		Brokers:        []string{kafkaBootstrapServers},
		Topic:          "orders",
		Balancer:       &kafka.LeastBytes{},
		RequiredAcks:   kafka.RequireAll,
		MaxMessageBytes: 1024 * 1024,
		Compression:    kafka.Snappy,
	})
	defer kafkaWriter.Close()

	service := &OrderService{
		db:          db,
		kafkaWriter: kafkaWriter,
	}

	// Run both gRPC and REST servers
	go runGRPCServer(service)
	runRESTServer(service)
}

// gRPC Server
func runGRPCServer(service *OrderService) {
	listener, err := net.Listen("tcp", ":50053")
	if err != nil {
		log.Fatalf("Failed to listen on port 50053: %v", err)
	}

	grpcServer := grpc.NewServer()
	// TODO: Register gRPC services here

	log.Println("Order Service gRPC listening on :50053")
	if err := grpcServer.Serve(listener); err != nil {
		log.Fatalf("gRPC server failed: %v", err)
	}
}

// REST Server
func runRESTServer(service *OrderService) {
	router := gin.Default()

	// Middleware
	router.Use(loggingMiddleware())

	// Health check
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "healthy",
			"service": "order-service",
		})
	})

	// Metrics
	router.GET("/metrics", gin.WrapF(promhttp.Handler().ServeHTTP))

	// API routes
	v1 := router.Group("/api/v1")
	{
		v1.POST("/orders", service.handleCreateOrder)
		v1.GET("/orders/:id", service.handleGetOrder)
		v1.GET("/orders", service.handleListOrders)
		v1.PUT("/orders/:id/status", service.handleUpdateOrderStatus)
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8003"
	}

	log.Printf("Order Service REST listening on :%s", port)
	if err := router.Run(":" + port); err != nil {
		log.Fatalf("REST server failed: %v", err)
	}
}

// REST Handlers
func (s *OrderService) handleCreateOrder(c *gin.Context) {
	start := time.Now()

	var req CreateOrderRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	order := &Order{
		ID:              uuid.New().String(),
		UserID:          req.UserID,
		Items:           req.Items,
		Status:          "PENDING",
		PaymentStatus:   "PENDING",
		ShippingAddress: req.ShippingAddress,
		CreatedAt:       time.Now(),
		UpdatedAt:       time.Now(),
	}

	// Calculate total
	totalAmount := 0.0
	for _, item := range order.Items {
		totalAmount += item.UnitPrice * float64(item.Quantity)
	}
	order.TotalAmount = totalAmount

	// Save to database
	err := s.saveOrder(c.Request.Context(), order)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create order"})
		orderLatency.WithLabelValues("create_error").Observe(time.Since(start).Seconds())
		return
	}

	// Publish to Kafka
	eventData, _ := json.Marshal(map[string]interface{}{
		"order_id":      order.ID,
		"user_id":       order.UserID,
		"total_amount":  order.TotalAmount,
		"items_count":   len(order.Items),
		"created_at":    order.CreatedAt,
	})

	err = s.kafkaWriter.WriteMessages(c.Request.Context(),
		kafka.Message{
			Key:   []byte(order.ID),
			Value: eventData,
		},
	)

	if err != nil {
		log.Printf("Failed to publish to Kafka: %v", err)
		kafkaEventsPublished.WithLabelValues("orders", "error").Inc()
	} else {
		kafkaEventsPublished.WithLabelValues("orders", "success").Inc()
	}

	orderCreated.WithLabelValues(order.UserID).Inc()
	orderLatency.WithLabelValues("create").Observe(time.Since(start).Seconds())

	c.JSON(http.StatusCreated, order)
}

func (s *OrderService) handleGetOrder(c *gin.Context) {
	orderID := c.Param("id")

	order, err := s.getOrder(c.Request.Context(), orderID)
	if err != nil {
		if err == sql.ErrNoRows {
			c.JSON(http.StatusNotFound, gin.H{"error": "Order not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Database error"})
		return
	}

	c.JSON(http.StatusOK, order)
}

func (s *OrderService) handleListOrders(c *gin.Context) {
	userID := c.Query("user_id")
	skip := 0
	limit := 10

	// TODO: Parse skip/limit from query

	orders, err := s.listOrders(c.Request.Context(), userID, skip, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Database error"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"orders": orders,
		"total":  len(orders),
	})
}

func (s *OrderService) handleUpdateOrderStatus(c *gin.Context) {
	orderID := c.Param("id")

	var req struct {
		Status        string `json:"status"`
		PaymentStatus string `json:"payment_status"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	order, err := s.getOrder(c.Request.Context(), orderID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Order not found"})
		return
	}

	order.Status = req.Status
	order.PaymentStatus = req.PaymentStatus
	order.UpdatedAt = time.Now()

	if err := s.updateOrder(c.Request.Context(), order); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update order"})
		return
	}

	c.JSON(http.StatusOK, order)
}

// Database functions
func createTables(db *sql.DB) error {
	schema := `
		CREATE TABLE IF NOT EXISTS orders (
			id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
			user_id VARCHAR(255) NOT NULL,
			items JSONB NOT NULL,
			total_amount FLOAT NOT NULL,
			status VARCHAR(50) NOT NULL,
			payment_status VARCHAR(50) NOT NULL,
			shipping_address JSONB NOT NULL,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		);

		CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
		CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
	`

	_, err := db.Exec(schema)
	return err
}

func (s *OrderService) saveOrder(ctx context.Context, order *Order) error {
	itemsJSON, _ := json.Marshal(order.Items)
	addressJSON, _ := json.Marshal(order.ShippingAddress)

	query := `
		INSERT INTO orders (id, user_id, items, total_amount, status, payment_status, shipping_address, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`

	_, err := s.db.ExecContext(ctx, query,
		order.ID, order.UserID, string(itemsJSON), order.TotalAmount,
		order.Status, order.PaymentStatus, string(addressJSON),
		order.CreatedAt, order.UpdatedAt,
	)

	return err
}

func (s *OrderService) getOrder(ctx context.Context, orderID string) (*Order, error) {
	var order Order
	var itemsJSON, addressJSON string

	query := `
		SELECT id, user_id, items, total_amount, status, payment_status, shipping_address, created_at, updated_at
		FROM orders
		WHERE id = $1
	`

	err := s.db.QueryRowContext(ctx, query, orderID).Scan(
		&order.ID, &order.UserID, &itemsJSON, &order.TotalAmount,
		&order.Status, &order.PaymentStatus, &addressJSON,
		&order.CreatedAt, &order.UpdatedAt,
	)

	if err != nil {
		return nil, err
	}

	json.Unmarshal([]byte(itemsJSON), &order.Items)
	json.Unmarshal([]byte(addressJSON), &order.ShippingAddress)

	return &order, nil
}

func (s *OrderService) listOrders(ctx context.Context, userID string, skip, limit int) ([]Order, error) {
	var orders []Order

	query := `
		SELECT id, user_id, items, total_amount, status, payment_status, shipping_address, created_at, updated_at
		FROM orders
		WHERE user_id = $1
		ORDER BY created_at DESC
		LIMIT $2 OFFSET $3
	`

	rows, err := s.db.QueryContext(ctx, query, userID, limit, skip)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var order Order
		var itemsJSON, addressJSON string

		err := rows.Scan(
			&order.ID, &order.UserID, &itemsJSON, &order.TotalAmount,
			&order.Status, &order.PaymentStatus, &addressJSON,
			&order.CreatedAt, &order.UpdatedAt,
		)

		if err != nil {
			return nil, err
		}

		json.Unmarshal([]byte(itemsJSON), &order.Items)
		json.Unmarshal([]byte(addressJSON), &order.ShippingAddress)

		orders = append(orders, order)
	}

	return orders, rows.Err()
}

func (s *OrderService) updateOrder(ctx context.Context, order *Order) error {
	itemsJSON, _ := json.Marshal(order.Items)
	addressJSON, _ := json.Marshal(order.ShippingAddress)

	query := `
		UPDATE orders
		SET status = $1, payment_status = $2, updated_at = $3
		WHERE id = $4
	`

	_, err := s.db.ExecContext(ctx, query,
		order.Status, order.PaymentStatus, order.UpdatedAt, order.ID,
	)

	return err
}

// Middleware
func loggingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		startTime := time.Now()

		c.Next()

		duration := time.Since(startTime)
		statusCode := c.Writer.Status()

		log.Printf("[%s] %s - Status: %d - Duration: %v",
			c.Request.Method, c.Request.URL.Path, statusCode, duration)
	}
}
