from es_client import connector

doc = connector.get(index="booksummaries", id="2298950")
print(doc["_source"].keys())
print("doc_vector present:", "doc_vector" in doc["_source"])
print("doc_vector length:", len(doc["_source"].get("doc_vector", [])))