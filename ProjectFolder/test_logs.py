from user_logs import get_user_profile

user_id = "INSERT-USER-ID-HERE"  # same as in your UI

profile = get_user_profile(user_id)
print("Clicked doc IDs:", profile["clicked_doc_ids"])
print("Recent queries:", profile["recent_queries"])
print("Genres count:", profile["genre_counts"])
print("Authors count:", profile["author_counts"])