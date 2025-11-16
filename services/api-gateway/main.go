package main

import (
	"context"
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
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// Metrics
var (
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total HTTP requests",
		},
		[]string{"method", "path", "status"},
	)
	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name: "http_request_duration_seconds",
			Help: "HTTP request duration in seconds",
		},
		[]string{"method", "path"},
	)
	grpcCallsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "grpc_calls_total",
			Help: "Total gRPC calls to downstream services",
		},
		[]string{"service", "method", "status"},
	)
)

func init() {
	prometheus.MustRegister(httpRequestsTotal)
	prometheus.MustRegister(httpRequestDuration)
	prometheus.MustRegister(grpcCallsTotal)
}

type APIGateway struct {
	userServiceConn    *grpc.ClientConn
	productServiceConn *grpc.ClientConn
	orderServiceConn   *grpc.ClientConn
	paymentServiceConn *grpc.ClientConn
}

type LoginRequest struct {
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required"`
}

type UserResponse struct {
	ID        string `json:"id"`
	Email     string `json:"email"`
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name"`
	Token     string `json:"token,omitempty"`
}

type ProductResponse struct {
	ID          string  `json:"id"`
	Name        string  `json:"name"`
	Description string `json:"description"`
	Price       float64 `json:"price"`
	Stock       int     `json:"stock"`
}

type OrderRequest struct {
	UserID           string        `json:"user_id" binding:"required"`
	Items            []OrderItem   `json:"items" binding:"required"`
	ShippingAddress  Address       `json:"shipping_address" binding:"required"`
}

type OrderItem struct {
	ProductID string `json:"product_id" binding:"required"`
	Quantity  int    `json:"quantity" binding:"required,gt=0"`
}

type Address struct {
	Street  string `json:"street" binding:"required"`
	City    string `json:"city" binding:"required"`
	State   string `json:"state" binding:"required"`
	Zip     string `json:"zip" binding:"required"`
	Country string `json:"country" binding:"required"`
}

type OrderResponse struct {
	OrderID        string    `json:"order_id"`
	UserID         string    `json:"user_id"`
	Status         string    `json:"status"`
	TotalAmount    float64   `json:"total_amount"`
	CreatedAt      time.Time `json:"created_at"`
}

func main() {
	// Setup Gin router
	router := gin.Default()

	// Add middleware
	router.Use(loggingMiddleware())
	router.Use(metricsMiddleware())

	// Initialize API Gateway
	gateway := &APIGateway{}

	// Connect to downstream services
	if err := gateway.connectDownstreamServices(); err != nil {
		log.Fatalf("Failed to connect to downstream services: %v", err)
	}
	defer gateway.closeConnections()

	// Health check endpoint
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "healthy",
			"service": "api-gateway",
			"time":    time.Now(),
		})
	})

	// Metrics endpoint
	router.GET("/metrics", gin.WrapF(promhttp.Handler().ServeHTTP))

	// API v1 routes
	v1 := router.Group("/api/v1")
	{
		// Auth endpoints
		auth := v1.Group("/auth")
		{
			auth.POST("/login", gateway.handleLogin)
			auth.POST("/register", gateway.handleRegister)
		}

		// Product endpoints
		products := v1.Group("/products")
		{
			products.GET("", gateway.handleListProducts)
			products.GET("/:id", gateway.handleGetProduct)
			products.POST("", gateway.handleCreateProduct)
		}

		// Order endpoints
		orders := v1.Group("/orders")
		{
			orders.POST("", gateway.handleCreateOrder)
			orders.GET("/:id", gateway.handleGetOrder)
			orders.GET("", gateway.handleListOrders)
		}

		// User endpoints
		users := v1.Group("/users")
		{
			users.GET("/:id", gateway.handleGetUser)
			users.PUT("/:id", gateway.handleUpdateUser)
		}
	}

	// Start server
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("API Gateway starting on port %s", port)
	if err := router.Run(":" + port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

// Downstream service connection
func (g *APIGateway) connectDownstreamServices() error {
	userServiceHost := os.Getenv("USER_SERVICE_HOST")
	if userServiceHost == "" {
		userServiceHost = "localhost"
	}

	productServiceHost := os.Getenv("PRODUCT_SERVICE_HOST")
	if productServiceHost == "" {
		productServiceHost = "localhost"
	}

	orderServiceHost := os.Getenv("ORDER_SERVICE_HOST")
	if orderServiceHost == "" {
		orderServiceHost = "localhost"
	}

	paymentServiceHost := os.Getenv("PAYMENT_SERVICE_HOST")
	if paymentServiceHost == "" {
		paymentServiceHost = "localhost"
	}

	var err error

	// Connect to User Service
	g.userServiceConn, err = grpc.Dial(
		userServiceHost+":50051",
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(1024*1024*10)),
	)
	if err != nil {
		return fmt.Errorf("failed to connect to user service: %w", err)
	}

	// Connect to Product Service
	g.productServiceConn, err = grpc.Dial(
		productServiceHost+":50052",
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(1024*1024*10)),
	)
	if err != nil {
		return fmt.Errorf("failed to connect to product service: %w", err)
	}

	// Connect to Order Service
	g.orderServiceConn, err = grpc.Dial(
		orderServiceHost+":50053",
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(1024*1024*10)),
	)
	if err != nil {
		return fmt.Errorf("failed to connect to order service: %w", err)
	}

	// Connect to Payment Service
	g.paymentServiceConn, err = grpc.Dial(
		paymentServiceHost+":50054",
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(grpc.MaxCallRecvMsgSize(1024*1024*10)),
	)
	if err != nil {
		return fmt.Errorf("failed to connect to payment service: %w", err)
	}

	return nil
}

