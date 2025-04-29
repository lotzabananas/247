import kuzu
import time
from .utils import get_logger

logger = get_logger(__name__)

def define_schema(conn):
    """Defines the Kuzu graph schema if it doesn't exist.

    Uses surrogate SERIAL keys for nodes where appropriate and keeps natural keys
    (like paths) as indexed properties.

    Args:
        conn: Active Kuzu connection object.
    """
    logger.info("Defining schema (v0.2 - using SERIAL keys)...")
    try:
        # Node Tables (using SERIAL for PKs, indexing natural keys)
        conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Repository(
                repo_id SERIAL,
                name STRING,
                root_path STRING,
                PRIMARY KEY (repo_id)
            )""")
        conn.execute("CREATE PROPERTY INDEX IF NOT EXISTS ON Repository(root_path)")

        conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Folder(
                folder_id SERIAL,
                path STRING,
                depth INT64,
                repo_id INT64, # FK to Repository.repo_id
                PRIMARY KEY (folder_id)
            )""")
        conn.execute("CREATE PROPERTY INDEX IF NOT EXISTS ON Folder(path)")

        conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS File(
                file_id SERIAL,
                path STRING,
                lang STRING,
                sha256 STRING,
                size INT64,
                repo_id INT64, # FK to Repository.repo_id
                PRIMARY KEY (file_id)
            )""")
        conn.execute("CREATE PROPERTY INDEX IF NOT EXISTS ON File(path)")
        conn.execute("CREATE PROPERTY INDEX IF NOT EXISTS ON File(sha256)") # Index sha for faster updates

        conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS ModuleClass(
                mc_id SERIAL,
                name STRING,
                lang STRING,
                lineno INT64,
                file_id INT64, # FK to File.file_id
                PRIMARY KEY (mc_id)
            )""")
        # Consider index on (file_id, lang, name) if needed for lookups

        conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Function(
                func_id SERIAL,
                name STRING,
                lang STRING,
                signature STRING, # Keep signature for disambiguation
                lineno INT64,
                file_id INT64, # FK to File.file_id
                mc_id INT64, # Optional FK to ModuleClass.mc_id
                embedding_id INT64, # Placeholder for FK to Vector table
                PRIMARY KEY (func_id)
            )""")
        # Consider index on (file_id, lang, name, signature) if needed for lookups

        conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS TestCase(
                test_id SERIAL,
                name STRING,
                framework STRING,
                result STRING,
                ts TIMESTAMP,
                file_id INT64, # FK to File.file_id
                PRIMARY KEY (test_id)
            )""")
        # Consider index on (file_id, name)

        conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Error(
                error_id SERIAL,
                message STRING,
                stack_hash STRING,
                ts TIMESTAMP,
                severity STRING,
                PRIMARY KEY (error_id)
            )""")
        conn.execute("CREATE PROPERTY INDEX IF NOT EXISTS ON Error(stack_hash)")

        conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Goal(
                goal_id SERIAL,
                title STRING,
                priority STRING,
                status STRING,
                due DATE,
                PRIMARY KEY (goal_id)
            )""")
        conn.execute("CREATE PROPERTY INDEX IF NOT EXISTS ON Goal(title)") # Assume title should be unique

        conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Requirement(
                req_id_internal SERIAL, # Internal Kuzu ID
                req_id STRING, # Original requirement ID (e.g., JIRA-123)
                text STRING,
                source STRING,
                PRIMARY KEY (req_id_internal)
            )""")
        conn.execute("CREATE PROPERTY INDEX IF NOT EXISTS ON Requirement(req_id)")

        conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Note(
                note_id SERIAL,
                author STRING,
                content STRING,
                ts TIMESTAMP,
                PRIMARY KEY (note_id)
            )""")

        # Separate Vector Table (as planned)
        # conn.execute("""
        #     CREATE TABLE IF NOT EXISTS Vector(
        #         vec_id SERIAL,
        #         func_id INT64, # FK to Function.func_id
        #         model STRING,
        #         dim INT64,
        #         embedding FLOAT32[768] # Example dimension
        #     )""")
        # conn.execute("CREATE VECTOR INDEX IF NOT EXISTS vector_idx ON Vector(embedding) (TYPE HNSW)")

        # Relationship Tables (using internal IDs)
        # Consider using a single polymorphic CONTAINS later if beneficial
        conn.execute("CREATE REL TABLE IF NOT EXISTS CONTAINS(FROM Repository TO Folder)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS CONTAINS(FROM Folder TO Folder)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS CONTAINS(FROM Folder TO File)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS CONTAINS(FROM File TO ModuleClass)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS CONTAINS(FROM ModuleClass TO Function)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS CONTAINS(FROM File TO Function)")

        conn.execute("CREATE REL TABLE IF NOT EXISTS CALLS(FROM Function TO Function)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS IMPORTS(FROM File TO File)")
        # conn.execute("CREATE REL TABLE IF NOT EXISTS IMPORTS(FROM File TO ModuleClass)")

        conn.execute("CREATE REL TABLE IF NOT EXISTS TESTS(FROM TestCase TO Function)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS ERROR_IN(FROM Error TO Function)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS SATISFIED_BY(FROM Requirement TO Function)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS SATISFIED_BY(FROM Requirement TO ModuleClass)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS TRACKED_BY(FROM Goal TO Requirement)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS TRACKED_BY(FROM Goal TO Note)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS REFERS_TO(FROM Note TO Function)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS REFERS_TO(FROM Note TO File)")

        logger.info("Schema definition complete.")
        # Allow time for schema operations if needed, although usually synchronous
        time.sleep(0.5)

    except Exception as e:
        logger.error(f"Error defining schema: {e}", exc_info=True)
        raise 