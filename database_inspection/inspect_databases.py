import pandas as pd
import sqlite3

def inspect_database(db_path: str, db_name: str):
    try:
        conn = sqlite3.connect(db_path)
        print(f"Connected to {db_path}")
        
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print(f"No tables found in {db_path}")
            return
            
        print(f"\nTables in {db_path}:")
        for table_name_tuple in tables:
            table_name = table_name_tuple[0]
            print(f"- {table_name}")

            try:
                # Count rows
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                print(f"  Number of rows in '{table_name}': {row_count}")

                # Select all data
                cursor.execute(f"SELECT * FROM {table_name}")
                columns = [description[0] for description in cursor.description]
                rows_to_display = cursor.fetchmany(10)

                if not rows_to_display:
                    print(f"  No data found in '{table_name}'.")
                else:
                    df = pd.DataFrame(rows_to_display, columns=columns)
                    print(f"  First 10 rows of '{table_name}':")
                    print(df.to_string(index=False))

                # Try to get last 5 rows
                order_by_col = None
                if 'slot_datetime' in columns:
                    order_by_col = 'slot_datetime'
                elif 'product_id' in columns:
                    order_by_col = 'product_id'
                elif len(columns) > 0:
                    order_by_col = columns[0]
                    
                if order_by_col:
                    cursor.execute(f"SELECT * FROM {table_name} ORDER BY {order_by_col} DESC LIMIT 5")
                    last_rows = cursor.fetchall()
                    if last_rows:
                        df_last = pd.DataFrame(last_rows, columns=columns)
                        print(f"\n  Last 5 rows of '{table_name}':")
                        print(df_last.to_string(index=False))
                    else:
                        print("\n  Could not fetch last 5 rows (empty result)")
                else:
                    print("\n  Could not determine column for ordering")
                    
            except Exception as e:
                print(f"  Error querying table '{table_name}': {e}")
                
    except Exception as e:
        print(f"Error connecting to database: {e}")
    finally:
        conn.close()
        print(f"\nConnection to {db_path} closed.")

if __name__ == '__main__':
    clinic_db_path = '/content/clinic_appointments_2.db'
    cob_db_path = '/content/cob_system_2.db'
    
    inspect_database(clinic_db_path, "Clinic Database")
    inspect_database(cob_db_path, "COB Database")