from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    password = Column(String)
    balance = Column(Integer, default=0, nullable=True)

    def __repr__(self):
        return f"User('{self.name}', '{self.password}', {self.balance})"


class Asset(Base):
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    coin_name = Column(String)
    quantity = Column(Integer)
    value_rub = Column(Integer)

    user = relationship("User")


engine = create_engine('sqlite:///database.db')
Session = sessionmaker(bind=engine)
session = Session()
