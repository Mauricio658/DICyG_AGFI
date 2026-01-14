from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from models import (
    db,
    Persona,
    Asistente,
    Rol,
    AsistenteMedico,
    Evento,
    Registro,
    BuzonComentario,
    Asistencia,
    InvitadoULM,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
from io import BytesIO
from flask import send_file, current_app
import qrcode
from PIL import Image, ImageDraw, ImageFont
import csv             
import io                     
import os    

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

    # Si viene con prefijo AGFI-
    if s.upper().startswith("AGFI-"):
        s = s.split("-", 1)[1].strip()

    try:
        return int(s)
    except ValueError:
        return None


# =====================================
# 1) Verificar token y rol (admin/staff)
# =====================================
@admin_bp.route("/verify", methods=["GET"])
@jwt_required()
def verify_admin():
    identidad = get_jwt_identity() or {}
    print("DEBUG verify_admin identidad:", identidad)

    rol = identidad.get("rol")

    # admin y staff pueden entrar al panel
    if rol not in ("admin", "staff"):
        return jsonify({
            "ok": False,
            "message": f"No autorizado para entrar al panel administrativo. Rol actual: {rol}"
        }), 403

    return jsonify({
        "ok": True,
        "user": identidad
    }), 200


# =====================================
# 3) Alta de asistentes formales
# =====================================
@admin_bp.route("/asistentes", methods=["POST"])
@jwt_required()
def crear_asistente_formal():
    identidad = get_jwt_identity() or {}
    # admin y staff pueden dar de alta asistentes
    if identidad.get("rol") not in ("admin", "staff"):
        return jsonify({
            "ok": False,
            "message": "Solo admin o staff pueden dar de alta asistentes."
        }), 403

    data = request.get_json() or {}

    nombre = data.get("nombre")
    correo = data.get("correo")
    password = data.get("password") 
    telefono = data.get("telefono")
    empresa = data.get("empresa")
    puesto = data.get("puesto")
    rol_front = data.get("rol")  # ingeniero / becario / estudiante
    carrera = data.get("carrera")
    generacion = data.get("generacion")
    fecha_nac = data.get("fecha_nacimiento")  # "YYYY-MM-DD"

    experiencia = data.get("experiencia")
    tipo_sangre = data.get("tipo_sangre")
    alergias = data.get("alergias")
    medicamentos_actuales = data.get("medicamentos_actuales")
    padecimientos = data.get("padecimientos")
    contacto_emergencia_nombre = data.get("contacto_emergencia_nombre")
    contacto_emergencia_telefono = data.get("contacto_emergencia_telefono")


    if not nombre or not correo or not rol_front:
        return jsonify({
            "ok": False,
            "message": "Faltan campos obligatorios (nombre, correo o rol)."
        }), 400

    # Verificar que no exista ya una persona con ese correo
    existente = Persona.query.filter_by(correo=correo).first()
    if existente:
        return jsonify({
            "ok": False,
            "message": "Ya existe una persona con ese correo."
        }), 409

    # Crear persona
    persona = Persona(
        nombre_completo=nombre,
        correo=correo,
        password_hash=password,   # QUEDA SOLO ESTE
        telefono=telefono,
        empresa=empresa,
        puesto=puesto,
        carrera=carrera,
        creado_en=datetime.utcnow(),
    )

    db.session.add(persona)
    db.session.flush()  # para tener persona.id_persona

    # Rol en BD (ingeniero/becario/estudiante)
    rol_obj = Rol.query.filter_by(nombre_rol=rol_front).first()
    if not rol_obj:
        db.session.rollback()
        return jsonify({"ok": False, "message": "Rol de asistente no encontrado en la base."}), 500

    # Procesar fecha nacimiento → mes/día para cumpleaños
    mes = None
    dia = None
    if fecha_nac:
        try:
            f = datetime.strptime(fecha_nac, "%Y-%m-%d").date()
            mes, dia = f.month, f.day
        except Exception:
            pass

    # Crear asistente 1 a 1 con persona
    asistente = Asistente(
        id_asistente=persona.id_persona,
        id_rol=rol_obj.id_rol,
        generacion=generacion,
        mes_cumple=mes,
        dia_cumple=dia,
        experiencia=experiencia,
        activo=True
    )
    db.session.add(asistente)
    db.session.flush()

        # 🔹 Crear/guardar datos médicos si existe al menos un dato
    if any([tipo_sangre, alergias, medicamentos_actuales,
            padecimientos, contacto_emergencia_nombre, contacto_emergencia_telefono]):
        datos_medicos = AsistenteMedico(
            id_asistente=asistente.id_asistente,
            tipo_sangre=tipo_sangre,
            alergias=alergias,
            medicamentos_actuales=medicamentos_actuales,
            padecimientos=padecimientos,
            contacto_emergencia_nombre=contacto_emergencia_nombre,
            contacto_emergencia_telefono=contacto_emergencia_telefono
        )
        db.session.add(datos_medicos)

    db.session.commit()

    return jsonify({
        "ok": True,
        "message": "Asistente creado correctamente.",
        "asistente": {
            "id_persona": persona.id_persona,
            "id_asistente": asistente.id_asistente,
            "nombre": persona.nombre_completo,
            "correo": persona.correo,
            "password": password,
            "rol": rol_front,
            "carrera": carrera,
            "generacion": generacion,
            "fecha_nacimiento": fecha_nac,
            "experiencia": experiencia,
            "tipo_sangre": tipo_sangre,
            "alergias": alergias,
            "medicamentos_actuales": medicamentos_actuales,
            "padecimientos": padecimientos,
            "contacto_emergencia_nombre": contacto_emergencia_nombre,
            "contacto_emergencia_telefono": contacto_emergencia_telefono
        }
    }), 201


# =====================================
# 4) Listar asistentes formales 
# =====================================
@admin_bp.route("/asistentes", methods=["GET"])
@jwt_required()
def listar_asistentes_formales():
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("admin", "staff"):
        return jsonify({
            "ok": False,
            "message": "Solo admin o staff pueden ver la lista de asistentes."
        }), 403

    asistentes = (
        db.session.query(Asistente, Persona, Rol)
        .join(Persona, Asistente.id_asistente == Persona.id_persona)
        .join(Rol, Asistente.id_rol == Rol.id_rol)
        .order_by(Persona.nombre_completo.asc())
        .all()
    )

    data = []
    for asistente, persona, rol in asistentes:
        data.append({
            "id_asistente": asistente.id_asistente,
            "nombre": persona.nombre_completo,
            "correo": persona.correo,
            "empresa": persona.empresa,
            "rol": rol.nombre_rol  # ingeniero / becario / estudiante
        })

    return jsonify({
        "ok": True,
        "asistentes": data
    }), 200

# =====================================
# 5) Credencial con QR para asistentes
# =====================================
@admin_bp.route("/credencial/<int:id_asistente>.png", methods=["GET"])
def credencial_asistente(id_asistente):
    # Buscar asistente + persona
    asistente = Asistente.query.filter_by(id_asistente=id_asistente).first()
    if not asistente or not asistente.persona:
        return jsonify({"ok": False, "message": "Asistente no encontrado."}), 404

    persona = asistente.persona

    # Texto del QR: AGFI-<id_asistente>
    qr_text = f"AGFI-{id_asistente}"

    # Generar imagen de QR
    qr_img = qrcode.make(qr_text).resize((300, 300))

    # Crear credencial base
    # Tamaño aproximado tipo gafete
    width, height = 600, 900
    card = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(card)

    # Intentar cargar logo
    logo = None
    try:
        logo_path = os.path.join(current_app.root_path, "logo_AGFI.png")      
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((180, 180))
        card.paste(logo, (40, 40), logo)
    except Exception as e:
        # Si no hay logo, no truena, solo sigue sin él
        print(f"[WARN] No se pudo cargar logo_AGFI.png: {e}")

    # Tipografías (usamos la default del sistema)
    font_big = ImageFont.load_default()
    font_small = ImageFont.load_default()

    # Nombre
    nombre_text = persona.nombre_completo or ""
    draw.text((40, 250), f"Nombre:", font=font_small, fill="black")
    draw.text((40, 280), nombre_text, font=font_big, fill="black")

    # Generación
    gen_text = asistente.generacion or ""
    draw.text((40, 330), f"Generación:", font=font_small, fill="black")
    draw.text((40, 360), gen_text, font=font_big, fill="black")

    # Carrera
    carrera_text = persona.carrera or ""
    draw.text((40, 410), f"Carrera:", font=font_small, fill="black")
    draw.text((40, 440), carrera_text, font=font_big, fill="black")

    # Colocar QR en la parte baja
    qr_x = (width - qr_img.width) // 2
    qr_y = height - qr_img.height - 80
    card.paste(qr_img, (qr_x, qr_y))

    # Texto pequeño debajo del QR con el código
    draw.text((qr_x, qr_y + qr_img.height + 10), qr_text, font=font_small, fill="black")

    # Devolver como PNG
    buffer = BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="image/png",
        as_attachment=False,
        download_name=f"credencial_{id_asistente}.png"
    )

