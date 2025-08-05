from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class Conversion(Base):
    __tablename__ = 'conversions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    from_currency = Column(String)
    to_currency = Column(String)
    amount = Column(Float)
    result = Column(Float)

engine = create_engine('sqlite:///conversions.db')
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)