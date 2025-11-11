package main

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"fmt"
	"log"
	"net"
	"os"
	"time"

	"context"
	_ "github.com/lib/pq"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	pb "github.com/ecommerce/user-service/pb"
)

type UserServiceServer struct {
	db *sql.DB
	pb.UnimplementedUserServiceServer
}

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

	// Test connection
	if err := db.Ping(); err != nil {
		log.Fatalf("Failed to ping database: %v", err)
	}

	// Create tables if they don't exist
	if err := createTables(db); err != nil {
		log.Fatalf("Failed to create tables: %v", err)
	}

	// gRPC server
	listener, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("Failed to listen on port 50051: %v", err)
	}

	server := grpc.NewServer()
	userService := &UserServiceServer{db: db}
	pb.RegisterUserServiceServer(server, userService)

	log.Println("User Service listening on :50051")
	if err := server.Serve(listener); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}

func (s *UserServiceServer) Authenticate(ctx context.Context, req *pb.AuthRequest) (*pb.AuthResponse, error) {
	var user pb.User
	var hashedPassword string

	query := `
		SELECT id, email, first_name, last_name, created_at, updated_at, active, password_hash
		FROM users
		WHERE email = $1
	`

	err := s.db.QueryRowContext(ctx, query, req.Email).Scan(
		&user.Id, &user.Email, &user.FirstName, &user.LastName,
		&user.CreatedAt, &user.UpdatedAt, &user.Active, &hashedPassword,
	)

	if err == sql.ErrNoRows {
		return &pb.AuthResponse{
			Success: false,
			Message: "Invalid email or password",
		}, nil
	}

	if err != nil {
		return nil, status.Errorf(codes.Internal, "Database error: %v", err)
	}

	// Verify password
	if !verifyPassword(req.Password, hashedPassword) {
		return &pb.AuthResponse{
			Success: false,
			Message: "Invalid email or password",
		}, nil
	}

	// Generate token (simplified JWT-like token)
	token := generateToken(user.Id)

	return &pb.AuthResponse{
		Success: true,
		Message: "Authentication successful",
		Token:   token,
		User:    &user,
	}, nil
}

func (s *UserServiceServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.User, error) {
	var user pb.User

	query := `
		SELECT id, email, first_name, last_name, created_at, updated_at, active
		FROM users
		WHERE id = $1
	`

	err := s.db.QueryRowContext(ctx, query, req.UserId).Scan(
		&user.Id, &user.Email, &user.FirstName, &user.LastName,
		&user.CreatedAt, &user.UpdatedAt, &user.Active,
	)

	if err == sql.ErrNoRows {
		return nil, status.Errorf(codes.NotFound, "User not found")
	}

	if err != nil {
		return nil, status.Errorf(codes.Internal, "Database error: %v", err)
	}

	return &user, nil
}

func (s *UserServiceServer) CreateUser(ctx context.Context, req *pb.CreateUserRequest) (*pb.User, error) {
	// Validate input
	if req.Email == "" || req.Password == "" {
		return nil, status.Errorf(codes.InvalidArgument, "Email and password are required")
	}

	// Hash password
	hashedPassword := hashPassword(req.Password)

	var user pb.User
	now := time.Now().Format(time.RFC3339)

	query := `
		INSERT INTO users (email, password_hash, first_name, last_name, active, created_at, updated_at)
		VALUES ($1, $2, $3, $4, true, $5, $6)
		RETURNING id, email, first_name, last_name, created_at, updated_at, active
	`

	err := s.db.QueryRowContext(ctx, query,
		req.Email, hashedPassword, req.FirstName, req.LastName, now, now,
	).Scan(
		&user.Id, &user.Email, &user.FirstName, &user.LastName,
		&user.CreatedAt, &user.UpdatedAt, &user.Active,
	)

	if err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to create user: %v", err)
	}

	return &user, nil
}

func (s *UserServiceServer) UpdateUser(ctx context.Context, req *pb.UpdateUserRequest) (*pb.User, error) {
	var user pb.User
	now := time.Now().Format(time.RFC3339)

	query := `
		UPDATE users
		SET first_name = COALESCE($1, first_name),
		    last_name = COALESCE($2, last_name),
		    email = COALESCE($3, email),
		    updated_at = $4
		WHERE id = $5
		RETURNING id, email, first_name, last_name, created_at, updated_at, active
	`

	err := s.db.QueryRowContext(ctx, query,
		req.FirstName, req.LastName, req.Email, now, req.UserId,
	).Scan(
		&user.Id, &user.Email, &user.FirstName, &user.LastName,
		&user.CreatedAt, &user.UpdatedAt, &user.Active,
	)

	if err == sql.ErrNoRows {
		return nil, status.Errorf(codes.NotFound, "User not found")
	}

	if err != nil {
		return nil, status.Errorf(codes.Internal, "Failed to update user: %v", err)
	}

	return &user, nil
}

// Helper functions
func createTables(db *sql.DB) error {
	schema := `
		CREATE TABLE IF NOT EXISTS users (
			id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
			email VARCHAR(255) UNIQUE NOT NULL,
			password_hash VARCHAR(255) NOT NULL,
			first_name VARCHAR(255),
			last_name VARCHAR(255),
			active BOOLEAN DEFAULT true,
			created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
		);

		CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
	`

	_, err := db.Exec(schema)
	return err
}

func hashPassword(password string) string {
	hash := sha256.Sum256([]byte(password))
	return hex.EncodeToString(hash[:])
}

func verifyPassword(password, hashedPassword string) bool {
	return hashPassword(password) == hashedPassword
}

func generateToken(userID string) string {
	// Simplified token generation (In production, use JWT)
	hash := sha256.Sum256([]byte(userID + time.Now().String()))
	return hex.EncodeToString(hash[:])
}
