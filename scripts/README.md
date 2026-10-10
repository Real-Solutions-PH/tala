# Scripts

## `fetch_models.sh`

One-time download of the models that `run.sh` does not expect you to fetch by hand. Safe to re-run: files already present are skipped. After it finishes, nothing needs the network (`run.sh` sets `HF_HUB_OFFLINE=1`).

It downloads into `$MODELS` (default `~/models`):

- Qwen3-Embedding-0.6B (Q8_0 GGUF) and bge-reranker-v2-m3 (Q8_0 GGUF)
- the Qwen3-Embedding tokenizer files, used by the document chunker
- the Meta MMS-TTS Tagalog and English voices (`facebook/mms-tts-tgl`, `facebook/mms-tts-eng`)
- the Docling layout and TableFormer models, into `$MODELS/docling`

The Qwen3-VL chat model, its `mmproj` file and whisper large-v3-turbo are downloaded with `curl`, as shown in the main README.

Requires the Hugging Face CLI (`hf`, or set `HF=/path/to/hf`) and `uv`.

```sh
./scripts/fetch_models.sh
MODELS=/data/models ./scripts/fetch_models.sh
```

Other startup scripts: `run.sh` in the repository root; icon generation lives in `frontend/scripts/`.
