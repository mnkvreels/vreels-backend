from sqlalchemy import create_engine
from database import Base, engine  # Ensure engine is properly configured

# WARNING: This will delete all existing data and recreate the tables!
print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)

print("Recreating tables...")
Base.metadata.create_all(bind=engine)

print("Database reset successfully!")
