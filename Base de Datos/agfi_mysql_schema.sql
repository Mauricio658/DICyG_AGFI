# ===============================================================
# MySQL 8.0 esquema "Sistema_AGFI" (v3 con especialización)
# ===============================================================

CREATE DATABASE IF NOT EXISTS Sistema_AGFI
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE Sistema_AGFI;

# ===============================================================
# 1) Catálogo de roles
# ===============================================================

CREATE TABLE roles (
  id_rol        TINYINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  nombre_rol    ENUM('ingeniero','becario','estudiante','administrador','staff') NOT NULL UNIQUE,
  costo_evento  DECIMAL(10,2) NOT NULL
);

INSERT INTO roles (nombre_rol, costo_evento)
VALUES ('ingeniero', 400.00),
       ('becario',      0.00),
       ('estudiante', 200.00),
       ('administrador',      0.00),
       ('staff',         0.00);

# ===============================================================
# 2) PERSONAS (superclase)
#    - CUALQUIER individuo conocido por el sistema vive aquí
#    - Info general de contacto
# ===============================================================

CREATE TABLE personas (
  id_persona      BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  nombre_completo VARCHAR(200) NOT NULL,
  correo          VARCHAR(190) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  telefono        VARCHAR(20)  NULL,
  empresa         VARCHAR(150) NULL,
  puesto          VARCHAR(120) NULL,
  carrera         VARCHAR(120) NOT NULL,
  creado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en  TIMESTAMP NULL DEFAULT NULL
                        ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_personas_correo UNIQUE KEY (correo),
  INDEX idx_personas_nombre (nombre_completo),
  INDEX idx_personas_tel (telefono)
);

# ===============================================================
# 3) ASISTENTES (subtipo formal)
#    - "Esta persona ya está dada de alta como asistente oficial"
#    - 1 a 1 con personas
# ===============================================================

CREATE TABLE asistentes (
  id_asistente    BIGINT UNSIGNED PRIMARY KEY,   -- MISMO valor que personas.id_persona
  id_rol          TINYINT UNSIGNED NULL,         -- FK a roles
  generacion      VARCHAR(40)  NULL,
  mes_cumple      TINYINT UNSIGNED NULL,
  dia_cumple      TINYINT UNSIGNED NULL,
  experiencia TEXT NULL,
  activo          BOOLEAN DEFAULT TRUE,

  CONSTRAINT fk_asistente_persona
    FOREIGN KEY (id_asistente)
    REFERENCES personas(id_persona)
    ON DELETE CASCADE,

  CONSTRAINT fk_asistente_rol
    FOREIGN KEY (id_rol)
    REFERENCES roles(id_rol),

  INDEX idx_asistentes_rol (id_rol),
  INDEX idx_asistentes_activo (activo)
);

# ===============================================================
# 4) INVITADOS_ULTIMO_MOMENTO (subtipo walk-in)
#    - Persona que apareció el día del evento sin preregistro
#    - 1 a 1 con personas también
# ===============================================================

CREATE TABLE invitados_ultimo_momento (
  id_invitado_ulm BIGINT UNSIGNED PRIMARY KEY,   -- MISMO valor que personas.id_persona
  id_evento       BIGINT UNSIGNED NOT NULL,      -- a qué evento llegó
  creado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_ulm_persona
    FOREIGN KEY (id_invitado_ulm)
    REFERENCES personas(id_persona)
    ON DELETE CASCADE
);

# ===============================================================
# 5) EVENTOS
#    (sin fecha_fin)
# ===============================================================

CREATE TABLE eventos (
  id_evento     BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  codigo        VARCHAR(50)  NOT NULL,
  nombre        VARCHAR(200) NOT NULL,
  fecha_inicio  DATETIME     NOT NULL,
  sede          VARCHAR(200) NULL,
  direccion     VARCHAR(250) NULL,
  ciudad        VARCHAR(120) NULL,
  estado        VARCHAR(120) NULL,
  pais          VARCHAR(120) NULL,
  notas         TEXT         NULL,
  creado_en     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT uq_eventos_codigo UNIQUE KEY (codigo),
  INDEX idx_eventos_codigo (codigo),
  INDEX idx_eventos_fecha (fecha_inicio)
);

# Relación evento <-> invitado_ultimo_momento
ALTER TABLE invitados_ultimo_momento
  ADD CONSTRAINT fk_ulm_evento
    FOREIGN KEY (id_evento)
    REFERENCES eventos(id_evento);

CREATE INDEX idx_ulm_evento ON invitados_ultimo_momento (id_evento);

# Para evitar el mismo colado duplicado en mismo evento
-- NOTA: usamos (id_evento, id_invitado_ulm) como unicidad lógica.
CREATE UNIQUE INDEX uq_ulm_evento_persona
  ON invitados_ultimo_momento (id_evento, id_invitado_ulm);

# ===============================================================
# 6) REGISTROS (RSVP / confirmación por evento)
#    - Ata a un ASISTENTE (no a cualquier persona)
# ===============================================================

CREATE TABLE registros (
  id_registro     BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  id_evento       BIGINT UNSIGNED NOT NULL,
  id_asistente    BIGINT UNSIGNED NOT NULL,
  asistencia      ENUM('si','no','tal_vez','desconocido')
                    DEFAULT 'desconocido',
  invitados       TINYINT UNSIGNED DEFAULT 0,
  confirmado      BOOLEAN DEFAULT NULL,
  fecha_confirmacion DATETIME NULL,
  comentarios     TEXT NULL,
  creado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uq_reg_evento_asistente (id_evento, id_asistente),

  CONSTRAINT fk_reg_evento
    FOREIGN KEY (id_evento)
    REFERENCES eventos(id_evento),

  CONSTRAINT fk_reg_asistente
    FOREIGN KEY (id_asistente)
    REFERENCES asistentes(id_asistente),

  INDEX idx_reg_evento (id_evento),
  INDEX idx_reg_asistente (id_asistente),
  INDEX idx_reg_evento_asistencia (id_evento, asistencia)
);

