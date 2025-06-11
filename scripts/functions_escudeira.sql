-- Criação de índices para otimizar a consulta
CREATE INDEX idx_results_constructorid ON Results (ConstructorId);
CREATE INDEX idx_results_driverid ON Results (DriverId);
CREATE INDEX idx_results_position ON Results (Position);
CREATE INDEX idx_driver_driverid ON Driver (DriverId);

-- Função PL/pgSQL para o Relatório 4
CREATE FUNCTION Public.ReportDriverWinsByConstructor(p_ConstructorId INTEGER)
    RETURNS TABLE (
        FullName TEXT,
        Wins BIGINT
    ) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        CONCAT(d.Forename, ' ', d.Surname) AS FullName,
        COUNT(r.ResultId) AS Wins
    FROM 
        Results r
        JOIN Driver d ON r.DriverId = d.DriverId
    WHERE 
        r.ConstructorId = p_ConstructorId
        AND r.Position = 1
    GROUP BY 
        d.DriverId, d.Forename, d.Surname
    ORDER BY 
        Wins DESC, FullName;
END;
$$ LANGUAGE plpgsql STABLE;


-- Criação de índices para otimizar a consulta
CREATE INDEX idx_results_constructorid ON Results (ConstructorId);
CREATE INDEX idx_results_statusid ON Results (StatusId);
CREATE INDEX idx_status_statusid ON Status (StatusId);

-- Função PL/pgSQL para o Relatório de Resultados por Status
CREATE OR REPLACE FUNCTION Public.ReportResultsByStatus(p_ConstructorId INTEGER)
    RETURNS TABLE (
        Status TEXT,
        ResultCount BIGINT
    ) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.Status,
        COUNT(r.ResultId) AS ResultCount
    FROM 
        Results r
        JOIN Status s ON r.StatusId = s.StatusId
    WHERE 
        r.ConstructorId = p_ConstructorId
    GROUP BY 
        s.StatusId, s.Status
    ORDER BY 
        ResultCount DESC, s.Status;
END;
$$ LANGUAGE plpgsql STABLE;


CREATE OR REPLACE FUNCTION Public.ReportConstructorWins(p_ConstructorId INTEGER)
RETURNS BIGINT AS $$
DECLARE
    win_count BIGINT;
BEGIN
    SELECT COUNT(*) INTO win_count
    FROM Results r
    WHERE r.ConstructorId = p_ConstructorId
      AND r.Position = 1;

    RETURN win_count;
END;
$$ LANGUAGE plpgsql STABLE;



CREATE OR REPLACE FUNCTION Public.ReportDistinctDrivers(p_ConstructorId INTEGER)
RETURNS BIGINT AS $$
DECLARE
    driver_count BIGINT;
BEGIN
    SELECT COUNT(DISTINCT r.DriverId)
    INTO driver_count
    FROM Results r
    WHERE r.ConstructorId = p_ConstructorId;

    RETURN driver_count;
END;
$$ LANGUAGE plpgsql STABLE;


CREATE OR REPLACE FUNCTION Public.ReportConstructorYears(p_ConstructorId INTEGER)
RETURNS TABLE (
    FirstYear INTEGER,
    LastYear INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        MIN(ra.Year) AS FirstYear,
        MAX(ra.Year) AS LastYear
    FROM 
        Results r
        JOIN Races ra ON r.RaceId = ra.RaceId
    WHERE 
        r.ConstructorId = p_ConstructorId;
END;
$$ LANGUAGE plpgsql STABLE;

