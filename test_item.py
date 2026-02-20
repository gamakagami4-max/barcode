from server.repositories.mmitem_repo import (
    fetch_all_item,
    create_item,
    update_item,
    delete_item,
)

print("----- TESTING mmitem REPOSITORY -----")

# 1️⃣ CREATE
print("\nCreating record...")
new_id = create_item(
    code="TEST-ITEM-001",
    name="Test Item",
    brand_id=None,
    filter_id=None,
    prty_id=None,
    stkr_id=None,
    sgdr_id=None,
    warehouse="WH-01",
    pnpr="PN-001",
    inc1="Inc1", inc2="Inc2", inc3="Inc3", inc4="Inc4",
    inc5="Inc5", inc6="Inc6", inc7="Inc7", inc8="Inc8",
    quantity=100,
    unit="PCS",
    user="TESTER"
)
print("Created ID:", new_id)

# 2️⃣ FETCH
print("\nFetching records...")
rows = fetch_all_item()
print("Total active rows:", len(rows))

created_row = next((r for r in rows if r["mlitemiy"] == new_id), None)
print("Created Row:", created_row)

# 3️⃣ UPDATE
print("\nUpdating record...")
update_item(
    item_id=new_id,
    code="TEST-ITEM-001-UPDATED",
    name="Test Item Updated",
    brand_id=None,
    filter_id=None,
    prty_id=None,
    stkr_id=None,
    sgdr_id=None,
    warehouse="WH-02",
    pnpr="PN-002",
    inc1="Inc1-U", inc2="Inc2-U", inc3="Inc3-U", inc4="Inc4-U",
    inc5="Inc5-U", inc6="Inc6-U", inc7="Inc7-U", inc8="Inc8-U",
    quantity=200,
    unit="BOX",
    user="TESTER"
)
print("Updated.")

# Verify update
rows_after_update = fetch_all_item()
updated_row = next((r for r in rows_after_update if r["mlitemiy"] == new_id), None)
print("Updated Row:", updated_row)

# 4️⃣ DELETE (SOFT)
print("\nSoft deleting record...")
delete_item(new_id, user="TESTER")
print("Deleted.")

# Verify deletion (should no longer appear in active rows)
rows_after_delete = fetch_all_item()
deleted_row = next((r for r in rows_after_delete if r["mlitemiy"] == new_id), None)
print("Row still active after delete (should be None):", deleted_row)

print("\nDone.")