func (g *APIGateway) closeConnections() {
	if g.userServiceConn != nil {
		g.userServiceConn.Close()
	}
	if g.productServiceConn != nil {
		g.productServiceConn.Close()
	}
	if g.orderServiceConn != nil {
		g.orderServiceConn.Close()
	}
	if g.paymentServiceConn != nil {
		g.paymentServiceConn.Close()
	}
}

// REST Handlers

func (g *APIGateway) handleLogin(c *gin.Context) {
	var req LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Call User Service gRPC (TODO: implement when user service gRPC is ready)
	// For now, return mock response
	c.JSON(http.StatusOK, UserResponse{
		ID:        uuid.New().String(),
		Email:     req.Email,
		FirstName: "John",
		LastName:  "Doe",
		Token:     generateMockToken(),
	})
}

func (g *APIGateway) handleRegister(c *gin.Context) {
	var req LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, UserResponse{
		ID:        uuid.New().String(),
		Email:     req.Email,
		FirstName: "John",
		LastName:  "Doe",
	})
}

func (g *APIGateway) handleListProducts(c *gin.Context) {
	skip := c.DefaultQuery("skip", "0")
	limit := c.DefaultQuery("limit", "10")

	// TODO: Call Product Service gRPC to get products
	products := []ProductResponse{
		{
			ID:          "prod-001",
			Name:        "Laptop",
			Description: "High-performance laptop",
			Price:       999.99,
			Stock:       10,
		},
		{
			ID:          "prod-002",
			Name:        "Monitor",
			Description: "4K Monitor",
			Price:       399.99,
			Stock:       20,
		},
	}

	c.JSON(http.StatusOK, gin.H{
		"skip":     skip,
		"limit":    limit,
		"products": products,
	})
}

func (g *APIGateway) handleGetProduct(c *gin.Context) {
	productID := c.Param("id")

	// TODO: Call Product Service gRPC to get single product
	product := ProductResponse{
		ID:          productID,
		Name:        "Laptop",
		Description: "High-performance laptop",
		Price:       999.99,
		Stock:       10,
	}

	c.JSON(http.StatusOK, product)
}

func (g *APIGateway) handleCreateProduct(c *gin.Context) {
	var product ProductResponse
	if err := c.ShouldBindJSON(&product); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	product.ID = uuid.New().String()

	// TODO: Call Product Service gRPC to create product
	c.JSON(http.StatusCreated, product)
}

func (g *APIGateway) handleCreateOrder(c *gin.Context) {
	var req OrderRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	orderID := uuid.New().String()

	// TODO: Call Order Service gRPC to create order
	// TODO: This will trigger Kafka event, Lambda notification, and Flink analytics

	response := OrderResponse{
		OrderID:     orderID,
		UserID:      req.UserID,
		Status:      "PENDING",
		TotalAmount: 1000.0, // Calculate from items
		CreatedAt:   time.Now(),
	}

	c.JSON(http.StatusCreated, response)
}

func (g *APIGateway) handleGetOrder(c *gin.Context) {
	orderID := c.Param("id")

	// TODO: Call Order Service gRPC to get order
	response := OrderResponse{
		OrderID:     orderID,
		UserID:      "user-123",
		Status:      "CONFIRMED",
		TotalAmount: 1000.0,
		CreatedAt:   time.Now(),
	}

	c.JSON(http.StatusOK, response)
}

func (g *APIGateway) handleListOrders(c *gin.Context) {
	userID := c.Query("user_id")

	// TODO: Call Order Service gRPC to list orders
	orders := []OrderResponse{
		{
			OrderID:     "order-001",
			UserID:      userID,
			Status:      "CONFIRMED",
			TotalAmount: 1000.0,
			CreatedAt:   time.Now(),
		},
	}

	c.JSON(http.StatusOK, orders)
}

func (g *APIGateway) handleGetUser(c *gin.Context) {
	userID := c.Param("id")

	// TODO: Call User Service gRPC to get user
	response := UserResponse{
		ID:        userID,
		Email:     "user@example.com",
		FirstName: "John",
		LastName:  "Doe",
	}

	c.JSON(http.StatusOK, response)
}

func (g *APIGateway) handleUpdateUser(c *gin.Context) {
	userID := c.Param("id")
	var req UserResponse
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// TODO: Call User Service gRPC to update user
	req.ID = userID
	c.JSON(http.StatusOK, req)
}

// Middleware

func loggingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		startTime := time.Now()

		c.Next()

		duration := time.Since(startTime)
		statusCode := c.Writer.Status()
		method := c.Request.Method
		path := c.Request.URL.Path

		log.Printf("[%s] %s %s - Status: %d - Duration: %v",
			method, path, c.Request.RemoteAddr, statusCode, duration)
	}
}

func metricsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		startTime := time.Now()

		c.Next()

		duration := time.Since(startTime).Seconds()
		statusCode := c.Writer.Status()
		method := c.Request.Method
		path := c.Request.URL.Path

		httpRequestsTotal.WithLabelValues(method, path, fmt.Sprintf("%d", statusCode)).Inc()
		httpRequestDuration.WithLabelValues(method, path).Observe(duration)
	}
}

// Helper functions

func generateMockToken() string {
	return fmt.Sprintf("token_%s_%d", uuid.New().String(), time.Now().Unix())
}
