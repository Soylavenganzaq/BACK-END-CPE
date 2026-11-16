-- SCRIPT UNIFICADO: ESTRUCTURA + DATOS DE PRUEBA + HISTORIAL POR MAC
-- Revisar datos de prueba y credenciales/hash antes de usar en ambientes compartidos.

-- ============================================================
-- BASE DE DATOS PRECONFIGURACIÓN
-- Modelo: Centrado en Eventos
-- ============================================================

CREATE SCHEMA IF NOT EXISTS inventario;
SET search_path TO inventario, public;

-- Definimos la zona horaria
SET TIMEZONE = 'America/Bogota';

-- 2. TIPOS DE DATOS PERSONALIZADOS (ENUM)
CREATE TYPE tipo_operacion_enum AS ENUM ('INGRESO', 'ENTREGA');
CREATE TYPE estado_equipo_enum AS ENUM ('INGRESADO', 'ENTREGADO');

-- 3. TABLAS DE CATÁLOGOS Y SEGURIDAD
CREATE TABLE roles (
    id_rol SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    CONSTRAINT chk_roles_nombre CHECK (nombre IN ('Super Admin', 'Admin', 'Usuario'))
);

CREATE TABLE tecnicos (
    identificacion VARCHAR(50) PRIMARY KEY,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    ciudad VARCHAR(100) NOT NULL,
    sede VARCHAR(100) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE usuarios (
    id_usuario BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identificacion_tecnico VARCHAR(50) REFERENCES tecnicos(identificacion) ON DELETE RESTRICT,
    id_rol SMALLINT NOT NULL REFERENCES roles(id_rol) ON DELETE RESTRICT,
    correo VARCHAR(150) NOT NULL UNIQUE,
    contrasena TEXT NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tipos_equipo (
    id_tipo SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE condiciones_equipo (
    id_condicion SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
);

-- 4. TABLA NÚCLEO DE EVENTOS
CREATE TABLE equipos (
    id_equipo BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mac TEXT NOT NULL,
    id_tipo SMALLINT NOT NULL REFERENCES tipos_equipo(id_tipo) ON DELETE RESTRICT,
    id_condicion_ingreso SMALLINT NOT NULL REFERENCES condiciones_equipo(id_condicion) ON DELETE RESTRICT,
    id_condicion_entrega SMALLINT REFERENCES condiciones_equipo(id_condicion) ON DELETE RESTRICT,
    estado estado_equipo_enum NOT NULL DEFAULT 'INGRESADO',
    fecha_ingreso TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_entrega TIMESTAMP,
    observaciones TEXT,
    
    CONSTRAINT restriccion_condicion_entrega CHECK (
        (id_condicion_entrega IS NULL OR id_condicion_ingreso = id_condicion_entrega)
        OR 
        (observaciones IS NOT NULL AND TRIM(observaciones) <> '')
    )
);

-- 5. TABLA DE OPERACIONES (CABECERA DE LOTES)
CREATE TABLE operaciones (
    id_operacion BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo_operacion tipo_operacion_enum NOT NULL,
    identificacion_tecnico VARCHAR(50) REFERENCES tecnicos(identificacion) ON DELETE RESTRICT,
    id_usuario BIGINT NOT NULL REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    hora TIME NOT NULL DEFAULT CURRENT_TIME,
    observaciones TEXT
);

-- 6. TABLA INTERMEDIA (DETALLE N:M)
CREATE TABLE detalle_operacion (
    id_detalle BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_operacion BIGINT NOT NULL REFERENCES operaciones(id_operacion) ON DELETE CASCADE,
    id_equipo BIGINT NOT NULL REFERENCES equipos(id_equipo) ON DELETE RESTRICT
);

-- 7. TABLA DE AUDITORÍA GENERAL
CREATE TABLE auditoria (
    id_auditoria BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario BIGINT REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tabla_afectada TEXT NOT NULL,
    operacion VARCHAR(10) NOT NULL,
    registro_afectado TEXT,
    informacion_anterior JSONB,
    informacion_nueva JSONB
);

-- ÍNDICES DE RENDIMIENTO
CREATE INDEX indice_equipos_mac ON equipos(mac);
CREATE INDEX indice_equipos_estado ON equipos(estado);
CREATE INDEX indice_tecnicos_ciudad_sede ON tecnicos(ciudad, sede);
CREATE INDEX indice_operaciones_fecha ON operaciones(fecha);
CREATE INDEX indice_operaciones_fecha_hora ON operaciones((fecha + hora));
CREATE INDEX indice_detalle_operacion_equipo ON detalle_operacion(id_equipo);
CREATE INDEX indice_detalle_operacion_operacion ON detalle_operacion(id_operacion);
CREATE INDEX indice_auditoria_fecha ON auditoria(fecha_hora);

-- Garantiza que una MAC solo tenga UN registro activo en estado 'INGRESADO'
CREATE UNIQUE INDEX indice_mac_activa_unica 
ON equipos (mac) 
WHERE estado = 'INGRESADO';


-- ============================================================
-- FUNCIONES ALMACENADAS
-- ============================================================

CREATE OR REPLACE FUNCTION registro_ingreso_lote(
    p_identificacion_tecnico VARCHAR(50),
    p_id_usuario BIGINT,
    p_observaciones_operacion TEXT,
    p_macs TEXT[],
    p_id_tipo INT,
    p_id_condicion INT
) RETURNS BIGINT 
LANGUAGE plpgsql
SET search_path = inventario, public
AS $$
DECLARE
    v_id_operacion BIGINT;
    v_macs_duplicadas TEXT[];
BEGIN
    SELECT ARRAY_AGG(mac) INTO v_macs_duplicadas
    FROM equipos
    WHERE mac = ANY(p_macs) AND estado = 'INGRESADO';

    IF v_macs_duplicadas IS NOT NULL AND array_length(v_macs_duplicadas, 1) > 0 THEN
        RAISE EXCEPTION 'Error de negocio: Las siguientes MACs ya se encuentran en laboratorio (estado INGRESADO): %', array_to_string(v_macs_duplicadas, ', ');
    END IF;

    INSERT INTO operaciones (tipo_operacion, identificacion_tecnico, id_usuario, observaciones)
    VALUES ('INGRESO', p_identificacion_tecnico, p_id_usuario, p_observaciones_operacion)
    RETURNING id_operacion INTO v_id_operacion;

    WITH nuevos AS (
        INSERT INTO equipos (mac, id_tipo, id_condicion_ingreso, estado)
        SELECT 
            m, 
            p_id_tipo, 
            p_id_condicion, 
            'INGRESADO'::estado_equipo_enum
        FROM UNNEST(p_macs) AS m
        RETURNING id_equipo
    )
    INSERT INTO detalle_operacion (id_operacion, id_equipo)
    SELECT v_id_operacion, id_equipo FROM nuevos;

    RETURN v_id_operacion;
END;
$$;

CREATE OR REPLACE FUNCTION registro_entrega_lote(
    p_identificacion_tecnico VARCHAR(50),
    p_id_usuario BIGINT,
    p_observaciones_operacion TEXT,
    p_macs TEXT[],
    p_id_condicion INT
) RETURNS BIGINT 
LANGUAGE plpgsql
SET search_path = inventario, public
AS $$
DECLARE
    v_id_operacion BIGINT;
    v_macs_invalidas TEXT[];
BEGIN
    SELECT ARRAY_AGG(m) INTO v_macs_invalidas
    FROM UNNEST(p_macs) AS m
    WHERE NOT EXISTS (
        SELECT 1 
        FROM equipos e 
        WHERE e.mac = m AND e.estado = 'INGRESADO'
    );

    IF v_macs_invalidas IS NOT NULL AND array_length(v_macs_invalidas, 1) > 0 THEN
        RAISE EXCEPTION 'Error de negocio: Las siguientes MACs no se encuentran en bodega para entrega (estado INGRESADO): %', 
            array_to_string(v_macs_invalidas, ', ');
    END IF;

    INSERT INTO operaciones (tipo_operacion, identificacion_tecnico, id_usuario, observaciones)
    VALUES ('ENTREGA', p_identificacion_tecnico, p_id_usuario, p_observaciones_operacion)
    RETURNING id_operacion INTO v_id_operacion;

    WITH actualizados AS (
        UPDATE equipos e
        SET 
            estado = 'ENTREGADO'::estado_equipo_enum,
            id_condicion_entrega = p_id_condicion,
            fecha_entrega = CURRENT_TIMESTAMP,
            observaciones = COALESCE(p_observaciones_operacion, e.observaciones)
        WHERE e.mac = ANY(p_macs) AND e.estado = 'INGRESADO'
        RETURNING e.id_equipo
    )
    INSERT INTO detalle_operacion (id_operacion, id_equipo)
    SELECT v_id_operacion, id_equipo FROM actualizados;

    RETURN v_id_operacion;
END;
$$;

CREATE OR REPLACE FUNCTION inventario.fn_total_equipos_por_usuario()
RETURNS TABLE (
    usuario VARCHAR,
    total_equipos BIGINT
) 
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        TRIM(t.identificacion)::VARCHAR AS usuario,
        COUNT(det.id_equipo) AS total_equipos
    FROM inventario.tecnicos t
    INNER JOIN inventario.operaciones o 
        ON TRIM(t.identificacion) = TRIM(o.identificacion_tecnico)
    INNER JOIN inventario.detalle_operacion det 
        ON o.id_operacion = det.id_operacion
    GROUP BY t.identificacion
    ORDER BY total_equipos DESC;
END;
$$;


-- ============================================================
-- TRIGGERS Y AUDITORÍA
-- ============================================================

CREATE OR REPLACE FUNCTION inventario.fn_auditar_tabla()
RETURNS TRIGGER AS $$
DECLARE
    v_id_usuario BIGINT;
BEGIN
    BEGIN
        v_id_usuario := NULLIF(current_setting('app.current_user_id', true), '')::BIGINT;
    EXCEPTION WHEN OTHERS THEN
        v_id_usuario := NULL;
    END;

    IF (TG_OP = 'INSERT') THEN
        INSERT INTO inventario.auditoria (
            id_usuario, tabla_afectada, operacion, registro_afectado, informacion_nueva
        )
        VALUES (
            v_id_usuario, TG_TABLE_NAME, TG_OP, ROW(NEW.*)::TEXT, to_jsonb(NEW)
        );
        RETURN NEW;

    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO inventario.auditoria (
            id_usuario, tabla_afectada, operacion, registro_afectado, informacion_anterior, informacion_nueva
        )
        VALUES (
            v_id_usuario, TG_TABLE_NAME, TG_OP, ROW(NEW.*)::TEXT, to_jsonb(OLD), to_jsonb(NEW)
        );
        RETURN NEW;

    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO inventario.auditoria (
            id_usuario, tabla_afectada, operacion, registro_afectado, informacion_anterior
        )
        VALUES (
            v_id_usuario, TG_TABLE_NAME, TG_OP, ROW(OLD.*)::TEXT, to_jsonb(OLD)
        );
        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_auditoria_equipos
AFTER INSERT OR UPDATE OR DELETE ON inventario.equipos
FOR EACH ROW EXECUTE FUNCTION inventario.fn_auditar_tabla();

CREATE TRIGGER trg_auditoria_operaciones
AFTER INSERT OR UPDATE OR DELETE ON inventario.operaciones
FOR EACH ROW EXECUTE FUNCTION inventario.fn_auditar_tabla();

CREATE TRIGGER trg_auditoria_usuarios
AFTER INSERT OR UPDATE OR DELETE ON inventario.usuarios
FOR EACH ROW EXECUTE FUNCTION inventario.fn_auditar_tabla();

CREATE TRIGGER trg_auditoria_tecnicos
AFTER INSERT OR UPDATE OR DELETE ON inventario.tecnicos
FOR EACH ROW EXECUTE FUNCTION inventario.fn_auditar_tabla();


-- ============================================================
-- VISTAS
-- ============================================================

CREATE OR REPLACE VIEW inventario.v_equipos_ingresados AS
SELECT 
    e.id_equipo,
    e.mac,
    te.nombre AS tipo_equipo,
    ce.nombre AS condicion_ingreso,
    e.estado,
    e.fecha_ingreso,
    e.observaciones
FROM inventario.equipos e
INNER JOIN inventario.tipos_equipo te 
    ON e.id_tipo = te.id_tipo
INNER JOIN inventario.condiciones_equipo ce 
    ON e.id_condicion_ingreso = ce.id_condicion
WHERE e.estado = 'INGRESADO';

CREATE OR REPLACE VIEW inventario.v_equipos_sin_rotacion AS
SELECT 
    e.id_equipo,
    e.mac,
    te.nombre AS tipo_equipo,
    ce.nombre AS condicion_ingreso,
    e.estado,
    e.fecha_ingreso,
    CURRENT_TIMESTAMP - e.fecha_ingreso AS tiempo_en_bodega,
    EXTRACT(DAY FROM (CURRENT_TIMESTAMP - e.fecha_ingreso))::INT AS dias_en_bodega,
    e.observaciones
FROM inventario.equipos e
INNER JOIN inventario.tipos_equipo te 
    ON e.id_tipo = te.id_tipo
INNER JOIN inventario.condiciones_equipo ce 
    ON e.id_condicion_ingreso = ce.id_condicion
WHERE e.estado = 'INGRESADO'
  AND e.fecha_ingreso < CURRENT_TIMESTAMP - INTERVAL '1 day';

CREATE OR REPLACE VIEW inventario.v_resumen_equipos_entregados AS
SELECT 
    te.nombre AS tipo_equipo,
    ce.nombre AS condicion_entrega,
    COUNT(e.id_equipo) AS total_entregados,
    MIN(e.fecha_entrega)::DATE AS primera_entrega,
    MAX(e.fecha_entrega)::DATE AS ultima_entrega
FROM inventario.equipos e
INNER JOIN inventario.tipos_equipo te 
    ON e.id_tipo = te.id_tipo
INNER JOIN inventario.condiciones_equipo ce 
    ON e.id_condicion_entrega = ce.id_condicion
WHERE e.estado = 'ENTREGADO'
GROUP BY te.nombre, ce.nombre;

CREATE OR REPLACE VIEW inventario.v_cantidad_equipos_por_familia AS
SELECT 
    te.nombre AS familia_equipo,
    COUNT(e.id_equipo) AS cantidad_entregados
FROM inventario.tipos_equipo te
LEFT JOIN inventario.equipos e 
    ON te.id_tipo = e.id_tipo 
   AND e.estado = 'ENTREGADO'
GROUP BY te.id_tipo, te.nombre;


-- ============================================================
-- PROCEDIMIENTOS ALMACENADOS
-- ============================================================

CREATE OR REPLACE PROCEDURE inventario.sp_exportar_equipos_csv(
    p_estado inventario.estado_equipo_enum DEFAULT 'INGRESADO',
    p_ruta_archivo TEXT DEFAULT 'C:/Users/Public/reporte_equipos.csv',
    p_fecha_inicio DATE DEFAULT NULL,
    p_fecha_fin DATE DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_sql TEXT;
    v_where TEXT;
BEGIN
    v_where := format('WHERE e.estado = %L', p_estado);

    IF p_fecha_inicio IS NOT NULL THEN
        IF p_estado = 'INGRESADO' THEN
            v_where := v_where || format(' AND e.fecha_ingreso::DATE >= %L', p_fecha_inicio);
        ELSE
            v_where := v_where || format(' AND e.fecha_entrega::DATE >= %L', p_fecha_inicio);
        END IF;
    END IF;

    IF p_fecha_fin IS NOT NULL THEN
        IF p_estado = 'INGRESADO' THEN
            v_where := v_where || format(' AND e.fecha_ingreso::DATE <= %L', p_fecha_fin);
        ELSE
            v_where := v_where || format(' AND e.fecha_entrega::DATE <= %L', p_fecha_fin);
        END IF;
    END IF;

    v_sql := format(
        'COPY (
            SELECT 
                e.id_equipo,
                e.mac,
                te.nombre AS tipo_equipo,
                ce_ing.nombre AS condicion_ingreso,
                ce_ent.nombre AS condicion_entrega,
                e.estado,
                e.fecha_ingreso,
                e.fecha_entrega,
                u.correo AS usuario_registro,
                e.observaciones
            FROM inventario.equipos e
            INNER JOIN inventario.tipos_equipo te 
                ON e.id_tipo = te.id_tipo
            INNER JOIN inventario.condiciones_equipo ce_ing 
                ON e.id_condicion_ingreso = ce_ing.id_condicion
            LEFT JOIN inventario.condiciones_equipo ce_ent 
                ON e.id_condicion_entrega = ce_ent.id_condicion
            LEFT JOIN inventario.detalle_operacion det 
                ON e.id_equipo = det.id_equipo
            LEFT JOIN inventario.operaciones o 
                ON det.id_operacion = o.id_operacion AND o.tipo_operacion = e.estado::TEXT
            LEFT JOIN inventario.usuarios u 
                ON o.id_usuario = u.id_usuario
            %s
        ) TO %L WITH (FORMAT CSV, HEADER, DELIMITER '','', ENCODING ''UTF8'')',
        v_where, p_ruta_archivo
    );

    EXECUTE v_sql;
    
    RAISE NOTICE 'Reporte exportado exitosamente en: %', p_ruta_archivo;
END;
$$;

-- ============================================================
-- DATOS INICIALES Y DE PRUEBA
-- ============================================================

-- ============================================================
-- LLenado de datos
-- ============================================================

SET search_path TO inventario, public;
-- Tabla Roles
INSERT INTO roles (nombre) VALUES ('Super Admin'), ('Admin'), ('Usuario');

-- Tipo_equipos
INSERT INTO tipos_equipo (nombre) VALUES 
('PHANTOM'),
('PHANTOM F2'),
('TVBOX'),
('ORB1'),
('ORB2'),
('DECO M5'),
('EERO'),
('POE'),
('SWITCH'),
('VILOO'),
('VILO5'),
('POE ADMIN 2.5'),
('POE ADMIN 1.0'),
('PHANTOMX'),
('PHANTOMBIT'),
('TV-BOX MDM');


--condiciones_equipo
--Pendiente Validar con Alejo más estados o reevaluación de estados.

INSERT INTO condiciones_equipo (nombre) VALUES 
('NUEVO'), ('REINTEGRO'), ('INCOMPLETO'), ('OBSOLETO'), 
('CONTAMINADO CUCARACHAS'), ('PUERTOS MALOS'), ('CARCASA MALA'), ('RAYADO');


--técnicos

INSERT INTO tecnicos (identificacion, nombres, apellidos, ciudad, sede) VALUES
('1000226390', 'David Santiago', 'Becerra Hernandez', 'Bogotá', 'Montevideo'),
('1000617061', 'Angel Felipe', 'Lemus Rodriguez', 'Bogotá', 'Montevideo'),
('1000635386', 'Reinel', 'Villegas', 'Bogotá', 'Montevideo'),
('1001576467', 'Jhoan Esteban', 'Cuervo Osorio', 'Medellín', 'OGUA'),
('1007240336', 'Cristian David', 'Sanchez', 'Medellín', 'OGUA'),
('1010229636', 'Gabriel Camilo', 'Ferro Sanchez', 'Bogotá', 'Montevideo'),
('1017270918', 'Kevin', 'Alvarez Alvarez', 'Medellín', 'OGUA'),
('1020408256', 'Alejandro', 'Calderón', 'Bogotá', 'Montevideo'),
('1021663875', 'Bryan Gabriel', 'Cardozo Benavides', 'Bogotá', 'Montevideo'),
('1022922639', 'Oscar Ivan', 'Castro Cerquera', 'Bogotá', 'Montevideo'),
('1022929844', 'Harrison Yesid', 'Ballesteros Barreto', 'Bogotá', 'Montevideo'),
('1031640268', 'Julio Cesar', 'Corredor Torres', 'Bogotá', 'Montevideo'),
('1033682204', 'Yeison Jesus', 'Rucinque Rubio', 'Bogotá', 'Montevideo'),
('1036448413', 'Sebastian', 'Ortiz', 'Medellín', 'OGUA'),
('1038867691', 'Daniel', 'Espinosa Sierra', 'Medellín', 'OGUA'),
('1038868521', 'Daniel', 'Cardona Rincon', 'Medellín', 'OGUA'),
('1039459130', 'Kevin', 'Montoya', 'Medellín', 'OGUA'),
('1089599835', 'Julian', 'Cortes Largo', 'Bogotá', 'Montevideo'),
('1090336786', 'Alvaro Yovany', 'Arenas Ospina', 'Medellín', 'OGUA'),
('1120838150', 'Alejandra', 'Rincon', 'Medellín', 'OGUA'),
('1123801480', 'Paulandrea', 'Mosquera', 'Bogotá', 'Montevideo'),
('1128443106', 'Juan Carlos', 'Londoño', 'Medellín', 'OGUA'),
('1152193172', 'Andres', 'Martinez', 'Medellín', 'OGUA'),
('1152206265', 'Samir', 'Murillo', 'Medellín', 'OGUA'),
('1152213127', 'John', 'Vallejo', 'Medellín', 'OGUA'),
('98709418', 'Juan Esteban', 'Sanchez Rivera', 'Medellín', 'OGUA');


INSERT INTO usuarios (identificacion_tecnico, id_rol, correo, contrasena) VALUES
('1000226390', 3, 'david.becerra@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1000617061', 3, 'angel.lemus@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1001576467', 3, 'jhoan.cuervo@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1007240336', 3, 'cristian.sanchez@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1010229636', 3, 'gabriel.ferro@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1017270918', 3, 'kevin.alvarez@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1020408256', 3, 'alejandro.calderon@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1021663875', 3, 'bryan.cardozo@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1022922639', 3, 'oscar.castro@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1022929844', 3, 'harrison.ballesteros@somosinternet.co', '$2a$1$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1031640268', 3, 'julio.corredor@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1033682204', 3, 'yeison.rucinque@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1036448413', 3, 'sebastian.ortiz@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1038867691', 3, 'daniel.espinosa@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1038868521', 3, 'daniel.cardona@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1039459130', 3, 'kevin.montoya@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1089599835', 3, 'julian.cortes@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1090336786', 3, 'alvaro.arenas@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1120838150', 3, 'alejandra.rincon@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1123801480', 3, 'paulandrea.mosquera@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1128443106', 2, 'juan.londono@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1152193172', 1, 'andres.martinez@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1152206265', 3, 'samir.murillo@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('1152213127', 3, 'john.vallejo@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG'),
('98709418', 3, 'juan.sanchez@somosinternet.co', '$2a$12$eImiTXuWVxfM37uY4JANjO2z/1pS3/L.o/AueM2R6O1fWfT8N/6aG');


SELECT registro_ingreso_lote(
    '1000226390',
    1, -- ID del usuario que registra (Debe existir en tabla usuarios)
    'Ingreso inicial limpio de prueba', --Puede ser un campo null
    ARRAY['C8:EE:A6:64:B8:32', '04:8F:00:09:C9:4B'], -- Arreglo de MACs a ingresar
    2, -- Se asigna el tipo mismo tipo a ambas MACs
    1  -- Se asigna la misma condición a ambas MACs
);


SELECT registro_entrega_lote(
    '1000226390', 
    1, 
    'Entrega de lote para despliegue en campo', -- Observaciones (Obligatorio si cambia la condición)
    ARRAY['C8:EE:A6:64:B8:32', '04:8F:00:09:C9:4B'], 
    1 -- ID de la condición de entrega (Ej: 1 = Bueno)
);


-- ============================================================
-- HISTORIAL COMPLETO DE EQUIPOS POR MAC
-- ============================================================
CREATE OR REPLACE FUNCTION inventario.fn_historial_por_mac(
    p_mac TEXT
)
RETURNS TABLE (
    id_equipo BIGINT,
    mac TEXT,
    id_operacion BIGINT,
    tipo_operacion TEXT,
    id_usuario BIGINT,
    identificacion_tecnico VARCHAR,
    fecha DATE,
    hora TIME,
    id_tipo SMALLINT,
    id_condicion_ingreso SMALLINT,
    id_condicion_entrega SMALLINT,
    estado TEXT,
    fecha_ingreso TIMESTAMP,
    fecha_entrega TIMESTAMP,
    observaciones TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id_equipo,
        e.mac,
        o.id_operacion,
        o.tipo_operacion::TEXT,
        o.id_usuario,
        o.identificacion_tecnico,
        o.fecha,
        o.hora,
        e.id_tipo,
        e.id_condicion_ingreso,
        e.id_condicion_entrega,
        e.estado::TEXT,
        e.fecha_ingreso,
        e.fecha_entrega,
        e.observaciones
    FROM inventario.equipos e
    INNER JOIN inventario.detalle_operacion d
        ON d.id_equipo = e.id_equipo
    INNER JOIN inventario.operaciones o
        ON o.id_operacion = d.id_operacion
    WHERE UPPER(TRIM(e.mac)) = UPPER(TRIM(p_mac))
    ORDER BY o.fecha ASC, o.hora ASC, o.id_operacion ASC;
END;
$$;
