from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL

# Moteur central — une seule instance partagée par toute l'application
engine = create_async_engine(
    DATABASE_URL,
    echo=False,       # Passer à True pour logger le SQL généré (debug uniquement)
    pool_size=10,     # Connexions permanentes maintenues ouvertes
    max_overflow=20,  # Connexions supplémentaires si le pool est saturé
)

# Fabrique de sessions — produit une session isolée par requête HTTP
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Objets restent lisibles après commit sans rechargement
)

# Classe parente de tous les modèles — enregistre chaque table dans les métadonnées
class Base(DeclarativeBase):
    pass

# Dépendance FastAPI — injectée via Depends(get_db) dans chaque route qui touche la DB
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise