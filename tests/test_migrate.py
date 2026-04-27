import sqlite3
import pytest
from sqlalchemy import create_engine, Table, Column, Float, String, MetaData, inspect
from rca_extractor.post_processing.migrate import migrate
from rca_extractor.post_processing.db_storage import Base

def test_migrate_adds_columns_to_empty_db(tmp_path, monkeypatch):
    """Verifica que migrate() añade columnas sin pérdida de registros."""
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file}"
    
    # 1. Crear BD v0.x con solo algunas columnas
    # Simulamos el estado anterior (v0.x) con menos columnas
    metadata_old = MetaData()
    projects_old = Table(
        "projects",
        metadata_old,
        Column("archivo", String, primary_key=True),
        Column("potencia_nominal_bruta_mw", Float),
        Column("region_provincia_y_comuna", String),
    )
    
    engine = create_engine(db_url)
    metadata_old.create_all(engine)
    
    # Insertar datos de prueba
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            "INSERT INTO projects (archivo, potencia_nominal_bruta_mw, region_provincia_y_comuna) "
            "VALUES (?, ?, ?)",
            ("118.pdf", 100.5, "Antofagasta")
        )
        conn.commit()
    
    # 2. Ejecutar migración
    # Monkeypatch config.DB_URL para que migrate use nuestra BD temporal
    monkeypatch.setattr("rca_extractor.post_processing.migrate.DB_URL", db_url)
    
    migrate()
    
    # 3. Verificar resultados
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("projects")}
    
    # Verificar que las columnas nuevas de la v1.0.0 (definidas en el ORM actual) existen
    orm_columns = {column.name for column in Base.metadata.tables["projects"].columns}
    assert orm_columns.issubset(columns)
    
    # Verificar que los datos originales están intactos
    with sqlite3.connect(db_file) as conn:
        cursor = conn.execute("SELECT archivo, potencia_nominal_bruta_mw FROM projects")
        row = cursor.fetchone()
        assert row[0] == "118.pdf"
        assert row[1] == 100.5
        
        # Verificar que una columna nueva tiene el valor por defecto (None/NULL en SQLite)
        cursor = conn.execute("SELECT prompt_version FROM projects")
        row = cursor.fetchone()
        assert row[0] is None

def test_migrate_no_op_on_updated_db(tmp_path, monkeypatch):
    """Verifica que migrate() no hace nada si la BD ya está actualizada."""
    db_file = tmp_path / "test_no_op.db"
    db_url = f"sqlite:///{db_file}"
    
    # Crear BD con el schema actual completo
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    
    monkeypatch.setattr("rca_extractor.post_processing.migrate.DB_URL", db_url)
    
    # No debería lanzar error
    migrate()
    
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("projects")}
    orm_columns = {column.name for column in Base.metadata.tables["projects"].columns}
    assert orm_columns == columns
