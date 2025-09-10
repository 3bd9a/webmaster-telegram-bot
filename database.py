from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import config

Base = declarative_base()
engine = create_engine(config.Config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    language_code = Column(String)
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    total_downloads = Column(Integer, default=0)
    total_size = Column(Float, default=0.0)
    is_banned = Column(Boolean, default=False)

class Download(Base):
    __tablename__ = "downloads"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    url = Column(String, nullable=False)
    domain = Column(String)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    file_path = Column(String)
    file_size = Column(Float)
    total_files = Column(Integer)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    error_message = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
