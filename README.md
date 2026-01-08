# OpenCode Quick Start (RTX 3060 12GB)

Local AI coding assistant with REPL-style agentic loops.

## 1. Install Ollama

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve
```

## 2. Pull Model (3060-optimized)

```bash
# Best for 12GB VRAM - Qwen 2.5 Coder 7B
ollama pull qwen2.5-coder:7b

# Alternative: Quantized 14B (tighter fit, better quality)
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
```

## 3. Install OpenCode

```bash
# Option A: npm
npm i -g opencode-ai@latest

# Option B: curl
curl -fsSL https://opencode.ai/install | bash
```

## 4. Configure

```bash
opencode config set provider ollama
opencode config set model qwen2.5-coder:7b
```

## 5. Run

```bash
# Start in any project directory
cd /your/project
opencode

# Or with a prompt
opencode "explain this codebase"
```

## Model Recommendations for 3060

| Model | VRAM | Quality | Speed |
|-------|------|---------|-------|
| `qwen2.5-coder:7b` | ~6GB | Good | Fast |
| `qwen2.5-coder:14b-instruct-q4_K_M` | ~10GB | Better | Medium |
| `deepseek-coder-v2:16b-lite-instruct-q4_0` | ~10GB | Good | Medium |
| `codellama:7b` | ~5GB | Decent | Fast |

## Cloud Fallback (for complex tasks)

```bash
# Use Together.ai for heavy lifting
export TOGETHER_API_KEY="your-key"
opencode config set provider together
opencode config set model Qwen/Qwen2.5-Coder-32B-Instruct
```

## Tips

- Run `ollama ps` to check loaded models
- Use `ollama rm <model>` to free VRAM
- For long context, try `qwen2.5-coder:7b-instruct-q8_0` (uses more VRAM but 128K context)
