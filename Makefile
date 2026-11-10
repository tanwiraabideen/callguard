.PHONY: backend frontend

backend:
	cd backend && uv run python -m app.main

frontend:
	cd frontend && npm install && npm run dev
