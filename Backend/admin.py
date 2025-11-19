from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from models import db, Persona, Asistente, Rol, IndicacionMedica, AsistentePreferencia

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
# 2) Crear usuario admin/staff
# =====================================
@admin_bp.route("/usuarios", methods=["POST"])
@jwt_required()
def crear_usuario():
    identidad = get_jwt_identity() or {}
    if identidad.get("rol") != "admin":
        return jsonify({
            "ok": False,
            "message": "Solo un administrador puede crear usuarios."
        }), 403

    data = request.get_json() or {}

    # Campos obligatorios
    nombre = data.get("nombre")
    correo = data.get("correo")
    password = data.get("password")
    rol_front = data.get("rol")  # admin o staff

    # Campos extra solicitados
    generacion = data.get("generacion")
    carrera = data.get("carrera")
    fecha_nac = data.get("fecha_nacimiento")  # "YYYY-MM-DD"
    indicaciones_txt = data.get("indicaciones_medicas")

    if not nombre or not correo or not password or not rol_front or not carrera:
        return jsonify({
            "ok": False,
            "message": "Faltan campos obligatorios."
        }), 400

    # ¿Existe correo?
    existente = Persona.query.filter_by(correo=correo).first()
    if existente:
        return jsonify({
            "ok": False,
            "message": "El correo ya está registrado."
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
        creado_en=datetime.utcnow()
    )

    db.session.add(persona)
    db.session.flush()

    # Mapear rol admin/staff -> nombre en BD
    nombre_rol_db = "administrador" if rol_front == "admin" else "staff"
    rol_obj = Rol.query.filter_by(nombre_rol=nombre_rol_db).first()
    if not rol_obj:
        db.session.rollback()
        return jsonify({"ok": False, "message": "Rol no encontrado en la base."}), 500

    # Procesar fecha nacimiento
    mes = None
    dia = None
    if fecha_nac:
        try:
            f = datetime.strptime(fecha_nac, "%Y-%m-%d").date()
            mes, dia = f.month, f.day
        except:
            pass

    # Crear asistente ligado 1 a 1
    asistente = Asistente(
        id_asistente=persona.id_persona,
        id_rol=rol_obj.id_rol,
        generacion=generacion,
        mes_cumple=mes,
        dia_cumple=dia,
        activo=True
    )
    db.session.add(asistente)
    db.session.flush()

    # Indicaciones médicas (si vienen)
    if indicaciones_txt:
        texto = indicaciones_txt.strip()
        if texto:
            indic = IndicacionMedica.query.filter_by(nombre=texto).first()
            if not indic:
                indic = IndicacionMedica(nombre=texto, descripcion=None)
                db.session.add(indic)
                db.session.flush()

            pref = AsistentePreferencia(
                id_asistente=asistente.id_asistente,
                id_indicacion=indic.id_indicacion,
                notas=None
            )
            db.session.add(pref)

    db.session.commit()

    return jsonify({
        "ok": True,
        "message": "Usuario creado correctamente.",
        "user": {
            "id_persona": persona.id_persona,
            "correo": persona.correo,
            "nombre": persona.nombre_completo,
            "rol": rol_front,
            "generacion": generacion,
            "carrera": carrera,
            "fecha_nacimiento": fecha_nac,
            "indicaciones_medicas": indicaciones_txt
        }
    }), 201

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
    indicaciones_txt = data.get("indicaciones_medicas")
    indicaciones_desc = data.get("indicaciones_descripcion")

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
        creado_en=datetime.utcnow()
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
        activo=True
    )
    db.session.add(asistente)
    db.session.flush()

    # Indicaciones médicas (si vienen)
    # Indicaciones médicas (si vienen)
    if indicaciones_txt:
        texto = indicaciones_txt.strip()
        if texto:
            indic = IndicacionMedica.query.filter_by(nombre=texto).first()
            if not indic:
                # Si no existe, la creamos con la descripción que mandó el usuario (puede ser None)
                indic = IndicacionMedica(
                    nombre=texto,
                    descripcion=indicaciones_desc
                )
                db.session.add(indic)
                db.session.flush()
            else:
                # Si ya existía y ahora nos mandan una descripción, opcionalmente puedes actualizarla
                if indicaciones_desc:
                    indic.descripcion = indicaciones_desc

            pref = AsistentePreferencia(
                id_asistente=asistente.id_asistente,
                id_indicacion=indic.id_indicacion,
                notas=indicaciones_desc  # si quieres guardar también por asistente
            )
            db.session.add(pref)
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
            "indicaciones_medicas": indicaciones_txt
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
