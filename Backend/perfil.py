from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from auth import registrar_log  # reutilizamos tu logger de auth
from models import db, Persona, Asistente, AsistenteMedico, Rol, Registro, Evento


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

from datetime import datetime

@perfil_bp.route("/eventos_proximos", methods=["GET"])
@jwt_required()
def eventos_proximos():
    """
    Devuelve los eventos futuros del asistente logueado
    (registros donde fecha_inicio >= ahora).
    """
    identidad = get_jwt_identity()
    id_persona = identidad.get("id_persona")

    persona = Persona.query.get(id_persona)
    if not persona or not persona.asistente:
        return jsonify({"ok": False, "message": "Asistente no encontrado"}), 404

    asistente = persona.asistente
    ahora = datetime.utcnow()

    registros = (
        Registro.query
        .join(Evento, Registro.id_evento == Evento.id_evento)
        .filter(
            Registro.id_asistente == asistente.id_asistente,
            Evento.fecha_inicio >= ahora
        )
        .order_by(Evento.fecha_inicio.asc())
        .all()
    )

    eventos_data = []
    for reg in registros:
        ev = reg.evento
        # Lugar "bonito"
        lugar = ev.ciudad or ev.sede or ev.estado or ev.pais

        eventos_data.append({
            "id_registro": int(reg.id_registro),
            "id_evento": int(ev.id_evento),
            "codigo_evento": ev.codigo,
            "nombre_evento": ev.nombre,
            "fecha_inicio": ev.fecha_inicio.isoformat(),
            "sede": ev.sede,
            "ciudad": ev.ciudad,
            "estado": ev.estado,
            "pais": ev.pais,
            "lugar": lugar,
            "asistencia": reg.asistencia,  # 'si','no','tal_vez','desconocido'
            "confirmado": reg.confirmado,
            "fecha_confirmacion": reg.fecha_confirmacion.isoformat() if reg.fecha_confirmacion else None,
            "invitados": reg.invitados,
            "comentarios": reg.comentarios,
        })

    return jsonify({"ok": True, "eventos": eventos_data}), 200

@perfil_bp.route("/eventos/<int:id_registro>/rsvp", methods=["PUT"])
@jwt_required()
def actualizar_rsvp(id_registro):
    """
    Actualiza la asistencia (RSVP) del registro indicado,
    solo si pertenece al asistente logueado.
    """
    identidad = get_jwt_identity()
    id_persona = identidad.get("id_persona")

    persona = Persona.query.get(id_persona)
    if not persona or not persona.asistente:
        return jsonify({"ok": False, "message": "Asistente no encontrado"}), 404

    asistente = persona.asistente

    registro = Registro.query.get(id_registro)
    if not registro:
        return jsonify({"ok": False, "message": "Registro no encontrado"}), 404

    if registro.id_asistente != asistente.id_asistente:
        # Intentando modificar un registro que no es suyo
        return jsonify({"ok": False, "message": "No tienes permiso para modificar este registro"}), 403

    data = request.get_json() or {}
    nueva_asistencia = data.get("asistencia")
    comentarios = data.get("comentarios")

    if nueva_asistencia not in ("si", "no", "tal_vez", "desconocido"):
        return jsonify({"ok": False, "message": "Valor de asistencia inválido"}), 400

    registro.asistencia = nueva_asistencia
    # Confirmado = True cuando responde algo distinto de "desconocido"
    registro.confirmado = True if nueva_asistencia in ("si", "no", "tal_vez") else None
    registro.fecha_confirmacion = datetime.utcnow()
    if comentarios is not None:
        registro.comentarios = comentarios.strip() or None

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "ok": False,
            "message": "Error al actualizar asistencia",
            "error": str(e)
        }), 500

    # Log de acción
    registrar_log(
        id_asistente=asistente.id_asistente,
        id_registro=registro.id_registro,
        accion="Actualización de RSVP",
        descripcion=f"Usuario {persona.correo} marcó asistencia='{nueva_asistencia}' para el evento {registro.evento.codigo}.",
        actor=persona.correo
    )

    return jsonify({
        "ok": True,
        "message": "Asistencia actualizada correctamente.",
        "asistencia": registro.asistencia,
        "confirmado": registro.confirmado,
        "fecha_confirmacion": registro.fecha_confirmacion.isoformat() if registro.fecha_confirmacion else None
    }), 200