# =====================================
# 6) Crear un evento nuevo
# =====================================
@admin_bp.route("/eventos", methods=["POST"])
@jwt_required()
def crear_evento():
    identidad = get_jwt_identity() or {}

    if identidad.get("rol") not in ("admin", "staff"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    data = request.get_json() or {}

    nombre = data.get("nombre")
    fecha = data.get("fecha")          # "YYYY-MM-DD"
    lugar = data.get("lugar")          # sede
    direccion = data.get("direccion")
    ciudad = data.get("ciudad")
    estado = data.get("estado")
    pais = data.get("pais")
    notas = data.get("notas")

    if not nombre or not fecha or not lugar:
        return jsonify({"ok": False, "message": "Faltan campos obligatorios."}), 400

    try:
        fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
    except Exception:
        return jsonify({"ok": False, "message": "Fecha inválida."}), 400

    # Código único simple
    codigo = f"EV-{int(datetime.utcnow().timestamp())}"

    try:
        ahora = datetime.utcnow()

        # 1) Crear evento
        evento = Evento(
            codigo=codigo,
            nombre=nombre,
            fecha_inicio=fecha_dt,
            sede=lugar,
            direccion=direccion,
            ciudad=ciudad,
            estado=estado,
            pais=pais,
            notas=notas,
            creado_en=ahora
        )
        db.session.add(evento)
        db.session.flush()  # ya tenemos evento.id_evento

        # 2) Obtener todos los asistentes formales
        asistentes = Asistente.query.all()

        registros_nuevos = []
        for a in asistentes:
            reg = Registro(
                id_evento=evento.id_evento,
                id_asistente=a.id_asistente,
                asistencia="desconocido",
                invitados=0,
                confirmado=None,
                fecha_confirmacion=None,
                comentarios=None,
                creado_en=ahora
            )
            registros_nuevos.append(reg)

        if registros_nuevos:
            db.session.add_all(registros_nuevos)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        # Muy útil para depurar mientras tanto
        print("Error al crear evento:", e)
        return jsonify({
            "ok": False,
            "message": "Error al crear evento",
            "error": str(e)
        }), 500

    return jsonify({
        "ok": True,
        "message": "Evento creado correctamente.",
        "evento": {
            "id_evento": evento.id_evento,
            "codigo": evento.codigo,
            "nombre": evento.nombre,
            "fecha": fecha,
            "lugar": evento.sede,
            "direccion": evento.direccion,
            "ciudad": evento.ciudad,
            "estado": evento.estado,
            "pais": evento.pais,
            "notas": evento.notas,
        },
        "registros_creados": len(registros_nuevos)
    }), 201

# =====================================
# 7) Listar eventos
# =====================================

@admin_bp.route("/eventos", methods=["GET"])
@jwt_required()
def listar_eventos():
    identidad = get_jwt_identity() or {}

    if identidad.get("rol") not in ("admin", "staff"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    eventos = Evento.query.order_by(Evento.fecha_inicio.desc()).all()

    # Total de asistentes oficiales (asistentes formales)
    total_oficiales = Asistente.query.count()

    data = []
    for ev in eventos:
        # Confirmados por evento (en tabla registros)
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
# 8) Listar comentarios del buzón
# =====================================
@admin_bp.route("/buzon", methods=["GET"])
@jwt_required()
def listar_buzon():
    """
    Devuelve todos los comentarios anónimos del buzón de sugerencias
    para que el administrador los pueda revisar.
    """
    identidad = get_jwt_identity()
    rol = identidad.get("rol") if isinstance(identidad, dict) else None

    # Solo admin o staff
    if rol not in ("admin", "staff"):
        return jsonify({
            "ok": False,
            "message": "No tienes permisos para ver el buzón."
        }), 403

    comentarios = (
        BuzonComentario.query
        .order_by(BuzonComentario.creado_en.desc())
        .all()
    )

    data = []
    for c in comentarios:
        data.append({
            "id": c.id_comentario,
            "asunto": c.asunto,
            "mensaje": c.mensaje,
            "evento_relacionado": c.evento_relacionado,
            "creado_en": c.creado_en.isoformat() if c.creado_en else None,
        })

    return jsonify({
        "ok": True,
        "comentarios": data
    }), 200

# =====================================
# 9) Pase de lista por evento (JSON)
# =====================================
@admin_bp.route("/pase_lista", methods=["GET"])
@jwt_required()
def pase_lista_evento():
    """
    Devuelve la lista de asistentes relacionados a un evento,
    incluyendo si tenían confirmación de asistencia.
    """
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("admin", "staff"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    id_evento = request.args.get("id_evento", type=int)
    if not id_evento:
        return jsonify({"ok": False, "message": "id_evento es requerido"}), 400

    # Validar que el evento exista
    evento = Evento.query.get(id_evento)
    if not evento:
        return jsonify({"ok": False, "message": "Evento no encontrado"}), 404

    # Traer registros + persona + rol + asistencia física (si existe)
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
            "asistencia_estado": reg.asistencia,          # si / no / tal_vez / desconocido
            "confirmado": reg.confirmado,                 # True / False / None
            "invitados": reg.invitados,
            "comentarios": reg.comentarios,
            "check_in": True if asistencia_fisica and asistencia_fisica.hora_entrada else False
        })

    return jsonify({"ok": True, "evento": {
                        "id_evento": evento.id_evento,
                        "nombre": evento.nombre,
                        "fecha": evento.fecha_inicio.strftime("%Y-%m-%d"),
                    },
                    "registros": data}), 200

# =====================================
# 10) Exportar pase de lista a CSV
# =====================================
@admin_bp.route("/pase_lista_csv", methods=["GET"])
@jwt_required()
def exportar_pase_lista_csv():
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("admin", "staff"):
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

    # Encabezados
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
# 11) Importar pase de lista desde CSV
# =====================================
@admin_bp.route("/pase_lista_import", methods=["POST"])
@jwt_required()
def importar_pase_lista_csv():
    """
    Espera un CSV con al menos la columna 'correo'. Opcionalmente:
    - asistencia_estado  (si / no / tal_vez / desconocido)
    - confirmado         (1/0, true/false, sí/no)
    - invitados          (entero)
    Actualiza o crea registros en la tabla 'registros' para el evento.
    """
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("admin", "staff"):
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
            no_encontrados.append({"motivo": "persona_o_asistente_no_encontrado", "correo": correo})
            continue

        asistente = persona.asistente

        # Buscar registro existente
        reg = Registro.query.filter_by(
            id_evento=id_evento,
            id_asistente=asistente.id_asistente
        ).first()

        if not reg:
            # Crear si no existe
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

        asistencia_estado = (row.get("asistencia_estado") or row.get("asistencia") or "").strip().lower()
        if asistencia_estado in ("si", "sí", "no", "tal_vez", "desconocido"):
            reg.asistencia = asistencia_estado

        confirmado_val = row.get("confirmado") or ""
        confirmado_bool = parse_bool(confirmado_val)
        if confirmado_bool is not None:
            reg.confirmado = confirmado_bool
            reg.fecha_confirmacion = ahora

        invitados_val = row.get("invitados") or ""
        try:
            reg.invitados = int(invitados_val) if invitados_val != "" else reg.invitados
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
# 12) Buscar asistente por QR + evento (incluye datos médicos)
# =====================================
@admin_bp.route("/qr_lookup", methods=["GET"])
@jwt_required()
def qr_lookup():
    """
    Busca a un asistente a partir del texto del QR (o id numérico)
    y del evento seleccionado. Devuelve datos de la persona,
    datos médicos (si existen) y el estado de asistencia para ese evento.
    """
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("admin", "staff"):
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

    # 🔹 Datos médicos
    medico = AsistenteMedico.query.get(id_asistente)

    # Buscar registro para ese evento
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

    # Si hay datos médicos, los agregamos
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
            "hora_entrada": asistencia_fisica.hora_entrada.isoformat() if asistencia_fisica.hora_entrada else None,
            "numero_mesa": asistencia_fisica.numero_mesa,
            "numero_asiento": asistencia_fisica.numero_asiento,
            "codigo_gafete": asistencia_fisica.codigo_gafete,
        }

    return jsonify(response), 200

