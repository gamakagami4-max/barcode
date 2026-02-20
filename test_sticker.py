from server.repositories.mmstkr_repo import (
    fetch_all_mmstkr,
    create_mmstkr,
    update_mmstkr,
    soft_delete_mmstkr,
)

print("----- TESTING mmstkr REPOSITORY -----")

# 1️⃣ CREATE
print("Creating record...")
new_id = create_mmstkr(
    name="TEST_STICKER",
    h_in=2.0,
    w_in=1.5,
    h_px=192,
    w_px=144,
    user="TESTER"
)
print("Created ID:", new_id)

# 2️⃣ FETCH
print("Fetching records...")
rows = fetch_all_mmstkr()
print("Total active rows:", len(rows))

# Get created row
created_row = next((r for r in rows if r["pk"] == new_id), None)
print("Created Row:", created_row)

# 3️⃣ UPDATE
print("Updating record...")
update_mmstkr(
    pk=new_id,
    name="TEST_STICKER_UPDATED",
    h_in=2.5,
    w_in=1.75,
    h_px=240,
    w_px=168,
    old_changed_no=created_row["changed_no"],
    user="TESTER"
)
print("Updated.")

# 4️⃣ DELETE (SOFT)
print("Soft deleting record...")
soft_delete_mmstkr(new_id, user="TESTER")
print("Deleted.")

print("Done.")