# ===============================================================
# 7) ASISTENCIA (check-in físico en puerta)
#    - SIN hora_salida
# ===============================================================

CREATE TABLE asistencia (
  id_asistencia   BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  id_registro     BIGINT UNSIGNED NOT NULL,
  hora_entrada    DATETIME NULL,
  numero_mesa     VARCHAR(10) NULL,
  numero_asiento  VARCHAR(10) NULL,
  codigo_gafete   VARCHAR(64) NULL,
  creado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uq_asistencia_registro (id_registro),

  CONSTRAINT fk_asistencia_registro
    FOREIGN KEY (id_registro)
    REFERENCES registros(id_registro),

  INDEX idx_asistencia_entrada (hora_entrada)
);

# ===============================================================
# 8) INDICACIONES MÉDICAS / PREFERENCIAS ALIMENTICIAS
#    - Se asocian a asistentes (o sea a la persona cuando ya es asistente formal)
# ===============================================================

CREATE TABLE asistente_medico (
  id_asistente BIGINT UNSIGNED PRIMARY KEY,
  tipo_sangre VARCHAR(10) NULL,
  alergias TEXT NULL,
  medicamentos_actuales TEXT NULL,
  padecimientos TEXT NULL,
  contacto_emergencia_nombre VARCHAR(200) NULL,
  contacto_emergencia_telefono VARCHAR(20) NULL,

  CONSTRAINT fk_am_asistente
    FOREIGN KEY (id_asistente)
    REFERENCES asistentes(id_asistente)
    ON DELETE CASCADE
);


# ===============================================================
# 9) LOGS (auditoría)
#    - Para saber quién hizo qué
#    - Guardamos llaves a evento / asistente / invitado ULM / registro
# ===============================================================

CREATE TABLE logs (
  id_log           BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  actor            VARCHAR(150) NULL,
  accion           VARCHAR(100) NOT NULL,
  descripcion      TEXT NULL,

  id_evento        BIGINT UNSIGNED NULL,
  id_asistente     BIGINT UNSIGNED NULL,
  id_registro      BIGINT UNSIGNED NULL,
  id_invitado_ulm  BIGINT UNSIGNED NULL,

  creado_en        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_logs_evento (id_evento),
  INDEX idx_logs_asistente (id_asistente),
  INDEX idx_logs_registro (id_registro),
  INDEX idx_logs_invitado (id_invitado_ulm),
  INDEX idx_logs_accion (accion),

  CONSTRAINT fk_logs_evento
    FOREIGN KEY (id_evento)
    REFERENCES eventos(id_evento),

  CONSTRAINT fk_logs_asistente
    FOREIGN KEY (id_asistente)
    REFERENCES asistentes(id_asistente),

  CONSTRAINT fk_logs_registro
    FOREIGN KEY (id_registro)
    REFERENCES registros(id_registro),

  CONSTRAINT fk_logs_invitado
    FOREIGN KEY (id_invitado_ulm)
    REFERENCES invitados_ultimo_momento(id_invitado_ulm)
);

# ===============================================================
# 10) VISTAS
# ===============================================================

-- 10.1 Vista para listar asistencia en evento
--      Nota: ahora tenemos que unir personas -> asistentes.
CREATE OR REPLACE VIEW vw_evento_asistencia AS
SELECT
  e.codigo                    AS codigo_evento,
  e.nombre                    AS nombre_evento,
  p.nombre_completo,
  p.correo,
  p.telefono,
  p.empresa,
  p.puesto,
  a.generacion,
  CONCAT(LPAD(a.dia_cumple,2,'0'), '/', LPAD(a.mes_cumple,2,'0')) AS cumple_ddmm,
  r.asistencia,
  r.invitados,
  r.confirmado,
  r.fecha_confirmacion,
  s.hora_entrada,
  s.numero_mesa,
  s.numero_asiento,
  s.codigo_gafete
FROM registros r
JOIN asistentes a        ON a.id_asistente    = r.id_asistente
JOIN personas  p         ON p.id_persona      = a.id_asistente
JOIN eventos   e         ON e.id_evento       = r.id_evento
LEFT JOIN asistencia s   ON s.id_registro     = r.id_registro;

-- 10.2 Vista de costos por rol (cobranza)
CREATE OR REPLACE VIEW vw_costos_evento AS
SELECT
  e.codigo            AS codigo_evento,
  e.nombre            AS nombre_evento,
  p.nombre_completo,
  p.correo,
  p.empresa,
  p.puesto,
  r.asistencia,
  rl.nombre_rol       AS rol,
  rl.costo_evento     AS costo
FROM registros r
JOIN asistentes a   ON a.id_asistente = r.id_asistente
JOIN personas  p    ON p.id_persona   = a.id_asistente
LEFT JOIN roles rl  ON rl.id_rol      = a.id_rol
JOIN eventos e      ON e.id_evento    = r.id_evento;

# ===========================================================
#Buzon de sugerencias
CREATE TABLE buzon_comentarios (
  id_comentario      BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  asunto             VARCHAR(150) NOT NULL,
  mensaje            TEXT NOT NULL,
  evento_relacionado VARCHAR(200) NULL,
  creado_en          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


# ===============================================================
# FIN DEL ESQUEMA
# ===============================================================