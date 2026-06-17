-- ============================================================
--  Schema Minero para demo RAG · HWC RDS PostgreSQL
--  Minera ficticia: "MineraAndes S.A."
-- ============================================================

CREATE TABLE IF NOT EXISTS equipos (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) UNIQUE NOT NULL,
    nombre          VARCHAR(100) NOT NULL,
    tipo            VARCHAR(50) NOT NULL,  -- excavadora / volquete / perforadora / cargador / otro
    area            VARCHAR(50),           -- tajo_norte / tajo_sur / planta / taller
    estado          VARCHAR(30) DEFAULT 'operativo',  -- operativo / mantenimiento / parado / standby
    horas_operacion INTEGER DEFAULT 0,
    ultima_revision DATE,
    operador_id     INTEGER
);

CREATE TABLE IF NOT EXISTS personal (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(120) NOT NULL,
    cargo           VARCHAR(80),
    area            VARCHAR(50),
    turno           VARCHAR(20) DEFAULT 'dia',  -- dia / noche / guardia
    estado          VARCHAR(20) DEFAULT 'activo',
    fecha_ingreso   DATE DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS produccion (
    id              SERIAL PRIMARY KEY,
    fecha           DATE NOT NULL,
    turno           VARCHAR(20) NOT NULL,
    area            VARCHAR(50),
    toneladas       NUMERIC(10,2),
    ley_mineral     NUMERIC(5,3),   -- % de cobre u otro mineral
    rendimiento     NUMERIC(5,2),   -- % de eficiencia
    equipo_id       INTEGER REFERENCES equipos(id),
    observaciones   VARCHAR(300)
);

CREATE TABLE IF NOT EXISTS incidentes (
    id              SERIAL PRIMARY KEY,
    fecha           TIMESTAMP DEFAULT NOW(),
    tipo            VARCHAR(50) NOT NULL,  -- accidente / near_miss / condicion_insegura / emergencia
    severidad       VARCHAR(20) DEFAULT 'bajo',  -- bajo / medio / alto / critico
    area            VARCHAR(50),
    descripcion     VARCHAR(500),
    personal_id     INTEGER REFERENCES personal(id),
    equipo_id       INTEGER REFERENCES equipos(id),
    estado          VARCHAR(20) DEFAULT 'abierto',  -- abierto / en_investigacion / cerrado
    accion_tomada   VARCHAR(300)
);

CREATE TABLE IF NOT EXISTS mantenimiento (
    id              SERIAL PRIMARY KEY,
    equipo_id       INTEGER REFERENCES equipos(id),
    tipo            VARCHAR(50),  -- preventivo / correctivo / predictivo
    descripcion     VARCHAR(300),
    fecha_inicio    TIMESTAMP DEFAULT NOW(),
    fecha_fin       TIMESTAMP,
    tecnico         VARCHAR(100),
    estado          VARCHAR(20) DEFAULT 'pendiente',  -- pendiente / en_proceso / completado
    costo           NUMERIC(10,2),
    prioridad       VARCHAR(20) DEFAULT 'normal'  -- baja / normal / alta / urgente
);

CREATE TABLE IF NOT EXISTS documentos (
    doc_id          VARCHAR(64) PRIMARY KEY,
    doc_name        VARCHAR(300) NOT NULL,
    obs_bucket      VARCHAR(120),
    chunk_count     INTEGER DEFAULT 0,
    indexed_at      TIMESTAMP DEFAULT NOW()
);

-- ── Datos de ejemplo ─────────────────────────────────────────

INSERT INTO personal (nombre, cargo, area, turno, estado) VALUES
  ('Carlos Quispe Mamani',    'Operador de Excavadora',   'tajo_norte', 'dia',    'activo'),
  ('Juan Huanca Flores',      'Operador de Volquete',     'tajo_norte', 'dia',    'activo'),
  ('María Torres Ccolque',    'Supervisora de Turno',     'tajo_sur',   'dia',    'activo'),
  ('Pedro Condori Yana',      'Técnico de Mantenimiento', 'taller',     'dia',    'activo'),
  ('Rosa Mamani Ccopa',       'Operadora de Perforadora', 'tajo_sur',   'noche',  'activo'),
  ('Luis Apaza Huanca',       'Operador de Cargador',     'planta',     'dia',    'activo'),
  ('Diego Vargas Ticona',     'Ingeniero de Minas',       'tajo_norte', 'dia',    'activo'),
  ('Ana Chura Mullisaca',     'Supervisora de Seguridad', 'tajo_sur',   'dia',    'activo'),
  ('Roberto Silva Pari',      'Operador de Volquete',     'tajo_norte', 'noche',  'activo'),
  ('Carmen Larico Quispe',    'Técnica de Laboratorio',   'planta',     'dia',    'activo')
ON CONFLICT DO NOTHING;

INSERT INTO equipos (codigo, nombre, tipo, area, estado, horas_operacion, ultima_revision, operador_id) VALUES
  ('EXC-001', 'Excavadora Komatsu PC800',   'excavadora',  'tajo_norte', 'operativo',    4520, '2026-05-15', 1),
  ('EXC-002', 'Excavadora CAT 390F',        'excavadora',  'tajo_sur',   'mantenimiento',3890, '2026-04-20', NULL),
  ('VOL-001', 'Volquete Komatsu 785-7',     'volquete',    'tajo_norte', 'operativo',    6200, '2026-05-28', 2),
  ('VOL-002', 'Volquete CAT 793F',          'volquete',    'tajo_norte', 'operativo',    5100, '2026-05-25', 9),
  ('VOL-003', 'Volquete Komatsu 785-7',     'volquete',    'tajo_sur',   'parado',       7800, '2026-03-10', NULL),
  ('PER-001', 'Perforadora Sandvik D65',    'perforadora', 'tajo_sur',   'operativo',    2300, '2026-05-30', 5),
  ('CAR-001', 'Cargador CAT 994K',          'cargador',    'planta',     'operativo',    3100, '2026-05-20', 6),
  ('EXC-003', 'Excavadora Hitachi EX1200',  'excavadora',  'tajo_norte', 'parado',       8900, '2026-02-15', NULL),
  ('VOL-004', 'Volquete Liebherr T264',     'volquete',    'tajo_sur',   'standby',      4400, '2026-05-10', NULL),
  ('PER-002', 'Perforadora Atlas Copco',    'perforadora', 'tajo_norte', 'mantenimiento',1800, '2026-05-01', NULL)
ON CONFLICT DO NOTHING;

INSERT INTO produccion (fecha, turno, area, toneladas, ley_mineral, rendimiento, equipo_id, observaciones) VALUES
  ('2026-06-08', 'dia',   'tajo_norte', 8500.00, 0.485, 92.5, 1, 'Producción normal'),
  ('2026-06-08', 'dia',   'tajo_sur',   6200.00, 0.512, 85.0, 6, 'Reducción por mantenimiento EXC-002'),
  ('2026-06-08', 'noche', 'tajo_norte', 7800.00, 0.471, 89.0, 3, 'Turno noche sin incidentes'),
  ('2026-06-08', 'noche', 'tajo_sur',   5900.00, 0.498, 82.0, 7, 'Producción afectada por VOL-003 parado'),
  ('2026-06-07', 'dia',   'tajo_norte', 9100.00, 0.490, 95.0, 1, 'Mejor turno de la semana'),
  ('2026-06-07', 'dia',   'tajo_sur',   7400.00, 0.505, 91.0, 6, 'Producción normal'),
  ('2026-06-07', 'noche', 'tajo_norte', 8200.00, 0.478, 88.0, 3, 'Lluvia leve afectó operaciones'),
  ('2026-06-07', 'noche', 'tajo_sur',   6800.00, 0.495, 87.0, 7, 'Normal'),
  ('2026-06-06', 'dia',   'tajo_norte', 8800.00, 0.488, 93.0, 1, 'Normal'),
  ('2026-06-06', 'dia',   'tajo_sur',   7100.00, 0.510, 90.0, 6, 'Normal')
ON CONFLICT DO NOTHING;

INSERT INTO incidentes (fecha, tipo, severidad, area, descripcion, personal_id, equipo_id, estado, accion_tomada) VALUES
  (NOW() - INTERVAL '2 hours',  'condicion_insegura', 'alto',   'tajo_norte', 'Talud inestable detectado en banco 15, riesgo de derrumbe', 7, NULL,  'abierto',          'Área acordonada, esperando evaluación geotécnica'),
  (NOW() - INTERVAL '5 hours',  'near_miss',          'medio',  'tajo_norte', 'VOL-001 casi impacta con EXC-001 en intersección de rampa', 2, 3,     'en_investigacion', 'Revisión de protocolos de tráfico interno'),
  (NOW() - INTERVAL '1 day',    'accidente',          'critico','tajo_sur',   'Operador sufrió golpe en cabeza durante maniobra de EXC-002', 1, 2,   'en_investigacion', 'Traslado a clínica, equipo bloqueado para investigación'),
  (NOW() - INTERVAL '3 days',   'emergencia',         'alto',   'planta',     'Derrame menor de reactivos en área de flotación', 10, NULL, 'cerrado',          'Limpieza completada, reporte a OSINERGMIN enviado'),
  (NOW() - INTERVAL '6 hours',  'condicion_insegura', 'medio',  'tajo_sur',   'VOL-003 presenta fuga de aceite hidráulico', NULL, 5,    'abierto',          'Equipo parado, técnico asignado')
ON CONFLICT DO NOTHING;

INSERT INTO mantenimiento (equipo_id, tipo, descripcion, fecha_inicio, fecha_fin, tecnico, estado, costo, prioridad) VALUES
  (2,  'correctivo',  'Reparación de sistema hidráulico brazo principal',  NOW() - INTERVAL '2 days', NULL,                        'Pedro Condori',  'en_proceso',  45000.00, 'alta'),
  (5,  'correctivo',  'Fuga de aceite en sistema de dirección',            NOW() - INTERVAL '1 day',  NULL,                        'Pedro Condori',  'en_proceso',  12000.00, 'urgente'),
  (8,  'correctivo',  'Falla en motor principal, requiere reemplazo',      NOW() - INTERVAL '15 days',NULL,                        'Externo',        'en_proceso', 180000.00, 'alta'),
  (10, 'preventivo',  'Mantenimiento programado 2000 horas',               NOW() - INTERVAL '3 days', NOW() - INTERVAL '1 day',   'Pedro Condori',  'completado',   8500.00, 'normal'),
  (1,  'preventivo',  'Mantenimiento programado 500 horas',                NOW() + INTERVAL '5 days', NOW() + INTERVAL '6 days',  'Pedro Condori',  'pendiente',    6000.00, 'normal')
ON CONFLICT DO NOTHING;
