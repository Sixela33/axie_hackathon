from sqlalchemy import Column, Integer, BigInteger, Numeric, Text, text
from database import Base

class EthTxs(Base):
    __tablename__ = 'ethtxs'
    
    time = Column(Integer, primary_key=True)
    txfrom = Column(Text)
    txto = Column(Text)
    gas = Column(BigInteger)
    gasprice = Column(BigInteger)
    block = Column(Integer)
    txhash = Column(Text)
    value = Column(Numeric)
    contract_to = Column(Text)
    contract_value = Column(Text)

class MaxBlock(Base):
    __table__ = text("max_block")