# =====================================
# 13) Actualizar datos básicos y marcar asistencia
# =====================================

@admin_bp.route("/qr_checkin", methods=["POST"])
@jwt_required()
def qr_checkin():
    """
    Guarda cambios en los datos del asistente (incluyendo datos médicos)
    y registra asistencia física en la tabla 'asistencia'.

    Espera JSON con:
    - id_evento (obligatorio)
    - id_asistente o code (AGFI-123 o '123')
    - nombre, correo, empresa, telefono, carrera, generacion, experiencia
    - rol  (ingeniero / becario / estudiante)
    - tipo_sangre, alergias, medicamentos_actuales, padecimientos
    - contacto_emergencia_nombre, contacto_emergencia_telefono
    """
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("admin", "staff"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    data = request.get_json() or {}

    # ---- 1) Validar evento ----
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

    # ---- 2) Resolver id_asistente (id o code) ----
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

    # ---- 3) Campos que pueden venir en el JSON ----
    nombre      = data.get("nombre")
    correo      = data.get("correo")
    empresa     = data.get("empresa")
    telefono    = data.get("telefono")
    carrera     = data.get("carrera")
    generacion  = data.get("generacion")
    experiencia = data.get("experiencia")
    rol_front   = data.get("rol")  # ingeniero / becario / estudiante

    tipo_sangre                  = data.get("tipo_sangre")
    alergias                     = data.get("alergias")
    medicamentos_actuales        = data.get("medicamentos_actuales")
    padecimientos                = data.get("padecimientos")
    contacto_emergencia_nombre   = data.get("contacto_emergencia_nombre")
    contacto_emergencia_telefono = data.get("contacto_emergencia_telefono")

    # ---- 4) Validar correo único si cambia ----
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

    # ---- 5) Actualizar Persona ----
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

    # ---- 6) Actualizar Asistente (rol, generación, experiencia) ----
    if rol_front:
        rol_obj = Rol.query.filter_by(nombre_rol=rol_front).first()
        if not rol_obj:
            return jsonify({"ok": False, "message": "Rol de asistente no válido."}), 400
        asistente.id_rol = rol_obj.id_rol

    if generacion is not None:
        asistente.generacion = generacion.strip() if isinstance(generacion, str) else generacion
    if experiencia is not None:
        asistente.experiencia = experiencia

    # ---- 7) Actualizar / crear AsistenteMedico ----
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

    # ---- 8) Registro en el evento ----
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

    # Marcamos asistencia lógica
    registro.asistencia = "si"
    if registro.confirmado is None:
        registro.confirmado = True
        registro.fecha_confirmacion = ahora

    # ---- 9) Asistencia física (hora_entrada en tabla asistencia) ----
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
            "hora_entrada": asistencia_obj.hora_entrada.isoformat() if asistencia_obj.hora_entrada else None,
            "registro_creado": creado_registro,
            "asistencia_creada": created_asistencia
        }
    }), 200

