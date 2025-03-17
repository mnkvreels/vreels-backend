from fastapi import FastAPI
from src.database import Base, engine
from src.api import router
import uvicorn
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Social Media App",
    description="Engine Behind Social Media App",
    version="0.1",
)
app.include_router(router)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Use Azure's dynamic port
    uvicorn.run(app, host="0.0.0.0", port=port)