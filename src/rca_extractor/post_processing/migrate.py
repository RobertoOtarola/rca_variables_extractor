import logging
import sqlite3
from sqlalchemy import inspect
from rca_extractor.post_processing.db_storage import get_engine, Base
from rca_extractor.config import DB_URL

log = logging.getLogger(__name__)

def migrate():
    """
    Migrates the SQLite database schema by adding any missing columns defined in the ORM.
    This is necessary for users upgrading from v0.x to v1.0.0+ since SQLAlchemy's
    create_all() does not alter existing tables to add new columns.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    engine = get_engine(DB_URL)
    
    # Check if table exists
    inspector = inspect(engine)
    if "projects" not in inspector.get_table_names():
        log.info("La tabla 'projects' no existe. Ejecutando create_all...")
        Base.metadata.create_all(engine)
        log.info("Tabla creada exitosamente.")
        return

    # Get existing columns from DB
    existing_columns = {col["name"] for col in inspector.get_columns("projects")}
    
    # Get all columns defined in ORM Project model
    orm_columns = {column.name for column in Base.metadata.tables["projects"].columns}
    
    missing_columns = orm_columns - existing_columns
    
    if not missing_columns:
        log.info("La base de datos está actualizada. No se requieren migraciones.")
        return
        
    log.info(f"Se encontraron {len(missing_columns)} columnas faltantes. Iniciando migración...")
    
    # SQLite ALTER TABLE ADD COLUMN
    # Use raw sqlite3 connection for ALTER TABLE as it's simpler
    # We must be careful: SQLite only allows adding one column at a time
    # We will map SQLAlchemy types to SQLite types roughly
    type_map = {
        "VARCHAR": "VARCHAR",
        "FLOAT": "FLOAT",
        "DATETIME": "DATETIME",
        "BOOLEAN": "BOOLEAN",
        "INTEGER": "INTEGER",
    }
    
    try:
        # We need the path from DB_URL, typically "sqlite:///data/processed/rca_data.db"
        db_path = str(engine.url).replace("sqlite:///", "")
        if not db_path:
            db_path = "rca_data.db"
            
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            for col_name in missing_columns:
                # Find the sqlalchemy column object to get its type
                col_obj = Base.metadata.tables["projects"].columns[col_name]
                sql_type = str(col_obj.type)
                sqlite_type = type_map.get(sql_type.split("(")[0].upper(), "VARCHAR")
                
                log.info(f"Agregando columna: {col_name} ({sqlite_type})")
                cursor.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {sqlite_type}")
                
            conn.commit()
            
        log.info("Migración completada exitosamente.")
    except Exception as exc:
        log.error("Error durante la migración: %s", exc, exc_info=True)

if __name__ == "__main__":
    migrate()
