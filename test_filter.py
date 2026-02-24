from server.repositories.mmfltr_repo import fetch_column_comments

# Fetch column comments from barcode.mmfltr
comments = fetch_column_comments()

print("Field Comments for barcode.mmfltr:\n")

for column, comment in comments.items():
    print(f"{column} -> {comment}")