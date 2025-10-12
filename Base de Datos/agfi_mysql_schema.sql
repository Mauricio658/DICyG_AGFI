# ===============================================================
# MySQL 8.0 esquema para "Lista de Asistencia - Desayuno Asamblea Ordinaria AGFI"
# ===============================================================

CREATE DATABASE IF NOT EXISTS agfi
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
USE agfi;

# ===============================================================
# 1) Datos principales
# ===============================================================

# Tabla de asistentes
CREATE TABLE asistentes (
  id_asistente    BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,     # PK
  nombre_completo VARCHAR(200) NOT NULL,
  correo          VARCHAR(190) NULL,
  telefono        VARCHAR(20)  NULL,
  empresa         VARCHAR(150) NULL,
  puesto          VARCHAR(120) NULL,
  generacion      VARCHAR(40)  NULL,                              # Generación (ej. '63', '2001', 'Beca')
  mes_cumple      TINYINT UNSIGNED NULL,
  dia_cumple      TINYINT UNSIGNED NULL,
  creado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,   # trazabilidad de creación
  actualizado_en  TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP, # trazabilidad de modificación
  CONSTRAINT uq_asistentes_correo UNIQUE KEY (correo),            # evita duplicidad de correos
  INDEX idx_asistentes_nombre (nombre_completo),
  INDEX idx_asistentes_telefono (telefono)
);

# Tabla de eventos (desayunos, asambleas, etc.)
CREATE TABLE eventos (
  id_evento     BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  codigo        VARCHAR(50)  NOT NULL,       # Ej. 'AGFI-ORD-2025-01'
  nombre        VARCHAR(200) NOT NULL,       # Ej. 'Desayuno Asamblea Ordinaria AGFI'
  fecha_inicio  DATETIME     NOT NULL,       # fecha y hora de inicio
  fecha_fin     DATETIME     NULL,           # fecha y hora de fin
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

# Tabla de registros (confirmaciones / RSVP)
CREATE TABLE registros (
  id_registro     BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  id_evento       BIGINT UNSIGNED NOT NULL,     # FK evento
  id_asistente    BIGINT UNSIGNED NOT NULL,     # FK asistente
  asistencia      ENUM('si','no','tal_vez','desconocido') DEFAULT 'desconocido',
  invitados       TINYINT UNSIGNED DEFAULT 0,
  personalizador1 ENUM('si','no','desconocido') DEFAULT 'desconocido',
  personalizador2 ENUM('si','no','desconocido') DEFAULT 'desconocido',
  confirmado      BOOLEAN DEFAULT NULL,
  fecha_confirmacion DATETIME NULL,
  comentarios     TEXT NULL,
  creado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_reg_evento_asistente (id_evento, id_asistente),
  CONSTRAINT fk_reg_evento FOREIGN KEY (id_evento) REFERENCES eventos(id_evento),
  CONSTRAINT fk_reg_asistente FOREIGN KEY (id_asistente) REFERENCES asistentes(id_asistente)
);

# Tabla de asistencia física (día del evento)
CREATE TABLE asistencia (
  id_asistencia   BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  id_registro     BIGINT UNSIGNED NOT NULL,   # FK registro
  hora_entrada    DATETIME NULL,
  hora_salida     DATETIME NULL,
  numero_mesa     VARCHAR(10) NULL,
  numero_asiento  VARCHAR(10) NULL,
  codigo_gafete   VARCHAR(64) NULL,           # QR o código de gafete
  creado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_asistencia_registro (id_registro),
  UNIQUE KEY uq_codigo_gafete (codigo_gafete),
  CONSTRAINT fk_asistencia_registro FOREIGN KEY (id_registro) REFERENCES registros(id_registro)
);

# Catálogo de preferencias alimenticias
CREATE TABLE preferencias_alimenticias (
  id_preferencia SMALLINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  nombre         VARCHAR(80) NOT NULL,     # Ej. 'Vegetariano', 'Vegano'
  descripcion    VARCHAR(200) NULL
);

# Relación entre asistente y preferencia
CREATE TABLE asistente_preferencia (
  id_asistente   BIGINT UNSIGNED NOT NULL,
  id_preferencia SMALLINT UNSIGNED NOT NULL,
  notas          VARCHAR(200) NULL,
  PRIMARY KEY (id_asistente, id_preferencia),
  CONSTRAINT fk_ap_asistente  FOREIGN KEY (id_asistente)  REFERENCES asistentes(id_asistente),
  CONSTRAINT fk_ap_preferencia FOREIGN KEY (id_preferencia) REFERENCES preferencias_alimenticias(id_preferencia)
);

# ===============================================================
# Vista práctica para exportar lista completa
# ===============================================================
CREATE OR REPLACE VIEW vw_evento_asistencia AS
SELECT
  e.codigo                    AS codigo_evento,
  e.nombre                    AS nombre_evento,
  a.nombre_completo,
  a.correo,
  a.telefono,
  a.empresa,
  a.puesto,
  a.generacion,
  CONCAT(LPAD(a.dia_cumple,2,'0'), '/', LPAD(a.mes_cumple,2,'0')) AS cumple_ddmm,
  r.asistencia,
  r.invitados,
  r.personalizador1,
  r.personalizador2,
  r.confirmado,
  r.fecha_confirmacion,
  s.hora_entrada,
  s.hora_salida,
  s.numero_mesa,
  s.numero_asiento,
  s.codigo_gafete
FROM registros r
JOIN asistentes a ON a.id_asistente = r.id_asistente
JOIN eventos e ON e.id_evento = r.id_evento
LEFT JOIN asistencia s ON s.id_registro = r.id_registro;

# ===============================================================
# Índices útiles
# ===============================================================
CREATE INDEX idx_reg_evento_asistencia ON registros (id_evento, asistencia);
CREATE INDEX idx_asistencia_entrada ON asistencia (hora_entrada);
CREATE INDEX idx_reg_evento ON registros (id_evento);
CREATE INDEX idx_reg_asistente ON registros (id_asistente);