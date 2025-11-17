import os

class Config:
    # Usamos una sola variable de entorno para todo
    SECRET_KEY = os.getenv("JWT_SECRET", "dev-key")
    JWT_SECRET_KEY = "Sei9set6e4mkawse"  # 👈 para Flask-JWT-Extended

    SQLALCHEMY_DATABASE_URI = (
        f"{os.getenv('DB_DIALECT','mysql+pymysql')}://"
        f"{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT','3306')}/"
        f"{os.getenv('DB_NAME')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
