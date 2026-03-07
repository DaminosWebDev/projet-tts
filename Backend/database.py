"""
==============================================================================
database.py — Connexion à PostgreSQL et configuration SQLAlchemy
==============================================================================
RESPONSABILITÉS :
  - Créer le moteur de connexion à PostgreSQL (engine)
  - Fournir une session de base de données à chaque requête
  - Définir la classe de base dont héritent tous les modèles

ANALOGIE GLOBALE :
  SQLAlchemy c'est comme un interprète entre Python et PostgreSQL.
  Tu parles Python → l'interprète traduit en SQL → PostgreSQL exécute.
  Tu n'as jamais besoin d'écrire du SQL brut (sauf cas avancés).

FLUX D'UNE REQUÊTE :
  Route FastAPI → get_db() → Session SQLAlchemy → asyncpg → PostgreSQL
==============================================================================
"""

# ── Imports ───────────────────────────────────────────────────────────────────

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
# QU'EST-CE QUE C'EST : Composants SQLAlchemy pour le mode asynchrone.
# POURQUOI async : FastAPI est async — si la DB bloquait, tout le serveur bloquerait.
#   create_async_engine  → crée le moteur de connexion async à PostgreSQL
#   AsyncSession         → une "session" = une transaction avec la DB
#                          Analogie : comme ouvrir un onglet dans un navigateur —
#                          tu fais tes opérations, puis tu fermes l'onglet (commit/close)
#   async_sessionmaker   → une fabrique qui crée des sessions à la demande
#                          Analogie : comme une machine à café — tu appuies sur un bouton,
#                          elle te donne un café (session) frais à chaque fois

from sqlalchemy.orm import DeclarativeBase
# QU'EST-CE QUE C'EST : Classe de base pour définir les modèles SQLAlchemy.
# POURQUOI : Tous nos modèles (User, JobYoutube, etc.) hériteront de cette classe.
#            SQLAlchemy sait alors que ces classes représentent des tables en DB.
# COMMENT : class User(Base) → SQLAlchemy crée automatiquement la table "users"

from config import DATABASE_URL
# QU'EST-CE QUE C'EST : L'URL de connexion à PostgreSQL depuis config.py.
# POURQUOI : Centraliser les credentials en un seul endroit.
# FORMAT : "postgresql+asyncpg://user:password@host:port/dbname"
#   postgresql  → type de base de données
#   asyncpg     → driver Python utilisé pour la connexion
#   tts_user    → notre utilisateur PostgreSQL
#   tts_password→ son mot de passe
#   localhost   → PostgreSQL tourne sur notre machine (via Docker)
#   5432        → port standard PostgreSQL
#   tts_db      → nom de notre base de données


# ── Moteur de connexion ───────────────────────────────────────────────────────

engine = create_async_engine(
    DATABASE_URL,
    # DATABASE_URL = "postgresql+asyncpg://tts_user:tts_password@localhost:5432/tts_db"

    echo=False,
    # echo=True  → affiche TOUT le SQL généré dans les logs (utile pour débugger)
    # echo=False → silencieux en production
    # CONSEIL : mettre True temporairement si tu veux voir ce que SQLAlchemy génère

    pool_size=10,
    # QU'EST-CE QUE C'EST : Nombre de connexions maintenues ouvertes en permanence.
    # ANALOGIE : comme avoir 10 lignes téléphoniques ouvertes en permanence.
    #            Au lieu d'ouvrir/fermer une connexion à chaque requête (lent),
    #            on réutilise les connexions existantes (rapide).
    # POURQUOI 10 : bon équilibre pour une API avec trafic modéré.

    max_overflow=20,
    # QU'EST-CE QUE C'EST : Connexions supplémentaires créables si les 10 sont occupées.
    # ANALOGIE : 20 lignes téléphoniques de secours si les 10 principales sont prises.
    # Total max : pool_size + max_overflow = 30 connexions simultanées maximum.
)
# RÉSULTAT : engine est l'objet central qui gère toutes les connexions à PostgreSQL.
# Il est créé UNE SEULE FOIS au démarrage et partagé par toute l'application.


