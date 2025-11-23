from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from models import db, Persona, Asistente, AsistenteMedico, Rol
from auth import registrar_log  # reutilizamos tu logger de auth


perfil_bp = Blueprint("perfil", __name__, url_prefix="/perfil")


# ==========================
# 1) Obtener perfil completo
# ==========================
@perfil_bp.route("/me", methods=["GET"])
@jwt_required()
def obtener_perfil():
    identidad = get_jwt_identity()
    id_persona = identidad.get("id_persona")

    persona = Persona.query.get(id_persona)
    if not persona:
        return jsonify({"ok": False, "message": "Persona no encontrada"}), 404

    asistente = persona.asistente
    medico = asistente.datos_medicos if asistente else None
    rol = asistente.rol if asistente and asistente.id_rol else None

    perfil = {
        "id_persona": int(persona.id_persona),
        "nombre_completo": persona.nombre_completo,
        "correo": persona.correo,
        "telefono": persona.telefono,
        "empresa": persona.empresa,
        "puesto": persona.puesto,
        "carrera": persona.carrera,
        "creado_en": persona.creado_en.isoformat() if persona.creado_en else None,
        "actualizado_en": persona.actualizado_en.isoformat() if persona.actualizado_en else None,
        "asistente": None,
        "rol": None,
        "medico": None,
        "ultima_actualizacion": (
            persona.actualizado_en or persona.creado_en
        ).isoformat() if (persona.actualizado_en or persona.creado_en) else None,
    }

    if asistente:
        perfil["asistente"] = {
            "id_asistente": int(asistente.id_asistente),
            "id_rol": asistente.id_rol,
            "generacion": asistente.generacion,
            "mes_cumple": asistente.mes_cumple,
            "dia_cumple": asistente.dia_cumple,
            "experiencia": asistente.experiencia,
            "activo": asistente.activo,
        }

    if rol:
        perfil["rol"] = {
            "id_rol": rol.id_rol,
            "nombre_rol": rol.nombre_rol,
            "costo_evento": str(rol.costo_evento),
        }

    if medico:
        perfil["medico"] = {
            "tipo_sangre": medico.tipo_sangre,
            "alergias": medico.alergias,
            "medicamentos_actuales": medico.medicamentos_actuales,
            "padecimientos": medico.padecimientos,
            "contacto_emergencia_nombre": medico.contacto_emergencia_nombre,
            "contacto_emergencia_telefono": medico.contacto_emergencia_telefono,
        }

    return jsonify({"ok": True, "perfil": perfil}), 200


# =====================================
# 2) Actualizar datos personales / AGFI
#   (form: Datos personales en perfil.html)
# =====================================
@perfil_bp.route("/me", methods=["PUT"])
@jwt_required()
def actualizar_perfil():
    identidad = get_jwt_identity()
    id_persona = identidad.get("id_persona")

    persona = Persona.query.get(id_persona)
    if not persona:
        return jsonify({"ok": False, "message": "Persona no encontrada"}), 404

    asistente = persona.asistente

    data = request.get_json() or {}

    # Campos que vienen del form "Datos personales" en perfil.html :contentReference[oaicite:0]{index=0}
    nombre = data.get("nombre_completo")
    correo = data.get("correo")
    telefono = data.get("telefono")
    empresa = data.get("empresa")
    puesto = data.get("puesto")
    experiencia = data.get("experiencia")  # si luego agregas campo en el front

    if nombre is not None:
        persona.nombre_completo = nombre.strip()
    if correo is not None:
        persona.correo = correo.strip()
    if telefono is not None:
        persona.telefono = telefono.strip() or None
    if empresa is not None:
        persona.empresa = empresa.strip() or None
    if puesto is not None:
        persona.puesto = puesto.strip() or None

    persona.actualizado_en = datetime.utcnow()

    if asistente and experiencia is not None:
        asistente.experiencia = experiencia.strip() or None

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": "Error al guardar", "error": str(e)}), 500

    # Log
    id_asistente_log = asistente.id_asistente if asistente else None
    registrar_log(
        id_asistente=id_asistente_log,
        accion="Actualización de datos personales",
        descripcion=f"Usuario {persona.correo} actualizó su perfil desde vista usuario.",
        actor=persona.correo
    )

    return jsonify({"ok": True, "message": "Datos personales actualizados correctamente."}), 200


# =====================================
# 3) Actualizar datos médicos / emergencia
#   (form: Consideraciones médicas en perfil.html)
# =====================================
@perfil_bp.route("/medico", methods=["PUT"])
@jwt_required()
def actualizar_medico():
    identidad = get_jwt_identity()
    id_persona = identidad.get("id_persona")

    persona = Persona.query.get(id_persona)
    if not persona or not persona.asistente:
        return jsonify({"ok": False, "message": "Asistente no encontrado para esta persona"}), 404

    asistente = persona.asistente

    data = request.get_json() or {}

    tipo_sangre = data.get("tipo_sangre")
    alergias = data.get("alergias")
    medicamentos_actuales = data.get("medicamentos_actuales")
    padecimientos = data.get("padecimientos")
    contacto_nombre = data.get("contacto_emergencia_nombre")
    contacto_tel = data.get("contacto_emergencia_telefono")

    # Obtener o crear registro médico 1:1 :contentReference[oaicite:1]{index=1}
    medico = asistente.datos_medicos
    if not medico:
        medico = AsistenteMedico(id_asistente=asistente.id_asistente)
        db.session.add(medico)

    if tipo_sangre is not None:
        medico.tipo_sangre = tipo_sangre.strip() or None
    if alergias is not None:
        medico.alergias = alergias.strip() or None
    if medicamentos_actuales is not None:
        medico.medicamentos_actuales = medicamentos_actuales.strip() or None
    if padecimientos is not None:
        medico.padecimientos = padecimientos.strip() or None
    if contacto_nombre is not None:
        medico.contacto_emergencia_nombre = contacto_nombre.strip() or None
    if contacto_tel is not None:
        medico.contacto_emergencia_telefono = contacto_tel.strip() or None

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "message": "Error al guardar datos médicos", "error": str(e)}), 500

    registrar_log(
        id_asistente=asistente.id_asistente,
        accion="Actualización de datos médicos",
        descripcion=f"Usuario {persona.correo} actualizó sus consideraciones médicas.",
        actor=persona.correo
    )

    return jsonify({"ok": True, "message": "Consideraciones médicas actualizadas correctamente."}), 200


# =====================================
# 4) Obtener solo la parte médica (opcional)
#    Útil si luego quieres separar requests
# =====================================
@perfil_bp.route("/medico", methods=["GET"])
@jwt_required()
def obtener_medico():
    identidad = get_jwt_identity()
    id_persona = identidad.get("id_persona")

    persona = Persona.query.get(id_persona)
    if not persona or not persona.asistente:
        return jsonify({"ok": False, "message": "Asistente no encontrado"}), 404

    asistente = persona.asistente
    medico = asistente.datos_medicos

    if not medico:
        return jsonify({
            "ok": True,
            "medico": None
        }), 200

    data = {
        "tipo_sangre": medico.tipo_sangre,
        "alergias": medico.alergias,
        "medicamentos_actuales": medico.medicamentos_actuales,
        "padecimientos": medico.padecimientos,
        "contacto_emergencia_nombre": medico.contacto_emergencia_nombre,
        "contacto_emergencia_telefono": medico.contacto_emergencia_telefono,
    }

    return jsonify({"ok": True, "medico": data}), 200
