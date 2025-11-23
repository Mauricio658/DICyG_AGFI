from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token
from datetime import timedelta
from flask_cors import CORS
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Persona, Asistente, Rol

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def registrar_log(
    id_asistente=None,
    accion="",
    descripcion=None,
    id_evento=None,
    id_registro=None,
    id_invitado_ulm=None,
    actor=None
):
    from models import Log  # import local para evitar problemas de import circular
    try:
        log = Log(
            actor=actor,
            accion=accion,
            descripcion=descripcion,
            id_evento=id_evento,
            id_asistente=id_asistente,
            id_registro=id_registro,
            id_invitado_ulm=id_invitado_ulm,
            creado_en=datetime.utcnow()  # 🔥 AQUÍ LE DAMOS VALOR SIEMPRE
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR LOG] No se pudo registrar el log: {e}")


#============================ Rutas de Auth ===========================#

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}

    correo = data.get("correo") or data.get("email")
    password = data.get("password") or data.get("pass")

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if not correo or not password:
        return jsonify({
            "ok": False,
            "message": "Correo y contraseña son obligatorios."
        }), 400

    persona = Persona.query.filter_by(correo=correo).first()
    if not persona:
        return jsonify({
            "ok": False,
            "message": "Usuario incorrectos."
        }), 401

    #if not persona.password_hash or not check_password_hash(persona.password_hash, password):
    if persona.password_hash != password:        
        return jsonify({
            "ok": False,
            "message": "Contraseña incorrectos."
        }), 401

    # Buscar rol a través de Asistente
    asistente = Asistente.query.filter_by(id_asistente=persona.id_persona).first()
    rol_nombre = "user"
    if asistente and asistente.id_rol:
        rol = Rol.query.get(asistente.id_rol)
        if rol:
            # mapeamos el enum de la tabla
            if rol.nombre_rol == "administrador":
                rol_nombre = "admin"
            elif rol.nombre_rol == "staff":
                rol_nombre = "staff"
            else:
                rol_nombre = "user"

    # Payload del JWT
    identidad = {
        "id_persona": int(persona.id_persona),
        "correo": persona.correo,
        "nombre": persona.nombre_completo,
        "rol": rol_nombre
    }

    access_token = create_access_token(
        identity=identidad,
        expires_delta=timedelta(hours=8)
    )

     # Log de éxito
    id_asistente_log = asistente.id_asistente if asistente else None
    registrar_log(
        id_asistente=id_asistente_log,
        accion=f"Login EXITOSO desde IP {ip}. Usuario: {persona.correo}, Rol: {rol_nombre}",
        descripcion=f"User-Agent: {request.headers.get('User-Agent', '')}",
        actor=persona.correo
    )

    return jsonify({
        "ok": True,
        "message": "Login exitoso",
        "token": access_token,
        "user": identidad
    }), 200

#=========================== Ruta de Logout ===========================#

@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    identidad = get_jwt_identity()  # viene del JWT
    correo = identidad.get("correo")
    id_persona = identidad.get("id_persona")

    # Determinar si es asistente para logs
    asistente = Asistente.query.filter_by(id_asistente=id_persona).first()
    id_asistente_log = asistente.id_asistente if asistente else None

    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    # Registrar log
    registrar_log(
        id_asistente=id_asistente_log,
        accion=f"Logout EXITOSO desde IP {ip}. Usuario: {correo}",
        descripcion=f"User-Agent: {request.headers.get('User-Agent', '')}",
        actor=correo
    )

    return jsonify({
        "ok": True,
        "message": "Logout exitoso. El token debe eliminarse del cliente."
    }), 200
