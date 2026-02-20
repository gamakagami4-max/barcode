from server.repositories.mmprty_repo import create_prty

pk = create_prty(
    ingredient="Sugar",
    spanish="Azucar",
    pronunciation="A-thu-car",
    german="Zucker",
    user="Admin",
)

print("Created ID:", pk)
