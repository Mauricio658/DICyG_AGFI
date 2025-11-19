import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from models import db, Persona
from auth import auth_bp
from admin import admin_bp

def create_app():
    app = Flask(__name__)

    CORS(app)

    # Config DB
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://agfi_user:agfi_pass@db:3306/Sistema_AGFI"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Config JWT
    app.config["JWT_SECRET_KEY"] = os.environ.get(
        "JWT_SECRET_KEY",
        "cambia-esto-en-produccion-porfa"
    )
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_ALGORITHM"] = "HS256"
    app.config["JWT_IDENTITY_CLAIM"] = "identity"
    
    db.init_app(app)
    JWTManager(app)

    # Registrar blueprint de auth
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    #============================ PRUEBAS ============================#
    # Ruta de prueba
    @app.route("/ping")
    def ping():
        return {"status": "ok", "message": "pong"}

    @app.route("/db-check")
    def db_check():
        try:
            count = Persona.query.count()
            return jsonify({"ok": True, "personas_en_bd": count})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    #=========================== FIN PRUEBAS ===========================#
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
