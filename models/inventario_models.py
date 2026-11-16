from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Identity,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    Time,
    TIMESTAMP,
)

from models.db import Base


class Role(Base):
    __tablename__ = 'roles'
    __table_args__ = {'schema': 'inventario'}

    id_rol = Column(SmallInteger, Identity(), primary_key=True)
    nombre = Column(String(30), nullable=False, unique=True)


class Tecnico(Base):
    __tablename__ = 'tecnicos'
    __table_args__ = {'schema': 'inventario'}

    identificacion = Column(String(50), primary_key=True)
    nombres = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    ciudad = Column(String(100), nullable=False)
    sede = Column(String(100), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    fecha_registro = Column(TIMESTAMP, nullable=False, default=None)


class Usuario(Base):
    __tablename__ = 'usuarios'
    __table_args__ = {'schema': 'inventario'}

    id_usuario = Column(BigInteger, Identity(), primary_key=True)
    identificacion_tecnico = Column(String(50), ForeignKey('inventario.tecnicos.identificacion'), nullable=True)
    id_rol = Column(SmallInteger, ForeignKey('inventario.roles.id_rol'), nullable=False)
    correo = Column(String(150), nullable=False, unique=True)
    contrasena = Column(Text, nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    fecha_registro = Column(TIMESTAMP, nullable=False, default=None)


class TipoEquipo(Base):
    __tablename__ = 'tipos_equipo'
    __table_args__ = {'schema': 'inventario'}

    id_tipo = Column(SmallInteger, Identity(), primary_key=True)
    nombre = Column(String(50), nullable=False, unique=True)


class CondicionEquipo(Base):
    __tablename__ = 'condiciones_equipo'
    __table_args__ = {'schema': 'inventario'}

    id_condicion = Column(SmallInteger, Identity(), primary_key=True)
    nombre = Column(String(50), nullable=False, unique=True)


class Equipo(Base):
    __tablename__ = 'equipos'
    __table_args__ = {'schema': 'inventario'}

    id_equipo = Column(BigInteger, Identity(), primary_key=True)
    mac = Column(String, nullable=False)
    id_tipo = Column(SmallInteger, ForeignKey('inventario.tipos_equipo.id_tipo'), nullable=False)
    id_condicion_ingreso = Column(SmallInteger, ForeignKey('inventario.condiciones_equipo.id_condicion'), nullable=False)
    id_condicion_entrega = Column(SmallInteger, ForeignKey('inventario.condiciones_equipo.id_condicion'), nullable=True)
    estado = Column(String(20), nullable=False, default='INGRESADO')
    fecha_ingreso = Column(TIMESTAMP, nullable=False, default=None)
    fecha_entrega = Column(TIMESTAMP, nullable=True)
    observaciones = Column(Text, nullable=True)


class Operacion(Base):
    __tablename__ = 'operaciones'
    __table_args__ = {'schema': 'inventario'}

    id_operacion = Column(BigInteger, Identity(), primary_key=True)
    tipo_operacion = Column(String(20), nullable=False)
    identificacion_tecnico = Column(String(50), ForeignKey('inventario.tecnicos.identificacion'), nullable=True)
    id_usuario = Column(BigInteger, ForeignKey('inventario.usuarios.id_usuario'), nullable=False)
    fecha = Column(Date, nullable=False, default=None)
    hora = Column(Time, nullable=False, default=None)
    observaciones = Column(Text, nullable=True)


class DetalleOperacion(Base):
    __tablename__ = 'detalle_operacion'
    __table_args__ = {'schema': 'inventario'}

    id_detalle = Column(BigInteger, Identity(), primary_key=True)
    id_operacion = Column(BigInteger, ForeignKey('inventario.operaciones.id_operacion'), nullable=False)
    id_equipo = Column(BigInteger, ForeignKey('inventario.equipos.id_equipo'), nullable=False)


class Auditoria(Base):
    __tablename__ = 'auditoria'
    __table_args__ = {'schema': 'inventario'}

    id_auditoria = Column(BigInteger, Identity(), primary_key=True)
    id_usuario = Column(BigInteger, ForeignKey('inventario.usuarios.id_usuario'), nullable=True)
    fecha_hora = Column(TIMESTAMP, nullable=False, default=None)
    tabla_afectada = Column(String, nullable=False)
    operacion = Column(String(10), nullable=False)
    registro_afectado = Column(Text, nullable=True)
    informacion_anterior = Column(JSON, nullable=True)
    informacion_nueva = Column(JSON, nullable=True)
