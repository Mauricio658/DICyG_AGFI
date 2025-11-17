from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ===============================================================
# 1) ROLES
# ===============================================================
class Rol(db.Model):
    __tablename__ = "roles"

    id_rol = db.Column(db.SmallInteger, primary_key=True, autoincrement=True)
    nombre_rol = db.Column(db.Enum('ingeniero', 'becario', 'estudiante',
                                   'administrador', 'staff'),
                           nullable=False, unique=True)
    costo_evento = db.Column(db.Numeric(10, 2), nullable=False)

    asistentes = db.relationship("Asistente", back_populates="rol")


# ===============================================================
# 2) PERSONAS
# ===============================================================
class Persona(db.Model):
    __tablename__ = "personas"

    id_persona = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    nombre_completo = db.Column(db.String(200), nullable=False)
    correo = db.Column(db.String(190), unique=True)
    password_hash = db.Column(db.String(255))
    telefono = db.Column(db.String(20))
    empresa = db.Column(db.String(150))
    puesto = db.Column(db.String(120))
    carrera = db.Column(db.String(120))
    creado_en = db.Column(db.DateTime, nullable=False)
    actualizado_en = db.Column(db.DateTime)

    asistente = db.relationship("Asistente", back_populates="persona", uselist=False)
    invitado_ulm = db.relationship("InvitadoULM", back_populates="persona", uselist=False)


# ===============================================================
# 3) ASISTENTES
# ===============================================================
class Asistente(db.Model):
    __tablename__ = "asistentes"

    id_asistente = db.Column(
        db.BigInteger,
        db.ForeignKey("personas.id_persona", ondelete="CASCADE"),
        primary_key=True
    )
    id_rol = db.Column(db.SmallInteger, db.ForeignKey("roles.id_rol"))
    generacion = db.Column(db.String(40))
    mes_cumple = db.Column(db.SmallInteger)
    dia_cumple = db.Column(db.SmallInteger)
    activo = db.Column(db.Boolean, default=True)

    persona = db.relationship("Persona", back_populates="asistente")
    rol = db.relationship("Rol", back_populates="asistentes")
    registros = db.relationship("Registro", back_populates="asistente")

    preferencias = db.relationship("AsistentePreferencia", back_populates="asistente")

    # 👇 ESTA LÍNEA ES LA QUE FALTABA
    logs = db.relationship("Log", back_populates="asistente")



# ===============================================================
# 4) INVITADOS ÚLTIMO MOMENTO
# ===============================================================
class InvitadoULM(db.Model):
    __tablename__ = "invitados_ultimo_momento"

    id_invitado_ulm = db.Column(
        db.BigInteger,
        db.ForeignKey("personas.id_persona", ondelete="CASCADE"),
        primary_key=True
    )
    id_evento = db.Column(db.BigInteger, db.ForeignKey("eventos.id_evento"), nullable=False)
    creado_en = db.Column(db.DateTime, nullable=False)

    persona = db.relationship("Persona", back_populates="invitado_ulm")
    evento = db.relationship("Evento", back_populates="invitados_ulm")

    logs = db.relationship("Log", back_populates="invitado_ulm")


# ===============================================================
# 5) EVENTOS
# ===============================================================
class Evento(db.Model):
    __tablename__ = "eventos"

    id_evento = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    codigo = db.Column(db.String(50), nullable=False, unique=True)
    nombre = db.Column(db.String(200), nullable=False)
    fecha_inicio = db.Column(db.DateTime, nullable=False)
    sede = db.Column(db.String(200))
    direccion = db.Column(db.String(250))
    ciudad = db.Column(db.String(120))
    estado = db.Column(db.String(120))
    pais = db.Column(db.String(120))
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, nullable=False)

    registros = db.relationship("Registro", back_populates="evento")
    invitados_ulm = db.relationship("InvitadoULM", back_populates="evento")
    logs = db.relationship("Log", back_populates="evento")


# ===============================================================
# 6) REGISTROS (RSVP)
# ===============================================================
class Registro(db.Model):
    __tablename__ = "registros"

    id_registro = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    id_evento = db.Column(db.BigInteger, db.ForeignKey("eventos.id_evento"), nullable=False)
    id_asistente = db.Column(db.BigInteger, db.ForeignKey("asistentes.id_asistente"), nullable=False)

    asistencia = db.Column(
        db.Enum('si', 'no', 'tal_vez', 'desconocido'),
        default='desconocido'
    )
    invitados = db.Column(db.SmallInteger, default=0)
    confirmado = db.Column(db.Boolean)
    fecha_confirmacion = db.Column(db.DateTime)
    comentarios = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, nullable=False)

    evento = db.relationship("Evento", back_populates="registros")
    asistente = db.relationship("Asistente", back_populates="registros")

    asistencia_registro = db.relationship("Asistencia", back_populates="registro", uselist=False)
    logs = db.relationship("Log", back_populates="registro")


# ===============================================================
# 7) ASISTENCIA (CHECK-IN FÍSICO)
# ===============================================================
class Asistencia(db.Model):
    __tablename__ = "asistencia"

    id_asistencia = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    id_registro = db.Column(db.BigInteger, db.ForeignKey("registros.id_registro"), nullable=False)
    hora_entrada = db.Column(db.DateTime)
    numero_mesa = db.Column(db.String(10))
    numero_asiento = db.Column(db.String(10))
    codigo_gafete = db.Column(db.String(64))
    creado_en = db.Column(db.DateTime, nullable=False)

    registro = db.relationship("Registro", back_populates="asistencia_registro")


# ===============================================================
# 8) INDICACIONES MÉDICAS
# ===============================================================
class IndicacionMedica(db.Model):
    __tablename__ = "indicaciones_medicas"

    id_indicacion = db.Column(db.SmallInteger, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(80), nullable=False)
    descripcion = db.Column(db.String(200))

    asistentes = db.relationship("AsistentePreferencia", back_populates="indicacion")


# ===============================================================
# 9) ASISTENTE PREFERENCIA (N:N)
# ===============================================================
class AsistentePreferencia(db.Model):
    __tablename__ = "asistente_preferencia"

    id_asistente = db.Column(db.BigInteger, db.ForeignKey("asistentes.id_asistente"), primary_key=True)
    id_indicacion = db.Column(db.SmallInteger, db.ForeignKey("indicaciones_medicas.id_indicacion"), primary_key=True)
    notas = db.Column(db.String(200))

    asistente = db.relationship("Asistente", back_populates="preferencias")
    indicacion = db.relationship("IndicacionMedica", back_populates="asistentes")


# ===============================================================
# 10) LOGS
# ===============================================================
class Log(db.Model):
    __tablename__ = "logs"

    id_log = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    actor = db.Column(db.String(150))
    accion = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)

    id_evento = db.Column(db.BigInteger, db.ForeignKey("eventos.id_evento"))
    id_asistente = db.Column(db.BigInteger, db.ForeignKey("asistentes.id_asistente"))
    id_registro = db.Column(db.BigInteger, db.ForeignKey("registros.id_registro"))
    id_invitado_ulm = db.Column(db.BigInteger, db.ForeignKey("invitados_ultimo_momento.id_invitado_ulm"))

    creado_en = db.Column(db.DateTime, nullable=False)

    evento = db.relationship("Evento", back_populates="logs")
    asistente = db.relationship("Asistente", back_populates="logs", foreign_keys=[id_asistente])
    registro = db.relationship("Registro", back_populates="logs")
    invitado_ulm = db.relationship("InvitadoULM", back_populates="logs")
