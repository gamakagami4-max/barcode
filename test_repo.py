from server.repositories.mmconc_repo import create_connection_record

new_id = create_connection_record("Test Connection", "Admin")
print("Created ID:", new_id)
