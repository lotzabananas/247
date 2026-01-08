#!/bin/bash
# OpenCode + Ollama Quick Setup for RTX 3060

set -e

echo "=== OpenCode Setup for RTX 3060 (12GB) ==="

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "[1/4] Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "[1/4] Ollama already installed"
fi

# Start Ollama if not running
if ! pgrep -x "ollama" > /dev/null; then
    echo "[2/4] Starting Ollama service..."
    ollama serve &
    sleep 3
else
    echo "[2/4] Ollama already running"
fi

# Pull the model
echo "[3/4] Pulling Qwen 2.5 Coder 7B (best for 12GB VRAM)..."
ollama pull qwen2.5-coder:7b

# Install OpenCode
if ! command -v opencode &> /dev/null; then
    echo "[4/4] Installing OpenCode..."
    if command -v npm &> /dev/null; then
        npm i -g opencode-ai@latest
    else
        curl -fsSL https://opencode.ai/install | bash
    fi
else
    echo "[4/4] OpenCode already installed"
fi

# Configure
echo ""
echo "=== Configuring OpenCode ==="
opencode config set provider ollama
opencode config set model qwen2.5-coder:7b

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Usage:"
echo "  cd /your/project"
echo "  opencode"
echo ""
echo "Or with a prompt:"
echo "  opencode 'explain this code'"
