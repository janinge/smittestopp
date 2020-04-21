from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, SmallInteger, String, Float, Table
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

Base = declarative_base()

service_association = Table('mac_service', Base.metadata,
                             Column('mac_address', Integer, ForeignKey('discovered.mac_address')),
                             Column('service_uuid', Integer, ForeignKey('service.uuid')))


class Random(Base):
    __tablename__ = 'discovered'

    mac_address = Column(String(17), primary_key=True)
    device_id = Column(String(32))
    public = Column(String(17))
    queued = Column(Float)
    connected = Column(Float)
    attempts = Column(Integer, default=0)
    services = relationship("Service", secondary=service_association)
    connect_time = Column(Integer)
    inquiry_time = Column(Integer)
    signal = relationship("Signal")

    def __repr__(self):
        return "<Random(mac_address='%s', device_id='%s', public='%s')>" % (
            self.mac_address, self.device_id, self.public)


class Signal(Base):
    __tablename__ = 'rssi'

    time = Column(Float, primary_key=True)
    rssi = Column(SmallInteger)
    reported = Column(SmallInteger)
    random = Column(String(17), ForeignKey('discovered.mac_address'))


class Service(Base):
    __tablename__ = 'service'

    uuid = Column(String(36), primary_key=True)
    characteristics = Column(SmallInteger)
