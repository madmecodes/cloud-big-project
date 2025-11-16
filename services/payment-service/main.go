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
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	_ "github.com/lib/pq"
	"google.golang.org/grpc"
)

// Metrics
var (
	paymentsProcessed = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "payments_processed_total",
			Help: "Total payments processed",
		},
		[]string{"status"},
	)
	paymentLatency = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name: "payment_processing_seconds",
			Help: "Payment processing latency",
		},
		[]string{"operation"},
	)
	paymentAmount = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "payment_amount_total",
			Help: "Total payment amount processed",
		},
		[]string{"currency"},
	)
)

func init() {
	prometheus.MustRegister(paymentsProcessed)
	prometheus.MustRegister(paymentLatency)
	prometheus.MustRegister(paymentAmount)
}

// Models
type PaymentRequest struct {
	OrderID       string `json:"order_id"`
	UserID        string `json:"user_id"`
	Amount        float64 `json:"amount"`
	Currency      string `json:"currency"`
	PaymentMethod string `json:"payment_method"`
	CardToken     string `json:"card_token,omitempty"`
}

type PaymentResponse struct {
	PaymentID string    `json:"payment_id"`
	OrderID   string    `json:"order_id"`
	Status    string    `json:"status"`
	Amount    float64   `json:"amount"`
	Currency  string    `json:"currency"`
	Message   string    `json:"message,omitempty"`
	CreatedAt time.Time `json:"created_at"`
}

type Payment struct {
	ID        string    `json:"id"`
	OrderID   string    `json:"order_id"`
	UserID    string    `json:"user_id"`
	Amount    float64   `json:"amount"`
	Currency  string    `json:"currency"`
	Status    string    `json:"status"`
	Method    string    `json:"method"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

type PaymentService struct {
	db *sql.DB
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

	service := &PaymentService{db: db}

	// Run both gRPC and REST servers
	go runGRPCServer(service)
	runRESTServer(service)
}

// gRPC Server
func runGRPCServer(service *PaymentService) {
	listener, err := net.Listen("tcp", ":50054")
	if err != nil {
		log.Fatalf("Failed to listen on port 50054: %v", err)
	}

	grpcServer := grpc.NewServer()
	// TODO: Register gRPC services here

	log.Println("Payment Service gRPC listening on :50054")
	if err := grpcServer.Serve(listener); err != nil {
		log.Fatalf("gRPC server failed: %v", err)
	}
}

// REST Server
func runRESTServer(service *PaymentService) {
	router := gin.Default()

	// Middleware
	router.Use(loggingMiddleware())

	// Health check
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "healthy",
			"service": "payment-service",
		})
	})

	// Metrics
	router.GET("/metrics", gin.WrapF(promhttp.Handler().ServeHTTP))

	// API routes
	v1 := router.Group("/api/v1")
	{
		v1.POST("/payments", service.handleProcessPayment)
		v1.GET("/payments/:id", service.handleGetPayment)
		v1.POST("/payments/:id/refund", service.handleRefundPayment)
		v1.GET("/orders/:order_id/payments", service.handleGetOrderPayments)
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8004"
	}

	log.Printf("Payment Service REST listening on :%s", port)
	if err := router.Run(":" + port); err != nil {
		log.Fatalf("REST server failed: %v", err)
	}
}

// REST Handlers
func (s *PaymentService) handleProcessPayment(c *gin.Context) {
	start := time.Now()

	var req PaymentRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate amount
	if req.Amount <= 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid amount"})
		return
	}

	// Process payment (mock Stripe-like behavior)
	paymentID := uuid.New().String()
	status := "COMPLETED"
	message := "Payment processed successfully"

	// Simulate payment processing
	if req.Amount > 10000 {
		status = "REQUIRES_REVIEW"
		message = "Payment amount exceeds limit, requires review"
	}

	payment := &Payment{
		ID:        paymentID,
		OrderID:   req.OrderID,
		UserID:    req.UserID,
		Amount:    req.Amount,
		Currency:  req.Currency,
		Status:    status,
		Method:    req.PaymentMethod,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	// Save to database
	if err := s.savePayment(c.Request.Context(), payment); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to process payment"})
		paymentsProcessed.WithLabelValues("error").Inc()
		paymentLatency.WithLabelValues("process").Observe(time.Since(start).Seconds())
		return
	}

	paymentsProcessed.WithLabelValues(status).Inc()
	paymentAmount.WithLabelValues(req.Currency).Add(req.Amount)
	paymentLatency.WithLabelValues("process").Observe(time.Since(start).Seconds())

	response := PaymentResponse{
		PaymentID: paymentID,
		OrderID:   req.OrderID,
		Status:    status,
		Amount:    req.Amount,
		Currency:  req.Currency,
		Message:   message,
		CreatedAt: time.Now(),
	}

	statusCode := http.StatusCreated
	if status != "COMPLETED" {
		statusCode = http.StatusAccepted
	}

	c.JSON(statusCode, response)
}

func (s *PaymentService) handleGetPayment(c *gin.Context) {
	paymentID := c.Param("id")

	payment, err := s.getPayment(c.Request.Context(), paymentID)
	if err != nil {
		if err == sql.ErrNoRows {
			c.JSON(http.StatusNotFound, gin.H{"error": "Payment not found"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Database error"})
		return
	}

	c.JSON(http.StatusOK, payment)
}

func (s *PaymentService) handleRefundPayment(c *gin.Context) {
	paymentID := c.Param("id")

	var req struct {
		Reason string `json:"reason"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	payment, err := s.getPayment(c.Request.Context(), paymentID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Payment not found"})
		return
	}

	payment.Status = "REFUNDED"
	payment.UpdatedAt = time.Now()

	if err := s.updatePayment(c.Request.Context(), payment); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to refund payment"})
		return
	}

	paymentsProcessed.WithLabelValues("refunded").Inc()

	c.JSON(http.StatusOK, gin.H{
		"payment_id": paymentID,
		"status":     "REFUNDED",
		"reason":     req.Reason,
		"refunded_at": time.Now(),
	})
}

