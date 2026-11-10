.PHONY: backend frontend audio eval

backend:
	cd backend && uv run python -m app.main

audio:
	cd backend && uv run python -m tools.generate_audio

eval:
	cd backend && uv run python -m tools.evaluate

frontend:
	cd frontend && npm install && npm run dev
