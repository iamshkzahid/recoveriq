# ═══════════════════════════════════════════
# RecoverIQ — Makefile
# Convenience commands for development
# ═══════════════════════════════════════════

.PHONY: setup setup-backend setup-frontend train run run-backend run-frontend demo clean help

# Default target
help:
	@echo "RecoverIQ — Available Commands:"
	@echo ""
	@echo "  make setup          — Install all dependencies (backend + frontend)"
	@echo "  make train          — Train the ML failure prediction model"
	@echo "  make run            — Start both backend and frontend servers"
	@echo "  make run-backend    — Start only the FastAPI backend"
	@echo "  make run-frontend   — Start only the React frontend"
	@echo "  make demo           — Run a simulation batch via API"
	@echo "  make clean          — Remove generated files and caches"
	@echo ""

# Full setup
setup: setup-backend setup-frontend
	@echo "✅ Setup complete!"

# Backend setup
setup-backend:
	@echo "📦 Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "✅ Backend ready!"

# Frontend setup
setup-frontend:
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm install
	@echo "✅ Frontend ready!"

# Train ML model
train:
	@echo "🧠 Training failure prediction model..."
	cd backend && python models/train_model.py
	@echo "✅ Model trained!"

# Run both servers
run:
	@echo "🚀 Starting RecoverIQ..."
	@echo "   Backend: http://localhost:8000"
	@echo "   Frontend: http://localhost:3000"
	@make run-backend &
	@make run-frontend

# Backend only
run-backend:
	cd backend && python core_engine.py

# Frontend only
run-frontend:
	cd frontend && npm run dev

# Demo simulation
demo:
	@echo "🎲 Running simulation batch..."
	curl -s -X POST http://localhost:8000/api/simulate/batch \
		-H "Content-Type: application/json" \
		-d '{"batch_size": 50, "failure_rate": 0.15}' | python -m json.tool

# Generate synthetic data
generate-data:
	cd backend && python data_generator.py

# Clean
clean:
	@echo "🧹 Cleaning up..."
	rm -f backend/*.db backend/*.db-wal backend/*.db-shm
	rm -f backend/models/*.joblib backend/models/model_metrics.json
	rm -rf backend/data/
	rm -rf backend/__pycache__ backend/models/__pycache__
	rm -rf frontend/node_modules frontend/dist
	@echo "✅ Clean!"
