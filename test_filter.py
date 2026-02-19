from server.repositories.mmfltr_repo import create_fltr

pk = create_fltr(
    name="Test Filter",
    description="Sample filter for testing",
    user="Admin",
)

print("Created ID:", pk)
