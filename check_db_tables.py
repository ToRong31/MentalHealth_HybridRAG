"""
Script to check existing PostgreSQL tables and columns
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "mental_health_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres123")


async def check_tables():
    """Check all tables and their columns in the database"""
    try:
        # Connect to database
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        print(f"✅ Connected to database: {DB_NAME}\n")
        print("=" * 80)
        
        # Get all tables
        tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """
        tables = await conn.fetch(tables_query)
        
        if not tables:
            print("❌ No tables found in the database")
            await conn.close()
            return
        
        print(f"📊 Found {len(tables)} table(s):\n")
        
        # For each table, get column information
        for table in tables:
            table_name = table['table_name']
            print(f"\n🔹 Table: {table_name}")
            print("-" * 80)
            
            # Get columns with details
            columns_query = """
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' 
                    AND table_name = $1
                ORDER BY ordinal_position;
            """
            columns = await conn.fetch(columns_query, table_name)
            
            # Get primary keys
            pk_query = """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = $1::regclass AND i.indisprimary;
            """
            pks = await conn.fetch(pk_query, table_name)
            pk_columns = [pk['attname'] for pk in pks]
            
            # Get foreign keys
            fk_query = """
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' 
                    AND tc.table_name = $1;
            """
            fks = await conn.fetch(fk_query, table_name)
            fk_dict = {fk['column_name']: f"{fk['foreign_table_name']}({fk['foreign_column_name']})" for fk in fks}
            
            # Print column information
            print(f"{'Column Name':<30} {'Type':<20} {'Nullable':<10} {'Key':<15} {'Default'}")
            print("-" * 80)
            
            for col in columns:
                col_name = col['column_name']
                data_type = col['data_type']
                if col['character_maximum_length']:
                    data_type += f"({col['character_maximum_length']})"
                
                nullable = "YES" if col['is_nullable'] == 'YES' else "NO"
                
                # Determine key type
                key_info = ""
                if col_name in pk_columns:
                    key_info = "PK"
                if col_name in fk_dict:
                    key_info += f" FK → {fk_dict[col_name]}"
                
                default = col['column_default'] or ""
                if len(default) > 30:
                    default = default[:27] + "..."
                
                print(f"{col_name:<30} {data_type:<20} {nullable:<10} {key_info:<15} {default}")
            
            # Get row count
            count_query = f"SELECT COUNT(*) FROM {table_name};"
            count = await conn.fetchval(count_query)
            print(f"\n📈 Row count: {count}")
        
        print("\n" + "=" * 80)
        await conn.close()
        print("\n✅ Database check completed successfully!")
        
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        print(f"\nConnection details:")
        print(f"  Host: {DB_HOST}")
        print(f"  Port: {DB_PORT}")
        print(f"  Database: {DB_NAME}")
        print(f"  User: {DB_USER}")


if __name__ == "__main__":
    asyncio.run(check_tables())
