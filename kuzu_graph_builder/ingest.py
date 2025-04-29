import kuzu
from pathlib import Path
from tqdm import tqdm
import pandas as pd # Required for Kuzu results

from .utils import calculate_sha256, get_logger
from .schema import define_schema

logger = get_logger(__name__)

def get_node_id(conn, table_name, pk_property, pk_value):
    """Helper to get the internal Kuzu ID for a node based on its natural key."""
    # Ensure pk_value is properly quoted if it's a string
    # Kuzu parameters handle this automatically
    # pk_value_quoted = f"'{pk_value}'" if isinstance(pk_value, str) else pk_value
    query = f"MATCH (n:{table_name} {{{pk_property}: $pk_value}}) RETURN n.internalID AS id"
    result = conn.execute(query, {"pk_value": pk_value}).get_as_df()
    if not result.empty:
        return result['id'][0]
    logger.warning(f"Could not find node in {table_name} with {pk_property}={pk_value}")
    return None

def process_directory(db_path: str, repo_root_path_str: str):
    """Processes a directory and populates the Kuzu database using batching (initial setup).

    Args:
        db_path: Path to the Kuzu database directory.
        repo_root_path_str: Path to the root directory of the repository.
    """
    repo_root_path = Path(repo_root_path_str).resolve()
    repo_name = repo_root_path.name

    if not repo_root_path.is_dir():
        logger.error(f"Provided path is not a valid directory: {repo_root_path}")
        return

    logger.info(f"Connecting to database at: {db_path}")
    # TODO: Increase memory limit if needed: db = kuzu.Database(db_path, buffer_pool_size=new_size_in_bytes)
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # Use explicit transaction for bulk operations
    logger.info("Starting ingest transaction...")
    conn.execute("BEGIN TRANSACTION WRITE")

    try:
        # Ensure schema exists
        define_schema(conn)

        # --- Upsert Repository Node ---
        logger.info(f"Processing repository: {repo_name} at {repo_root_path}")
        # Use MERGE for the single repository node
        conn.execute(
            "MERGE (r:Repository {root_path: $path}) ON CREATE SET r.name = $name ON MATCH SET r.name = $name RETURN r.repo_id AS id",
            {"path": str(repo_root_path), "name": repo_name}
        )
        repo_id_result = conn.get_as_df()
        if repo_id_result.empty:
             raise RuntimeError(f"Failed to create or match repository node for {repo_root_path}")
        repo_internal_id = repo_id_result['id'][0]
        logger.info(f"Using Repository ID: {repo_internal_id}")


        # --- Filesystem Traversal (Batched Approach Prep) ---
        logger.info("Scanning directory structure...")
        # TODO: Add ignore patterns (.kuzuignore, etc.)
        # TODO: Add follow_symlinks=False when available or manual check
        # TODO: Parallelize this section
        all_paths = list(repo_root_path.rglob('*'))

        folders_to_add = []
        files_to_add = []
        folder_rels_to_add = [] # (parent_path, child_path)
        file_rels_to_add = []   # (parent_path, child_path)

        logger.info(f"Found {len(all_paths)} items. Collecting data for batch insertion...")

        # Collect data first
        for item_path in tqdm(all_paths, desc="Collecting filesystem data"):
            try:
                if item_path.is_symlink(): # Basic symlink check
                    logger.warning(f"Skipping symlink: {item_path}")
                    continue

                relative_path = item_path.relative_to(repo_root_path)
                depth = len(relative_path.parts)
                full_path_str = str(item_path.resolve())
                parent_path_str = str(item_path.parent.resolve())

                if item_path.is_dir():
                    folders_to_add.append({
                        "path": full_path_str,
                        "depth": depth,
                        "repo_id": repo_internal_id
                    })
                    if item_path.parent == repo_root_path:
                        # Link to Repository later using repo_internal_id and folder path
                        folder_rels_to_add.append((str(repo_root_path), full_path_str, 'repo_folder'))
                    else:
                        folder_rels_to_add.append((parent_path_str, full_path_str, 'folder_folder'))

                elif item_path.is_file():
                    # TODO: Add max file size check
                    file_size = item_path.stat().st_size
                    file_lang = item_path.suffix.lstrip('.')
                    # TODO: Parallelize hashing
                    sha256_hash = calculate_sha256(item_path)

                    if sha256_hash: # Only process if hash could be calculated
                         files_to_add.append({
                            "path": full_path_str,
                            "lang": file_lang,
                            "sha256": sha256_hash,
                            "size": file_size,
                            "repo_id": repo_internal_id
                         })
                         file_rels_to_add.append((parent_path_str, full_path_str))
                    else:
                        logger.warning(f"Skipping file due to hashing error: {item_path}")

            except OSError as e:
                 logger.error(f"Error processing path {item_path}: {e}")
            except Exception as e:
                 logger.error(f"Unexpected error processing path {item_path}: {e}", exc_info=True)

        # --- Batch Insert/Update Nodes ---
        # TODO: Implement actual batching using COPY FROM (preferred) or multi-value INSERT.
        # This requires converting lists of dicts to formats Kuzu accepts (e.g., Pandas DF, Arrow Table, CSV)
        logger.info(f"Collected {len(folders_to_add)} folders and {len(files_to_add)} files.")
        logger.warning("Batch insertion not yet implemented. Falling back to slower row-by-row MERGE.")

        # --- Temporary Fallback: Row-by-row MERGE (Keep for now, replace later) ---
        logger.info("Inserting/Updating Folders (row-by-row fallback)...")
        for folder_data in tqdm(folders_to_add, desc="Merging Folders"):
            conn.execute(
                "MERGE (f:Folder {path: $path}) ON CREATE SET f.depth = $depth, f.repo_id = $repo_id ON MATCH SET f.depth = $depth, f.repo_id = $repo_id",
                folder_data
            )

        logger.info("Inserting/Updating Files (row-by-row fallback)...")
        files_to_parse = []
        for file_data in tqdm(files_to_add, desc="Merging Files"):
            # Check existing hash before merging
            existing_hash_df = conn.execute(
                "MATCH (f:File {path: $path}) RETURN f.sha256 AS sha",
                 {"path": file_data["path"]}
             ).get_as_df()

            needs_parsing = True
            if not existing_hash_df.empty:
                if existing_hash_df['sha'][0] == file_data['sha256']:
                    needs_parsing = False

            # Always MERGE to update metadata like size potentially
            conn.execute(
                """
                MERGE (f:File {path: $path})
                ON CREATE SET f.lang = $lang, f.sha256 = $sha256, f.size = $size, f.repo_id = $repo_id
                ON MATCH SET f.lang = $lang, f.sha256 = $sha256, f.size = $size, f.repo_id = $repo_id
                """,
                file_data
            )
            if needs_parsing:
                files_to_parse.append(file_data["path"])
                # TODO: Add file_id here if we get it back from MERGE

        # --- Batch Insert Relationships ---
        # TODO: Implement actual batching for relationships.
        logger.warning("Batch relationship insertion not yet implemented. Falling back to slower row-by-row MERGE.")

        logger.info("Creating Folder relationships (row-by-row fallback)...")
        for parent_path, child_path, rel_type in tqdm(folder_rels_to_add, desc="Merging Folder Rels"):
            if rel_type == 'repo_folder':
                conn.execute(
                    "MATCH (repo:Repository {root_path: $parent_path}), (folder:Folder {path: $child_path}) MERGE (repo)-[:CONTAINS]->(folder)",
                    {"parent_path": parent_path, "child_path": child_path}
                )
            elif rel_type == 'folder_folder':
                 conn.execute(
                    "MATCH (parent:Folder {path: $parent_path}), (folder:Folder {path: $child_path}) MERGE (parent)-[:CONTAINS]->(folder)",
                    {"parent_path": parent_path, "child_path": child_path}
                 )

        logger.info("Creating File relationships (row-by-row fallback)...")
        for parent_path, child_path in tqdm(file_rels_to_add, desc="Merging File Rels"):
             conn.execute(
                 "MATCH (parent:Folder {path: $parent_path}), (file:File {path: $child_path}) MERGE (parent)-[:CONTAINS]->(file)",
                 {"parent_path": parent_path, "child_path": child_path}
             )

        # --- Code Parsing Step ---
        logger.info(f"{len(files_to_parse)} files marked for parsing.")
        # TODO: Implement Tree-sitter (or other parser) integration here.
        # This function should take the list of file paths (and potentially their internal IDs)
        # perform parsing, and then batch-insert the resulting Function, ModuleClass, CALLS, etc. nodes/rels.
        # parse_and_ingest_code_elements(conn, files_to_parse)
        if files_to_parse:
            logger.warning("Code parsing logic is not yet implemented.")

        # --- Placeholder for other Node types ---
        # TODO: Implement ingestion for Error, Goal, Requirement, Note nodes.

        # --- Commit Transaction ---
        logger.info("Committing transaction...")
        conn.execute("COMMIT")
        logger.info("Filesystem processing and basic ingestion complete.")

    except Exception as e:
        logger.error(f"An error occurred during processing: {repr(e)}", exc_info=True)
        logger.info("Rolling back transaction due to error...")
        try:
            conn.execute("ROLLBACK")
            logger.info("Transaction rolled back.")
        except Exception as rb_e:
            logger.error(f"Failed to rollback transaction: {repr(rb_e)}", exc_info=True)
    finally:
        logger.info("Database connection closed implicitly when DB object goes out of scope.")

# Placeholder for the future parsing function
def parse_and_ingest_code_elements(conn, file_paths):
    logger.info(f"Starting code parsing for {len(file_paths)} files...")
    # 1. Load necessary Tree-sitter grammars based on file extensions
    # 2. For each file:
    #    - Read content
    #    - Parse using Tree-sitter
    #    - Extract relevant nodes (functions, classes, calls, imports)
    #    - Collect data for batch insertion (Functions, ModuleClasses, CALLS, IMPORTS)
    # 3. Batch insert Functions/ModuleClasses
    # 4. Batch insert CALLS/IMPORTS relationships
    pass 