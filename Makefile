.PHONY: backend frontend audio eval deploy-backend

backend:
	cd backend && uv run python -m app.main

audio:
	cd backend && uv run python -m tools.generate_audio

eval:
	cd backend && uv run python -m tools.evaluate

deploy-backend:
	git subtree push --prefix backend heroku main

frontend:
	cd frontend && npm install && npm run dev
