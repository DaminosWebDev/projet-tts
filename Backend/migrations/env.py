from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

# Ajoute Backend/ au PATH — permet d'importer database, models, config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Enregistre tous les modèles dans Base.metadata — obligatoire pour l'autogenerate
from database import Base
from models.user import User
from models.job_youtube import JobYoutube
from models.job_tts import JobTTS
from models.job_stt import JobSTT

# Driver sync — Alembic ne supporte pas asyncpg
from config import DATABASE_URL_SYNC

config = context.config

# Configure le logging défini dans alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Surcharge l'URL d'alembic.ini — la vraie valeur vient de config.py via .env
config.set_main_option("sqlalchemy.url", DATABASE_URL_SYNC)

# Référence des tables connues — Alembic compare ça avec la DB réelle
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # Génère le SQL brut sans connexion — utile pour review ou environnements restreints
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Connexion directe — applique les migrations sur la DB cible
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Pas de pool — connexion unique ouverte/fermée par migration
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Détecte aussi les changements de type de colonne
        )
        with context.begin_transaction():
            context.run_migrations()


# Point d'entrée — Alembic choisit le mode selon la commande lancée
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()