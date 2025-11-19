from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from models import db, Persona, Asistente, Rol, IndicacionMedica, AsistentePreferencia

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


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
