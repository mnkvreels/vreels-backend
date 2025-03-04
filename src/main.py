from fastapi import FastAPI
from src.database import Base, engine
from src.api import router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Social Media App",
    description="Engine Behind Social Media App",
    version="0.1",
)
app.include_router(router)