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

)



admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
from io import BytesIO
from flask import send_file, current_app
import qrcode
from PIL import Image, ImageDraw, ImageFont
import csv             
import io                     
import os    

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
