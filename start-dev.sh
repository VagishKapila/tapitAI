#!/bin/bash

echo “Starting backend…”
cd backend
source venv/bin/activate
uvicorn app.main:app –reload –port 8000 &

echo “Starting ngrok…”
ngrok http 8000 &

echo “Starting frontend…”
cd ../frontend
npx expo start

