# Personalized Book Search Engine

A personalized search engine for books built on Elasticsearch and Flask. The system combines BM25 lexical retrieval with a personalized reranking stage that uses explicit user preferences (favorite genres, authors, books, interests) and implicit click feedback to adapt search results to individual users.

Built for the DD2477 Search Engines and Information Retrieval Systems course at KTH.

## Features

- **Multi-field BM25 retrieval** over title, author, summary and genres
- **Dense semantic matching** using `all-MiniLM-L6-v2` sentence embeddings (384-d)
- **Explicit user profiles** — favorite genres, authors, books and free-text interests
- **Implicit click feedback** — clicked document/genre/author counts with weighted vector averaging
- **Adaptive profile blending** — smooth transition from explicit preferences (cold start) to click-dominated profiles
- **7-component reranking score** — normalized BM25 + genre/author/book match + repeat-click bonus + query-doc and user-doc semantic similarity
- **Web interface** with profile form, search, click logging and CSV export

## Project Structure

```
ProjectFolder/
├── app.py                 # Flask web app (search, profile, click logging, export)
├── indexer.py             # Parses CMU dataset, generates embeddings, bulk-indexes
├── search_engine.py       # BM25 retrieval + personalized reranking
├── user_profiles.py       # Profile CRUD and click-driven updates
├── user_logs.py           # Append-only click event logging
├── embeddings_utils.py    # Model loading (LRU-cached), encoding, vector ops
├── es_mappings.py         # Index settings and mappings for all 3 indices
├── es_client.py           # Singleton Elasticsearch connection
├── Website/
│   └── index.html         # Frontend template
├── Corpus/
│   └── README             # Dataset description (data file not included)
└── EvaluationFolder/
    ├── eval.ipynb          # Evaluation notebook (P@10, nDCG@10)
    └── Personas/           # 12 persona CSV files with relevance labels
```

## Prerequisites

- **Python 3.10+**
- **Docker** (for running Elasticsearch locally)

## Setup

### 1. Start Elasticsearch

```bash
curl -fsSL https://elastic.co/start-local | sh
```

This creates an `elastic-start-local/` directory with a `.env` file containing connection credentials.

### 2. Initialize the enviroment

```bash
conda env create -f environment.yml
```

### 3. Activate the enviroment

```bash 
conda activate personalized-search
```

### 4. Index the documents

```bash
cd ProjectFolder
python indexer.py
```

This parses the 16,559 book records, generates 384-d sentence embeddings in batches of 32, and bulk-indexes them into Elasticsearch (chunk size 200). Takes approximately 5–10 minutes depending on hardware.

Three Elasticsearch indices are created:
- **`booksummaries`** — book documents with metadata and dense vectors
- **`user_profiles`** — per-user explicit preferences and implicit feedback
- **`user_logs`** — append-only click event log

### 5. Run the application

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Usage

1. **Search** — enter a query to get BM25-ranked results.
2. **Set preferences** — fill in the profile form (favorite genres, authors, books, interests) and submit. Subsequent searches will use personalized reranking.
3. **Click results** — each click is logged and updates your implicit profile. As clicks accumulate, the system gradually shifts from explicit preferences to behavioral signals.
4. **Export** — download search results as CSV.

Enter a `User ID` in the search form to enable personalization. Searching without a User ID returns baseline BM25 results.


## Evaluation

The `EvaluationFolder/` contains pre-computed evaluation data:

- **12 synthetic personas** (`Personas/*.csv`) with search results and relevance labels across three settings (Baseline, No clicks, After clicks)
- **`eval.ipynb`** — Jupyter notebook that computes P@10 and nDCG@10 from the CSV files

To reproduce the metrics and plots:

```bash
cd EvaluationFolder
jupyter notebook eval.ipynb
```

### Results Summary

| Setting | Avg P@10 | Avg nDCG@10 |
|---------|----------|-------------|
| Baseline | 0.621 | 0.630 |
| No clicks (explicit only) | 0.688 | 0.708 |
| After clicks | 0.733 | 0.757 |

## Authors

Jonathan Tadesse, Shuangyu Zhu, Aditi Palavalli, Jinghua Yang