# ── Fabrique de sessions ──────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    engine,
    # engine = le moteur créé ci-dessus — les sessions l'utilisent pour se connecter

    class_=AsyncSession,
    # class_ = type de session à créer (AsyncSession pour le mode async)

    expire_on_commit=False,
    # QU'EST-CE QUE C'EST : Comportement des objets après un commit().
    # expire_on_commit=True  → après commit(), les objets sont "expirés" :
    #                          accéder à leurs attributs recharge depuis la DB (1 requête de plus)
    # expire_on_commit=False → les objets restent utilisables après commit() sans rechargement
    # POURQUOI False : en mode async, le rechargement automatique peut causer des erreurs.
    #                  On garde les données en mémoire jusqu'à la fin de la requête HTTP.
)
# RÉSULTAT : AsyncSessionLocal est une fabrique.
# Appeler AsyncSessionLocal() crée une nouvelle session prête à l'emploi.


# ── Classe de base des modèles ────────────────────────────────────────────────

class Base(DeclarativeBase):
    """
    Classe de base dont héritent TOUS les modèles SQLAlchemy du projet.

    QU'EST-CE QUE C'EST : Un "moule" vide que chaque modèle va remplir.
    POURQUOI : SQLAlchemy a besoin que tous les modèles partagent la même base
               pour pouvoir créer les tables et gérer les relations entre elles.
    COMMENT : En héritant de Base, une classe devient automatiquement une table SQL.

    EXEMPLE :
        class User(Base):           → crée la table "users" en DB
            __tablename__ = "users"
            id = Column(Integer)    → crée la colonne "id"
    """
    pass
    # pass = la classe est vide pour l'instant
    # DeclarativeBase fournit tout le comportement nécessaire


# ── Dépendance FastAPI : get_db() ─────────────────────────────────────────────

async def get_db():
    """
    Générateur de session de base de données — injecté dans les routes FastAPI.

    QU'EST-CE QUE C'EST : Une fonction qui crée une session DB pour chaque requête
                          HTTP et la ferme automatiquement à la fin.
    POURQUOI : Chaque requête HTTP doit avoir sa propre session DB isolée.
               Si deux requêtes partagent la même session → risque de corruption.
    COMMENT : FastAPI utilise le système de "dépendances" (Depends) pour injecter
              automatiquement get_db() dans les routes qui en ont besoin.

    ANALOGIE : C'est comme un vestiaire au cinéma :
               - Tu arrives (début de requête) → on te donne un casier (session)
               - Tu fais tes opérations (lecture/écriture en DB)
               - Tu repars (fin de requête) → le casier est libéré automatiquement

    UTILISATION DANS UNE ROUTE :
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            # db est automatiquement injecté par FastAPI
            # FastAPI appelle get_db(), récupère la session, l'injecte
            # À la fin de la route, FastAPI ferme la session automatiquement
            result = await db.execute(select(User))
            return result.scalars().all()

    Retourne :
        AsyncSession : une session de base de données prête à l'emploi.
    """
    async with AsyncSessionLocal() as session:
        # async with → gestionnaire de contexte asynchrone
        # AsyncSessionLocal() → crée une nouvelle session
        # La session est automatiquement fermée à la sortie du bloc "with"
        # même en cas d'erreur (équivalent d'un try/finally)

        try:
            yield session
            # yield → ce mot-clé transforme get_db() en "générateur"
            # ANALOGIE : yield = "je te donne la session, fais ce que tu veux,
            #             puis rends-la moi quand tu as fini"
            # La route reçoit "session" et l'utilise
            # Quand la route termine → on revient ici et le "with" ferme la session

            await session.commit()
            # commit() = "valide toutes les modifications faites pendant cette session"
            # ANALOGIE : comme appuyer sur "Enregistrer" dans un document
            # Sans commit() → les modifications sont perdues à la fermeture

        except Exception:
            await session.rollback()
            # rollback() = "annule toutes les modifications si une erreur s'est produite"
            # ANALOGIE : comme "Annuler" (Ctrl+Z) — on revient à l'état initial
            # Garantit que la DB reste cohérente même en cas d'erreur
            raise
            # raise = re-propage l'exception pour que FastAPI retourne une erreur HTTP