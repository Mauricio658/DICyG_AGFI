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
    BuzonComentario
)



admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
from io import BytesIO
from flask import send_file, current_app
import qrcode
from PIL import Image, ImageDraw, ImageFont


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
