"""SQLAlchemy ORM models: users, networks, junctions, roads, observed_flows, solutions."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    networks: Mapped[list["Network"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Network(Base):
    __tablename__ = "networks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    method: Mapped[str] = mapped_column(String(16), default="manual")  # 'manual' | 'map'
    map_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # pickup, destination, route ...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    user: Mapped[User] = relationship(back_populates="networks")
    junctions: Mapped[list["Junction"]] = relationship(back_populates="network", cascade="all, delete-orphan",
                                                       order_by="Junction.id")
    roads: Mapped[list["Road"]] = relationship(back_populates="network", cascade="all, delete-orphan",
                                               order_by="Road.position")
    solutions: Mapped[list["Solution"]] = relationship(back_populates="network", cascade="all, delete-orphan",
                                                       order_by="Solution.id")


class Junction(Base):
    __tablename__ = "junctions"
    __table_args__ = (UniqueConstraint("network_id", "key", name="uq_junction_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(80))
    x: Mapped[float] = mapped_column(default=0.0)
    y: Mapped[float] = mapped_column(default=0.0)
    lat: Mapped[float | None] = mapped_column(nullable=True)
    lng: Mapped[float | None] = mapped_column(nullable=True)
    node_type: Mapped[str] = mapped_column(String(16), default="junction")
    # D = net vehicles leaving the modelled network here (+ exit, - enter): incoming - outgoing = D
    net_demand: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    network: Mapped[Network] = relationship(back_populates="junctions")


class Road(Base):
    __tablename__ = "roads"
    __table_args__ = (UniqueConstraint("network_id", "key", name="uq_road_key"),
                      CheckConstraint("source_id <> target_id", name="ck_road_no_self_loop"))
    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(120), default="")  # road name
    source_id: Mapped[int] = mapped_column(ForeignKey("junctions.id", ondelete="CASCADE"))
    target_id: Mapped[int] = mapped_column(ForeignKey("junctions.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    length_m: Mapped[float | None] = mapped_column(nullable=True)
    geometry: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [[lat, lng], ...] from source to target
    osm_way_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    highway: Mapped[str] = mapped_column(String(32), default="")
    origin: Mapped[str] = mapped_column(String(8), default="user")  # 'osm' | 'user'
    network: Mapped[Network] = relationship(back_populates="roads")
    source: Mapped[Junction] = relationship(foreign_keys=[source_id])
    target: Mapped[Junction] = relationship(foreign_keys=[target_id])
    observed: Mapped["ObservedFlow | None"] = relationship(back_populates="road", cascade="all, delete-orphan",
                                                           uselist=False)


class ObservedFlow(Base):
    """A sensor measurement. A road WITHOUT a row here is an unknown (variable) road."""
    __tablename__ = "observed_flows"
    __table_args__ = (CheckConstraint("value >= 0", name="ck_flow_nonneg"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    road_id: Mapped[int] = mapped_column(ForeignKey("roads.id", ondelete="CASCADE"), unique=True)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    road: Mapped[Road] = relationship(back_populates="observed")


class Solution(Base):
    __tablename__ = "solutions"
    id: Mapped[int] = mapped_column(primary_key=True)
    network_id: Mapped[int] = mapped_column(ForeignKey("networks.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    classification: Mapped[str] = mapped_column(String(16))  # unique | infinite | none
    rank: Mapped[int] = mapped_column(Integer)
    n_equations: Mapped[int] = mapped_column(Integer)
    n_unknowns: Mapped[int] = mapped_column(Integer)
    free_variables: Mapped[list] = mapped_column(JSON, default=list)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)  # network changed since it was solved
    network: Mapped[Network] = relationship(back_populates="solutions")