func (s *PaymentService) handleGetOrderPayments(c *gin.Context) {
	orderID := c.Param("order_id")

	payments, err := s.getOrderPayments(c.Request.Context(), orderID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Database error"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"order_id": orderID,
		"payments": payments,
		"total":    len(payments),
	})
}

// Database functions
func createTables(db *sql.DB) error {
	schema := `
		CREATE TABLE IF NOT EXISTS payments (
			id UUID PRIMARY KEY,
			order_id VARCHAR(255) NOT NULL,
			user_id VARCHAR(255) NOT NULL,
			amount FLOAT NOT NULL,
			currency VARCHAR(10) NOT NULL,
			status VARCHAR(50) NOT NULL,
			method VARCHAR(50) NOT NULL,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		);

		CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
		CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
		CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
	`

	_, err := db.Exec(schema)
	return err
}

func (s *PaymentService) savePayment(ctx context.Context, payment *Payment) error {
	query := `
		INSERT INTO payments (id, order_id, user_id, amount, currency, status, method, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`

	_, err := s.db.ExecContext(ctx, query,
		payment.ID, payment.OrderID, payment.UserID, payment.Amount,
		payment.Currency, payment.Status, payment.Method,
		payment.CreatedAt, payment.UpdatedAt,
	)

	return err
}

func (s *PaymentService) getPayment(ctx context.Context, paymentID string) (*Payment, error) {
	var payment Payment

	query := `
		SELECT id, order_id, user_id, amount, currency, status, method, created_at, updated_at
		FROM payments
		WHERE id = $1
	`

	err := s.db.QueryRowContext(ctx, query, paymentID).Scan(
		&payment.ID, &payment.OrderID, &payment.UserID, &payment.Amount,
		&payment.Currency, &payment.Status, &payment.Method,
		&payment.CreatedAt, &payment.UpdatedAt,
	)

	return &payment, err
}

func (s *PaymentService) updatePayment(ctx context.Context, payment *Payment) error {
	query := `
		UPDATE payments
		SET status = $1, updated_at = $2
		WHERE id = $3
	`

	_, err := s.db.ExecContext(ctx, query,
		payment.Status, payment.UpdatedAt, payment.ID,
	)

	return err
}

func (s *PaymentService) getOrderPayments(ctx context.Context, orderID string) ([]Payment, error) {
	var payments []Payment

	query := `
		SELECT id, order_id, user_id, amount, currency, status, method, created_at, updated_at
		FROM payments
		WHERE order_id = $1
		ORDER BY created_at DESC
	`

	rows, err := s.db.QueryContext(ctx, query, orderID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var payment Payment

		err := rows.Scan(
			&payment.ID, &payment.OrderID, &payment.UserID, &payment.Amount,
			&payment.Currency, &payment.Status, &payment.Method,
			&payment.CreatedAt, &payment.UpdatedAt,
		)

		if err != nil {
			return nil, err
		}

		payments = append(payments, payment)
	}

	return payments, rows.Err()
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