# =====================================
# 14) Alta express de invitados de último momento
# =====================================
@admin_bp.route("/alta_express", methods=["POST"])
@jwt_required()
def alta_express_admin():
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") not in ("admin"):
        return jsonify({"ok": False, "message": "No autorizado."}), 403

    data = request.get_json() or {}

    id_evento   = data.get("id_evento")
    nombre      = (data.get("nombre") or "").strip()
    correo      = (data.get("correo") or "").strip()
    empresa     = (data.get("empresa") or "").strip()
    rol_front   = (data.get("rol") or "").strip()
    carrera     = (data.get("carrera") or "").strip()
    generacion  = (data.get("generacion") or "").strip()

    # Validaciones básicas
    if not id_evento:
        return jsonify({"ok": False, "message": "id_evento es requerido."}), 400
    try:
        id_evento = int(id_evento)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "id_evento inválido."}), 400

    if not nombre or not correo or not rol_front or not carrera or not generacion:
        return jsonify({
            "ok": False,
            "message": "Nombre, correo, clasificación, carrera y generación son obligatorios."
        }), 400

    evento = Evento.query.get(id_evento)
    if not evento:
        return jsonify({"ok": False, "message": "Evento no encontrado."}), 404

    rol_obj = Rol.query.filter_by(nombre_rol=rol_front).first()
    if not rol_obj:
        return jsonify({"ok": False, "message": "Rol de asistente no válido."}), 400

    ahora = datetime.utcnow()

    # 1) Persona (se busca por correo)
    persona = Persona.query.filter_by(correo=correo).first()
    persona_creada = False

    if not persona:
        # 👇 Aquí ponemos el password en TEXTO PLANO "SinLogin"
        persona = Persona(
            nombre_completo=nombre,
            correo=correo,
            password_hash="SinLogin",
            telefono=None,
            empresa=empresa or None,
            puesto=None,
            carrera=carrera,     # NOT NULL en la base
            creado_en=ahora
        )
        db.session.add(persona)
        db.session.flush()   # para tener persona.id_persona
        persona_creada = True
    else:
        # Si ya existía, actualizamos datos básicos
        persona.nombre_completo = nombre
        if empresa:
            persona.empresa = empresa
        if carrera:
            persona.carrera = carrera

    # 2) Asistente (ligado a persona)
    asistente = persona.asistente
    asistente_creado = False

    if not asistente:
        asistente = Asistente(
            id_asistente=persona.id_persona,
            id_rol=rol_obj.id_rol,
            generacion=generacion,
            activo=True
        )
        db.session.add(asistente)
        asistente_creado = True
    else:
        asistente.id_rol = rol_obj.id_rol
        if generacion:
            asistente.generacion = generacion

        # 3) Invitado de último momento (subtipo walk-in)
    invitado_ulm = InvitadoULM.query.filter_by(
        id_invitado_ulm=persona.id_persona,
        id_evento=id_evento
    ).first()
    invitado_creado = False

    if not invitado_ulm:
        invitado_ulm = InvitadoULM(
            id_invitado_ulm=persona.id_persona,
            id_evento=id_evento,
            creado_en=ahora
        )
        db.session.add(invitado_ulm)
        invitado_creado = True

    # 3) Registro (relación con evento)
    registro = Registro.query.filter_by(
        id_evento=id_evento,
        id_asistente=asistente.id_asistente
    ).first()
    registro_creado = False

    if not registro:
        registro = Registro(
            id_evento=id_evento,
            id_asistente=asistente.id_asistente,
            asistencia="si",       # ya está presente
            invitados=0,
            confirmado=True,
            fecha_confirmacion=ahora,
            comentarios="Alta express (invitado último momento).",
            creado_en=ahora
        )
        db.session.add(registro)
        registro_creado = True
    else:
        registro.asistencia = "si"
        if registro.confirmado is None:
            registro.confirmado = True
            registro.fecha_confirmacion = ahora

    # 4) Asistencia física (check-in)
    asistencia_obj = Asistencia.query.filter_by(
        id_registro=registro.id_registro
    ).first()
    asistencia_creada = False

    if not asistencia_obj:
        asistencia_obj = Asistencia(
            id_registro=registro.id_registro,
            hora_entrada=ahora,
            codigo_gafete=f"AGFI-{asistente.id_asistente}",
            creado_en=ahora
        )
        db.session.add(asistencia_obj)
        asistencia_creada = True
    else:
        if not asistencia_obj.hora_entrada:
            asistencia_obj.hora_entrada = ahora
        if not asistencia_obj.codigo_gafete:
            asistencia_obj.codigo_gafete = f"AGFI-{asistente.id_asistente}"

    db.session.commit()

    return jsonify({
        "ok": True,
        "message": "Invitado de último momento dado de alta y asistencia registrada.",
        "data": {
            "id_persona": persona.id_persona,
            "id_asistente": asistente.id_asistente,
            "id_evento": evento.id_evento,
            "id_registro": registro.id_registro,
            "id_asistencia": asistencia_obj.id_asistencia,
            "codigo_qr": f"AGFI-{asistente.id_asistente}",
            "persona_creada": persona_creada,
            "asistente_creado": asistente_creado,
            "invitado_ulm_creado": invitado_creado,
            "registro_creado": registro_creado,
            "asistencia_creada": asistencia_creada
        }
    }), 200


