# Local Model Setup

The project uses two local models:
- **LLM** via Ollama: person extraction at ingest, result formatting at search.
- **Embedding model** `BAAI/bge-small-en-v1.5` via sentence-transformers.

## 1. Install Ollama
- **Windows / macOS:** download and run the installer from https://ollama.com/download.
  Ollama then runs as a background service.
- **Linux / WSL:**
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

Verify:
```bash
ollama --version
```

## 2. Pull a model
| RAM | Model | Command | Download |
|---|---|---|---|
| 8 GB | Llama 3.2 3B (default) | `ollama pull llama3.2:3b` | ~2 GB |
| 8 GB | Qwen 2.5 3B (good structured output) | `ollama pull qwen2.5:3b` | ~1.9 GB |
| 16 GB+ | Llama 3.1 8B (best quality) | `ollama pull llama3.1:8b` | ~4.9 GB |

Set the one you pulled as `OLLAMA_MODEL` in `.env`. Newer models: https://ollama.com/library.

## 3. Test
```bash
ollama run llama3.2:3b "Say hello in one line"
```

JSON mode through the API (how the app calls it):
```bash
curl http://localhost:11434/api/chat -d '{
  "model": "llama3.2:3b",
  "format": "json",
  "stream": false,
  "messages": [{"role": "user", "content": "Return {\"people\":[{\"name\":\"Tim Cook\",\"role\":\"CEO\"}]} as JSON"}]
}'
```
On Windows PowerShell use `curl.exe`, or just test with `ollama run`.

## 4. Configure `.env`
```
LLM_PROVIDER=ollama
LLM_TIMEOUT_SECONDS=60
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

## 5. Pre-download the embedding model
Inside the project virtual environment:
```bash
python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('BAAI/bge-small-en-v1.5'); print(m.get_sentence_embedding_dimension())"
```
Expected output: `384` (must match `EMBEDDING_DIM`). About 130 MB, cached after the first run.

## Troubleshooting
| Problem | Fix |
|---|---|
| `Ollama not reachable` | Start it: `ollama serve` (or open the Ollama app) |
| `model not found` | `ollama pull <OLLAMA_MODEL>`; check the name with `ollama list` |
| First request very slow / timeout | Model is loading into memory; retry, or raise `LLM_TIMEOUT_SECONDS` |
| Answers are prose, not JSON | Ensure `format: "json"` is sent; try `qwen2.5:3b` or an 8B model |
| Laptop too slow | Use `llama3.2:3b`, or switch to `LLM_PROVIDER=groq` with a free API key |
