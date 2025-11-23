from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import csv
import io

from models import (
    db,
    Persona,
    Asistente,
    Rol,
    AsistenteMedico,
    Evento,
    Registro,
    Asistencia,
)

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")


# =====================================
# Helper: parsear código de QR
# =====================================
def _parse_qr_code_to_id_asistente(code: str):
    """
    Recibe el texto leído del QR o lo que se tecleó.
    Soporta:
    - 'AGFI-123'
    - 'agfi-123'
    - '123' (solo número)
    Devuelve id_asistente (int) o None si no se puede parsear.
    """
    if not code:
        return None
    s = str(code).strip()
    if not s:
        return None

    if s.upper().startswith("AGFI-"):
        s = s.split("-", 1)[1].strip()

    try:
        return int(s)
    except ValueError:
        return None


# =====================================
# 1) Verificar token y rol (vista staff)
# =====================================
@staff_bp.route("/verify", methods=["GET"])
@jwt_required()
def verify_staff():
    identidad = get_jwt_identity() or {}
    rol = identidad.get("rol")

    # Aquí permitimos staff y admin, por si un admin quiere entrar al panel de staff
    if rol not in ("staff", "admin"):
        return jsonify({
            "ok": False,
            "message": f"No autorizado para entrar al panel de staff. Rol actual: {rol}"
        }), 403

    return jsonify({
        "ok": True,
        "user": identidad
    }), 200


