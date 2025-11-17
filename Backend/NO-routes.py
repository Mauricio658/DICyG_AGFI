from flask import Blueprint, jsonify, request
from models import db, Evento   # 👈 sin punto

bp = Blueprint("api", __name__, url_prefix="/api")

@bp.get("/ping")
def ping():
    return {"ok": True, "msg": "pong"}

@bp.get("/eventos")
def listar_eventos():
    eventos = Evento.query.order_by(Evento.id_evento.desc()).limit(50).all()
    data = [{"id": e.id_evento, "codigo": e.codigo, "nombre": e.nombre} for e in eventos]
    return jsonify(data)

@bp.post("/asistencia/checkin")
def checkin():
    payload = request.get_json() or {}
    # aquí usarías tu lógica de registro de asistencia…
    return {"ok": True, "msg": "asistencia registrada (demo)", "data": payload}

@bp.post("/alta-express")
def alta_express():
    payload = request.get_json() or {}
    # crear persona/asistente y devolver QR en otro paso
    return {"ok": True, "msg": "alta express (demo)", "data": payload}