@admin_bp.route("/credencial_zip/<int:id_asistente>", methods=["GET"])
def generar_credencial_completa(id_asistente):
    asistente = Asistente.query.get(id_asistente)
    if not asistente or not asistente.persona:
        return jsonify({"ok": False, "message": "Asistente no encontrado."}), 404

    persona = asistente.persona

    # Rutas de las plantillas PNG
    front_path = "1.png"
    back_path  = "2.png"

    front = Image.open(front_path).convert("RGBA")
    back  = Image.open(back_path).convert("RGBA")

    draw_f = ImageDraw.Draw(front)
    draw_b = ImageDraw.Draw(back)

    #              font = ImageFont.truetype("arial.ttf", 15)
    font = ImageFont.truetype("dejavu-sans.book.ttf", 15)

    # =============================
    #  FRENTE — posiciones exactas
    # =============================
    draw_f.text((600, 280), persona.nombre_completo or "", fill="black", font=font)
    draw_f.text((600, 350), asistente.generacion or "", fill="black", font=font)

    miembro_desde = persona.creado_en.strftime("%Y") if persona.creado_en else ""
    draw_f.text((830, 350), miembro_desde, fill="black", font=font)

    draw_f.text((600, 425), persona.carrera or "", fill="black", font=font)

    # =============================
    #  REVERSO — QR centrado
    # =============================
    qr_text = f"AGFI-{id_asistente}"
    qr_img = qrcode.make(qr_text).resize((300, 300))

    # pegar QR
    back.paste(qr_img, (355, 80))


    # =============================
    #  CREAR ZIP CON AMBAS IMÁGENES
    # =============================
    buffer_zip = BytesIO()
    import zipfile

    with zipfile.ZipFile(buffer_zip, "w") as z:
        fb = BytesIO()
        front.save(fb, format="PNG")
        z.writestr(f"credencial_front_{id_asistente}.png", fb.getvalue())

        bb = BytesIO()
        back.save(bb, format="PNG")
        z.writestr(f"credencial_back_{id_asistente}.png", bb.getvalue())

    buffer_zip.seek(0)

    return send_file(
        buffer_zip,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"credencial_{id_asistente}.zip"
    )
