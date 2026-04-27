#!/usr/bin/env bash
# DARWIN-PHOENIX setup — Chapter 7 of the Masterbook
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=== [1/3] Setting up Python environment with uv ==="
uv venv .venv --clear
# Windows activation path
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || -f ".venv/Scripts/activate" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

uv pip install \
    langgraph \
    langchain-core \
    langchain-groq \
    groq \
    evalplus \
    pytest \
    docker \
    scikit-learn \
    bandit \
    coverage

echo ""
echo "=== [2/3] Building Docker sandbox image ==="
docker build -t dp-sandbox -f Dockerfile.sandbox .

echo ""
echo "=== [3/3] Pulling Ollama model: qwen2.5-coder:7b ==="
ollama pull qwen2.5-coder:7b

echo ""
echo "=== Setup complete ==="
echo "Activate env:  source .venv/Scripts/activate  (Windows)"
echo "Smoke test:    pytest --co -q"
