from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
engine = create_engine("sqlite:///jobs.db")
SessionLocal = sessionmaker(bind=engine)

class AnalysisJob(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    plugins = Column(String)
    result = Column(Text)

Base.metadata.create_all(bind=engine)
