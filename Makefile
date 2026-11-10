.PHONY: backend frontend audio

backend:
	cd backend && uv run python -m app.main

audio:
	cd backend && uv run python -m tools.generate_audio

frontend:
	cd frontend && npm install && npm run dev