# =====================================
# 2) Listar eventos (para selects de pase de lista y QR)
# =====================================
@staff_bp.route("/eventos", methods=["GET"])
@jwt_required()
def listar_eventos_staff():
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("staff", "admin"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    eventos = Evento.query.order_by(Evento.fecha_inicio.desc()).all()
    total_oficiales = Asistente.query.count()

    data = []
    for ev in eventos:
        confirmados = Registro.query.filter_by(
            id_evento=ev.id_evento,
            confirmado=True
        ).count()

        data.append({
            "id_evento": ev.id_evento,
            "codigo": ev.codigo,
            "nombre": ev.nombre,
            "fecha": ev.fecha_inicio.strftime("%Y-%m-%d"),
            "lugar": ev.sede,
            "direccion": ev.direccion,
            "ciudad": ev.ciudad,
            "estado": ev.estado,
            "pais": ev.pais,
            "notas": ev.notas,
            "invitados": total_oficiales,
            "confirmados": confirmados
        })

    return jsonify({"ok": True, "eventos": data}), 200


# =====================================
# 3) Pase de lista por evento (JSON)
# =====================================
@staff_bp.route("/pase_lista", methods=["GET"])
@jwt_required()
def pase_lista_evento_staff():
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("staff", "admin"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    id_evento = request.args.get("id_evento", type=int)
    if not id_evento:
        return jsonify({"ok": False, "message": "id_evento es requerido"}), 400

    evento = Evento.query.get(id_evento)
    if not evento:
        return jsonify({"ok": False, "message": "Evento no encontrado"}), 404

    registros = (
        db.session.query(Registro, Asistente, Persona, Rol, Asistencia)
        .join(Asistente, Registro.id_asistente == Asistente.id_asistente)
        .join(Persona, Asistente.id_asistente == Persona.id_persona)
        .join(Rol, Asistente.id_rol == Rol.id_rol)
        .outerjoin(Asistencia, Asistencia.id_registro == Registro.id_registro)
        .filter(Registro.id_evento == id_evento)
        .order_by(Persona.nombre_completo.asc())
        .all()
    )

    data = []
    for reg, asist, persona, rol, asistencia_fisica in registros:
        data.append({
            "id_registro": reg.id_registro,
            "id_asistente": asist.id_asistente,
            "nombre": persona.nombre_completo,
            "correo": persona.correo,
            "empresa": persona.empresa,
            "rol": rol.nombre_rol,
            "asistencia_estado": reg.asistencia,
            "confirmado": reg.confirmado,
            "invitados": reg.invitados,
            "comentarios": reg.comentarios,
            "check_in": True if asistencia_fisica and asistencia_fisica.hora_entrada else False
        })

    return jsonify({
        "ok": True,
        "evento": {
            "id_evento": evento.id_evento,
            "nombre": evento.nombre,
            "fecha": evento.fecha_inicio.strftime("%Y-%m-%d"),
        },
        "registros": data
    }), 200


# =====================================
# 4) Exportar pase de lista a CSV
# =====================================
@staff_bp.route("/pase_lista_csv", methods=["GET"])
@jwt_required()
def exportar_pase_lista_csv_staff():
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("staff", "admin"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    id_evento = request.args.get("id_evento", type=int)
    if not id_evento:
        return jsonify({"ok": False, "message": "id_evento es requerido"}), 400

    evento = Evento.query.get(id_evento)
    if not evento:
        return jsonify({"ok": False, "message": "Evento no encontrado"}), 404

    registros = (
        db.session.query(Registro, Asistente, Persona, Rol, Asistencia)
        .join(Asistente, Registro.id_asistente == Asistente.id_asistente)
        .join(Persona, Asistente.id_asistente == Persona.id_persona)
        .join(Rol, Asistente.id_rol == Rol.id_rol)
        .outerjoin(Asistencia, Asistencia.id_registro == Registro.id_registro)
        .filter(Registro.id_evento == id_evento)
        .order_by(Persona.nombre_completo.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id_evento",
        "codigo_evento",
        "nombre_evento",
        "fecha_evento",
        "id_registro",
        "id_asistente",
        "nombre",
        "correo",
        "empresa",
        "rol",
        "asistencia_estado",
        "confirmado",
        "invitados",
        "comentarios",
        "check_in",
    ])

    for reg, asist, persona, rol, asistencia_fisica in registros:
        writer.writerow([
            evento.id_evento,
            evento.codigo,
            evento.nombre,
            evento.fecha_inicio.strftime("%Y-%m-%d"),
            reg.id_registro,
            asist.id_asistente,
            persona.nombre_completo or "",
            persona.correo or "",
            persona.empresa or "",
            rol.nombre_rol or "",
            reg.asistencia or "",
            "" if reg.confirmado is None else ("1" if reg.confirmado else "0"),
            reg.invitados or 0,
            (reg.comentarios or "").replace("\n", " ").replace("\r", " "),
            "1" if (asistencia_fisica and asistencia_fisica.hora_entrada) else "0",
        ])

    output.seek(0)
    filename = f"pase_lista_evento_{evento.id_evento}.csv"

    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )


# =====================================
# 5) Importar pase de lista desde CSV
# =====================================
@staff_bp.route("/pase_lista_import", methods=["POST"])
@jwt_required()
def importar_pase_lista_csv_staff():
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("staff", "admin"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    id_evento = request.form.get("id_evento", type=int)
    if not id_evento:
        return jsonify({"ok": False, "message": "id_evento es requerido"}), 400

    evento = Evento.query.get(id_evento)
    if not evento:
        return jsonify({"ok": False, "message": "Evento no encontrado"}), 404

    if "file" not in request.files:
        return jsonify({"ok": False, "message": "No se encontró archivo CSV (campo 'file')"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "message": "Nombre de archivo vacío"}), 400

    try:
        content = file.read().decode("utf-8-sig")
    except Exception:
        return jsonify({"ok": False, "message": "No se pudo leer el archivo como UTF-8"}), 400

    reader = csv.DictReader(io.StringIO(content))

    total = 0
    actualizados = 0
    creados = 0
    no_encontrados = []

    def parse_bool(val):
        if val is None:
            return None
        s = str(val).strip().lower()
        if s in ("1", "true", "t", "sí", "si", "yes", "y"):
            return True
        if s in ("0", "false", "f", "no", "n"):
            return False
        return None

    ahora = datetime.utcnow()

    for row in reader:
        total += 1
        correo = (row.get("correo") or "").strip()

        if not correo:
            no_encontrados.append({"motivo": "sin_correo", "row": row})
            continue

        persona = Persona.query.filter_by(correo=correo).first()
        if not persona or not persona.asistente:
            no_encontrados.append({
                "motivo": "persona_o_asistente_no_encontrado",
                "correo": correo
            })
            continue

        asistente = persona.asistente

        reg = Registro.query.filter_by(
            id_evento=id_evento,
            id_asistente=asistente.id_asistente
        ).first()

        if not reg:
            reg = Registro(
                id_evento=id_evento,
                id_asistente=asistente.id_asistente,
                asistencia="desconocido",
                invitados=0,
                confirmado=None,
                fecha_confirmacion=None,
                comentarios=None,
                creado_en=ahora
            )
            db.session.add(reg)
            creados += 1
        else:
            actualizados += 1

        asistencia_estado = (row.get("asistencia_estado") or
                             row.get("asistencia") or "").strip().lower()
        if asistencia_estado in ("si", "sí", "no", "tal_vez", "desconocido"):
            reg.asistencia = asistencia_estado

        confirmado_val = row.get("confirmado") or ""
        confirmado_bool = parse_bool(confirmado_val)
        if confirmado_bool is not None:
            reg.confirmado = confirmado_bool
            reg.fecha_confirmacion = ahora

        invitados_val = row.get("invitados") or ""
        try:
            if invitados_val != "":
                reg.invitados = int(invitados_val)
        except ValueError:
            pass

        comentarios_val = row.get("comentarios") or ""
        if comentarios_val:
            reg.comentarios = comentarios_val

    db.session.commit()

    return jsonify({
        "ok": True,
        "message": "Importación completada.",
        "resumen": {
            "filas_totales": total,
            "registros_creados": creados,
            "registros_actualizados": actualizados,
            "no_encontrados": no_encontrados
        }
    }), 200


# =====================================
# 6) Buscar asistente por QR + evento (incluye datos médicos)
# =====================================
@staff_bp.route("/qr_lookup", methods=["GET"])
@jwt_required()
def qr_lookup_staff():
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("staff", "admin"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    code = (request.args.get("code") or "").strip()
    id_evento = request.args.get("id_evento", type=int)

    if not code or not id_evento:
        return jsonify({"ok": False, "message": "Faltan code o id_evento."}), 400

    id_asistente = _parse_qr_code_to_id_asistente(code)
    if not id_asistente:
        return jsonify({"ok": False, "message": "Código QR inválido."}), 400

    asistente = Asistente.query.get(id_asistente)
    if not asistente or not asistente.persona:
        return jsonify({"ok": False, "message": "Asistente no encontrado."}), 404

    persona = asistente.persona
    rol = asistente.rol

    medico = AsistenteMedico.query.get(id_asistente)

    registro = Registro.query.filter_by(
        id_evento=id_evento,
        id_asistente=id_asistente
    ).first()

    asistencia_fisica = registro.asistencia_registro if registro else None

    asist_json = {
        "id_asistente": id_asistente,
        "codigo_qr": f"AGFI-{id_asistente}",
        "nombre": persona.nombre_completo,
        "correo": persona.correo,
        "empresa": persona.empresa,
        "telefono": persona.telefono,
        "carrera": persona.carrera,
        "generacion": asistente.generacion,
        "rol": rol.nombre_rol if rol else None,
    }

    if medico:
        asist_json.update({
            "tipo_sangre": medico.tipo_sangre,
            "alergias": medico.alergias,
            "medicamentos_actuales": medico.medicamentos_actuales,
            "padecimientos": medico.padecimientos,
            "contacto_emergencia_nombre": medico.contacto_emergencia_nombre,
            "contacto_emergencia_telefono": medico.contacto_emergencia_telefono,
        })

    response = {
        "ok": True,
        "asistente": asist_json,
        "registro": None,
        "asistencia": None
    }

    if registro:
        response["registro"] = {
            "id_registro": registro.id_registro,
            "asistencia_estado": registro.asistencia,
            "confirmado": registro.confirmado,
            "invitados": registro.invitados,
            "comentarios": registro.comentarios,
        }

    if asistencia_fisica:
        response["asistencia"] = {
            "id_asistencia": asistencia_fisica.id_asistencia,
            "hora_entrada": (
                asistencia_fisica.hora_entrada.isoformat()
                if asistencia_fisica.hora_entrada else None
            ),
            "numero_mesa": asistencia_fisica.numero_mesa,
            "numero_asiento": asistencia_fisica.numero_asiento,
            "codigo_gafete": asistencia_fisica.codigo_gafete,
        }

    return jsonify(response), 200


# =====================================
# 7) Actualizar datos y marcar asistencia
# =====================================
@staff_bp.route("/qr_checkin", methods=["POST"])
@jwt_required()
def qr_checkin_staff():
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("staff", "admin"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    data = request.get_json() or {}

    id_evento = data.get("id_evento")
    if not id_evento:
        return jsonify({"ok": False, "message": "id_evento es requerido."}), 400

    try:
        id_evento = int(id_evento)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "id_evento inválido."}), 400

    evento = Evento.query.get(id_evento)
    if not evento:
        return jsonify({"ok": False, "message": "Evento no encontrado."}), 404

    id_asistente = data.get("id_asistente")
    if id_asistente is None:
        code = data.get("code")
        id_asistente = _parse_qr_code_to_id_asistente(code)

    try:
        id_asistente = int(id_asistente)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "No se pudo resolver el asistente."}), 400

    asistente = Asistente.query.get(id_asistente)
    if not asistente or not asistente.persona:
        return jsonify({"ok": False, "message": "Asistente no encontrado."}), 404

    persona = asistente.persona

    nombre      = data.get("nombre")
    correo      = data.get("correo")
    empresa     = data.get("empresa")
    telefono    = data.get("telefono")
    carrera     = data.get("carrera")
    generacion  = data.get("generacion")
    experiencia = data.get("experiencia")
    rol_front   = data.get("rol")

    tipo_sangre                  = data.get("tipo_sangre")
    alergias                     = data.get("alergias")
    medicamentos_actuales        = data.get("medicamentos_actuales")
    padecimientos                = data.get("padecimientos")
    contacto_emergencia_nombre   = data.get("contacto_emergencia_nombre")
    contacto_emergencia_telefono = data.get("contacto_emergencia_telefono")

    if correo and correo != persona.correo:
        existe = Persona.query.filter(
            Persona.correo == correo,
            Persona.id_persona != persona.id_persona
        ).first()
        if existe:
            return jsonify({
                "ok": False,
                "message": "Ya existe otra persona con ese correo."
            }), 409

    if nombre:
        persona.nombre_completo = nombre.strip()
    if correo:
        persona.correo = correo.strip()
    if empresa is not None:
        persona.empresa = empresa.strip() if isinstance(empresa, str) else empresa
    if telefono is not None:
        persona.telefono = telefono.strip() if isinstance(telefono, str) else telefono
    if carrera is not None:
        persona.carrera = carrera.strip() if isinstance(carrera, str) else carrera

    if rol_front:
        rol_obj = Rol.query.filter_by(nombre_rol=rol_front).first()
        if not rol_obj:
            return jsonify({"ok": False, "message": "Rol de asistente no válido."}), 400
        asistente.id_rol = rol_obj.id_rol

    if generacion is not None:
        asistente.generacion = generacion.strip() if isinstance(generacion, str) else generacion
    if experiencia is not None:
        asistente.experiencia = experiencia

    medico = AsistenteMedico.query.get(id_asistente)
    if not medico:
        medico = AsistenteMedico(id_asistente=id_asistente)
        db.session.add(medico)

    if tipo_sangre is not None:
        medico.tipo_sangre = tipo_sangre
    if alergias is not None:
        medico.alergias = alergias
    if medicamentos_actuales is not None:
        medico.medicamentos_actuales = medicamentos_actuales
    if padecimientos is not None:
        medico.padecimientos = padecimientos
    if contacto_emergencia_nombre is not None:
        medico.contacto_emergencia_nombre = contacto_emergencia_nombre
    if contacto_emergencia_telefono is not None:
        medico.contacto_emergencia_telefono = contacto_emergencia_telefono

    ahora = datetime.utcnow()
    registro = Registro.query.filter_by(
        id_evento=id_evento,
        id_asistente=id_asistente
    ).first()

    creado_registro = False
    if not registro:
        registro = Registro(
            id_evento=id_evento,
            id_asistente=id_asistente,
            asistencia="desconocido",
            invitados=0,
            confirmado=None,
            fecha_confirmacion=None,
            comentarios=None,
            creado_en=ahora
        )
        db.session.add(registro)
        creado_registro = True

    registro.asistencia = "si"
    if registro.confirmado is None:
        registro.confirmado = True
        registro.fecha_confirmacion = ahora

    asistencia_obj = Asistencia.query.filter_by(id_registro=registro.id_registro).first()
    created_asistencia = False

    if not asistencia_obj:
        asistencia_obj = Asistencia(
            id_registro=registro.id_registro,
            hora_entrada=ahora,
            codigo_gafete=f"AGFI-{id_asistente}",
            creado_en=ahora
        )
        db.session.add(asistencia_obj)
        created_asistencia = True
    else:
        if not asistencia_obj.hora_entrada:
            asistencia_obj.hora_entrada = ahora

    db.session.commit()

    return jsonify({
        "ok": True,
        "message": "Datos actualizados y asistencia registrada correctamente.",
        "detalles": {
            "id_asistente": id_asistente,
            "id_evento": id_evento,
            "id_registro": registro.id_registro,
            "id_asistencia": asistencia_obj.id_asistencia,
            "hora_entrada": (
                asistencia_obj.hora_entrada.isoformat()
                if asistencia_obj.hora_entrada else None
            ),
            "registro_creado": creado_registro,
            "asistencia_creada": created_asistencia
        }
    }), 200
