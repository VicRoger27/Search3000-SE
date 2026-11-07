# Search3000-SE ⚡
> An AI-Augmented Search Engine Built to Rival Google.

Search3000 combines an on-disk inverted index, real-time web crawler, and **Spark-X 2.6 1.7B Q8_0** running locally on your GPU via `llama.cpp` to provide:
1. **SLM Query Intent Reformulation ("What you meant to say")**: Corrects typos, spelling errors, and semantic ambiguity before querying.
2. **Base128 Disk Store**: All indexed sites, postings, and metadata are serialized directly to disk in 7-bit Base128 format inside `data/indexed_sites_base128/`.
3. **Live-Fetch Web Crawler**: Discovers, scrapes, and indexes live web pages on the fly as topics are searched.
4. **Google AI Overview**: Real-time token streaming with source citations powered by Spark-X 2.6 on your RTX 5060 Ti GPU.
5. **Google-Rivaling Minimalist UI**: Clean search aesthetic with instant "Showing results for / Did you mean" overrides and site management sidecar.

---

## Quickstart

Run with one command:
```bash
python run.py
```
This boots the Spark-X GPU engine, mounts the Base128 disk store, and opens the search interface in your default browser at `http://127.0.0.1:8000`.

---

## Architecture Overview

```
Search3000/
├── engine/
│   ├── models/
│   │   └── sparkx_engine.py    # llama-server manager & Spark-X 2.6 client (GPU)
│   ├── storage/
│   │   ├── base128.py          # 7-bit Base128 binary encoder/decoder
│   │   └── disk_index.py       # BM25 ranker & Base128 folder catalog
│   └── crawler/
│       └── live_crawler.py     # Live-fetch web crawler & content parser
├── api/
│   └── main.py                 # FastAPI application
├── web/
│   ├── index.html              # Google-style home & search results page
│   ├── style.css               # Clean Google UI styles
│   └── app.js                  # Search client & streaming AI Overview
├── data/
│   └── indexed_sites_base128/  # On-disk Base128 indexed repository
└── run.py                      # Single-command launcher
```
