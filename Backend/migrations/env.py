"""
==============================================================================
migrations/env.py — Configuration Alembic
==============================================================================
QU'EST-CE QUE C'EST :
  Le cerveau d'Alembic. Ce fichier est exécuté à chaque commande alembic
  (generate, upgrade, downgrade...).

RESPONSABILITÉS :
  1. Se connecter à PostgreSQL
  2. Charger tous nos modèles SQLAlchemy
  3. Comparer les modèles avec la DB réelle → détecter les différences
  4. Générer/appliquer les migrations en conséquence

DEUX MODES DE FONCTIONNEMENT :
  - offline : génère le SQL sans se connecter (pour review)
  - online  : se connecte et applique les changements directement
==============================================================================
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Chargement de notre configuration ────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# QU'EST-CE QUE C'EST : Ajoute le dossier Backend/ au PATH Python.
# POURQUOI : Alembic s'exécute depuis n'importe où — il ne sait pas où
#            se trouve notre code. Cette ligne lui dit "cherche les modules
#            dans le dossier Backend/".
# COMMENT :
#   __file__ = chemin de ce fichier (env.py)
#   dirname(__file__) = dossier migrations/
#   dirname(dirname(__file__)) = dossier Backend/
#   sys.path.insert(0, ...) = ajoute Backend/ en premier dans le PATH

# Import de tous nos modèles
# IMPORTANT : tous les modèles doivent être importés ici
# Alembic en a besoin pour détecter les tables à créer/modifier
from database import Base
from models.user import User
from models.job_youtube import JobYoutube
from models.job_tts import JobTTS
from models.job_stt import JobSTT
# Si tu ajoutes un nouveau modèle → l'importer ici aussi

from config import DATABASE_URL_SYNC
# On utilise DATABASE_URL_SYNC (psycopg2) et pas DATABASE_URL (asyncpg)
# car Alembic est synchrone

# ── Configuration Alembic standard ───────────────────────────────────────────

config = context.config
# context.config = objet qui lit alembic.ini

if config.config_file_name is not None:
    fileConfig(config.config_file_name)
# Configure le logging depuis alembic.ini

# On écrase l'URL d'alembic.ini par celle de notre config.py
config.set_main_option("sqlalchemy.url", DATABASE_URL_SYNC)
# POURQUOI écraser : on veut que l'URL vienne de config.py (qui lit .env)
# et pas être écrite en dur dans alembic.ini

target_metadata = Base.metadata
# QU'EST-CE QUE C'EST : Les métadonnées de tous nos modèles.
# Base.metadata contient la description de toutes les tables déclarées
# avec class MonModele(Base).
# Alembic compare ces métadonnées avec la DB réelle pour détecter
# ce qui doit être créé, modifié ou supprimé.


# ── Mode offline ─────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Mode offline : génère le SQL sans se connecter à la DB.
    Utile pour review le SQL avant de l'appliquer.
    Lancé par : alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Mode online ──────────────────────────────────────────────────────────────

def run_migrations_online() -> None:
    """
    Mode online : se connecte à la DB et applique les migrations.
    Lancé par : alembic upgrade head
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # NullPool = pas de pool de connexions pour les migrations
        # Chaque migration ouvre et ferme sa propre connexion
        # POURQUOI : les migrations sont des opérations ponctuelles,
        #            pas besoin de garder des connexions ouvertes
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # compare_type=True → détecte aussi les changements de TYPE de colonne
            # Ex: String(100) → String(255) sera détecté comme un changement
        )
        with context.begin_transaction():
            context.run_migrations()


# ── Point d'entrée ────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()