from server.repositories.mmconc_repo import create_connection_record, create_table_record

# Just a connection
conn_id = create_connection_record("TestoConnection", "Admin")
print("Connection ID:", conn_id)

# A connection + table in one shot
table_id = create_table_record("Test Connection", "dbo.Orders", "SELECT * FROM dbo.Orders", "Admin")
print("Table ID:", table_id)