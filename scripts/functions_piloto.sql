-- Function to get the first and last year of a driver's data
CREATE OR REPLACE FUNCTION Public.ReportDriverYears(p_driver_id INTEGER)
RETURNS TABLE (FirstYear INTEGER, LastYear INTEGER) AS $$
BEGIN
    RETURN QUERY
    SELECT MIN(r.year) AS FirstYear, MAX(r.year) AS LastYear
    FROM Results res
    JOIN Races r ON res.raceid = r.raceid
    WHERE res.driverid = p_driver_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get detailed performance metrics for a driver
CREATE OR REPLACE FUNCTION Public.ReportDriverPerformance(p_driver_id INTEGER)
    RETURNS TABLE (
        Year INTEGER,
        CircuitName TEXT,
        TotalPoints INTEGER,
        TotalWins INTEGER,
        TotalRaces INTEGER
    ) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.year,
        c.name AS CircuitName,
        COALESCE(SUM(res.points)::INTEGER, 0) AS TotalPoints,
        SUM(CASE WHEN res.position = 1 THEN 1 ELSE 0 END)::INTEGER AS TotalWins,
        COUNT(res.resultid)::INTEGER AS TotalRaces
    FROM Results res
    JOIN Races r ON res.raceid = r.raceid
    JOIN Circuits c ON r.circuitid = c.circuitid
    WHERE res.driverid = p_driver_id
    GROUP BY r.year, c.name
    ORDER BY r.year, c.name;
END;
$$ LANGUAGE plpgsql;


-- Function for Relatório 6: Total points per year and race for a driver
CREATE OR REPLACE FUNCTION Public.ReportDriverPointsByYearAndRace(p_driver_id INTEGER)
RETURNS TABLE (
    Year INTEGER,
    RaceName TEXT,
    Points FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        r.year,
        r.name AS RaceName,
        COALESCE(SUM(res.points), 0) AS Points
    FROM Results res
    JOIN Races r ON res.raceid = r.raceid
    WHERE res.driverid = p_driver_id
    GROUP BY r.year, r.name
    ORDER BY r.year, Points DESC;
END;
$$ LANGUAGE plpgsql;

-- Function for Relatório 7: Count of results by status for a driver
CREATE OR REPLACE FUNCTION Public.ReportDriverResultsByStatus(p_driver_id INTEGER)
RETURNS TABLE (
    Status TEXT,
    Total BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.status,
        COUNT(*) AS Total
    FROM Results res
    JOIN Status s ON res.statusid = s.statusid
    WHERE res.driverid = p_driver_id
    GROUP BY s.status
    ORDER BY Total DESC;
END;
$$ LANGUAGE plpgsql;


-- Index on Results.driverid for filtering by driver
CREATE INDEX idx_results_driverid ON Results (driverid);

-- Index on Results.raceid for joining with Races
CREATE INDEX idx_results_raceid ON Results (raceid);

-- Index on Results.statusid for joining with Status
CREATE INDEX idx_results_statusid ON Results (statusid);

-- Index on Races.year for grouping and ordering
CREATE INDEX idx_races_year ON Races (year);

-- Composite index on Results for common query pattern in Relatório 6
CREATE INDEX idx_results_driverid_raceid ON Results (driverid, raceid, points);