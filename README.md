# Personalised Search

##  Setup

Follow these steps to set up Elasticsearch and Kibana locally.

### 1. Prerequisites

Make sure you have **Docker installed and running**.

### 2. Start Elasticsearch & Kibana

Run the following command in your terminal:

```bash
curl -fsSL https://elastic.co/start-local | sh
```

### 3. Configure Environment Variables

Navigate to the generated folder and load environment variables:

```bash
cd elastic-start-local
source .env
```

Export the required variables:

```bash
export ES_LOCAL_URL
export ES_LOCAL_API_KEY
export ES_LOCAL_PASSWORD
```

### 4. Verify Connection

Run the following script to ensure everything is working:

```bash
python connect.py
```

If no errors occur, setup is complete

The dataset concists of ≈17k books with meta data (title,author,publish data) and their plot summary https://www.cs.cmu.edu/~dbamman/booksummaries.html .

Run the indexer.py file to index the documents, should take less than <15s
```bash
python indexer.py
```

TODO -

