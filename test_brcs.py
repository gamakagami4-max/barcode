from server.repositories.mmbrcs_repo import (
    fetch_all_mmbrcs,
    create_mmbrcs,
    update_mmbrcs,
    delete_mmbrcs,
)

print("----- TESTING mmbrcs REPOSITORY -----")

# 1️⃣ CREATE
print("Creating record...")
new_id = create_mmbrcs(
    code="ABC",
    type_case=True,
    user="TESTER"
)
print("Created ID:", new_id)

# 2️⃣ FETCH
print("Fetching records...")
rows = fetch_all_mmbrcs()
print("Total active rows:", len(rows))

# 3️⃣ UPDATE
print("Updating record...")
update_mmbrcs(
    mmbrcs_id=new_id,
    code="ABD",
    type_case=False,
    user="TESTER"
)
print("Updated.")

# 4️⃣ DELETE (SOFT)
print("Soft deleting record...")
delete_mmbrcs(new_id, user="TESTER")
print("Deleted.")

print("Done.")
