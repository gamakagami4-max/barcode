from server.repositories.mbstlt_repo import create_stlt

pk = create_stlt(
    code="STL001",
    name="Test Stilt",
    size="M",
    disp=True,
    user="Admin",
)
print("Created ID:", pk)