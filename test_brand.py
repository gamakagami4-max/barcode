from server.repositories.mmbrnd_repo import create_brnd

pk = create_brnd(
    code="BR001",
    name="Toyota",
    case_name="Automotive",
    user="Admin",
)

print("Created Brand ID:", pk)
