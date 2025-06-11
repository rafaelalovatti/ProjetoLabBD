-- Função para popular USERS com escuderias existentes
-- Justificativa: Automatiza a criação de usuários para todas as escuderias na tabela Constructors,
-- gerando logins no formato <constructorref>_c e senhas hasheadas, conforme especificado.
CREATE OR REPLACE FUNCTION populate_constructor_users()
RETURNS VOID AS $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN SELECT ConstructorId, ConstructorRef FROM Constructors
    LOOP
        INSERT INTO USERS (Login, Password, Tipo, IdOriginal)
        VALUES (
            rec.ConstructorRef || '_c',                  -- Login no formato <constructorref>_c
            crypt(rec.ConstructorRef, gen_salt('bf')),   -- Senha hasheada com SCRAM-SHA-256
            'Escuderia',                                 -- Tipo de usuário
            rec.ConstructorId                            -- Vincula ao ConstructorId
        )
        ON CONFLICT (Login) DO NOTHING;                 -- Evita duplicatas
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Função para popular USERS com pilotos existentes
-- Justificativa: Automatiza a criação de usuários para todos os pilotos na tabela Driver,
-- gerando logins no formato <driverref>_d e senhas hasheadas, conforme especificado.
CREATE OR REPLACE FUNCTION populate_driver_users()
RETURNS VOID AS $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN SELECT DriverId, DriverRef FROM Driver
    LOOP
        INSERT INTO USERS (Login, Password, Tipo, IdOriginal)
        VALUES (
            rec.DriverRef || '_d',                       -- Login no formato <driverref>_d
            crypt(rec.DriverRef, gen_salt('bf')),        -- Senha hasheada com SCRAM-SHA-256
            'Piloto',                                    -- Tipo de usuário
            rec.DriverId                                 -- Vincula ao DriverId
        )
        ON CONFLICT (Login) DO NOTHING;                 -- Evita duplicatas
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Executar funções de população
-- Justificativa: Garante que a tabela USERS seja inicializada com todos os usuários
-- correspondentes às escuderias e pilotos existentes na base.
SELECT populate_constructor_users();
SELECT populate_driver_users();

-- Função para dashboard de escuderia
-- Justificativa: Fornece dados agregados para o dashboard da escuderia, incluindo vitórias,
-- total de pilotos e anos de participação, atendendo aos requisitos do dashboard.
CREATE OR REPLACE FUNCTION get_constructor_dashboard(constructor_id INTEGER)
RETURNS TABLE (
    vitorias BIGINT,        -- Quantidade de vitórias (1º lugar)
    total_pilotos BIGINT,   -- Quantidade de pilotos distintos
    primeiro_ano INTEGER,   -- Primeiro ano de participação
    ultimo_ano INTEGER      -- Último ano de participação
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM Results r WHERE r.ConstructorId = constructor_id AND r.Position = 1) AS vitorias,
        (SELECT COUNT(DISTINCT r.DriverId) FROM Results r WHERE r.ConstructorId = constructor_id) AS total_pilotos,
        (SELECT MIN(ra.Year) FROM Results r JOIN Races ra ON r.RaceId = ra.RaceId WHERE r.ConstructorId = constructor_id) AS primeiro_ano,
        (SELECT MAX(ra.Year) FROM Results r JOIN Races ra ON r.RaceId = ra.RaceId WHERE r.ConstructorId = constructor_id) AS ultimo_ano;
END;
$$ LANGUAGE plpgsql;

-- Função para dashboard de piloto
-- Justificativa: Fornece dados agregados para o dashboard do piloto, incluindo anos de participação
-- e desempenho por ano/circuito (pontos, vitórias, corridas), atendendo aos requisitos do dashboard.
CREATE OR REPLACE FUNCTION get_driver_dashboard(driver_id INTEGER)
RETURNS TABLE (
    primeiro_ano INTEGER,   -- Primeiro ano de participação
    ultimo_ano INTEGER,     -- Último ano de participação
    ano INTEGER,            -- Ano da corrida
    circuito TEXT,          -- Nome do circuito
    pontos FLOAT,           -- Total de pontos
    vitorias BIGINT,        -- Quantidade de vitórias
    corridas BIGINT         -- Quantidade de corridas
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT MIN(ra.Year) FROM Results r JOIN Races ra ON r.RaceId = ra.RaceId WHERE r.DriverId = driver_id) AS primeiro_ano,
        (SELECT MAX(ra.Year) FROM Results r JOIN Races ra ON r.RaceId = ra.RaceId WHERE r.DriverId = driver_id) AS ultimo_ano,
        ra.Year,
        c.Name AS circuito,
        COALESCE(SUM(r.Points), 0) AS pontos,
        COUNT(CASE WHEN r.Position = 1 THEN 1 END) AS vitorias,
        COUNT(r.ResultId) AS corridas
    FROM Results r
    JOIN Races ra ON r.RaceId = ra.RaceId
    JOIN Circuits c ON ra.CircuitId = c.CircuitId
    WHERE r.DriverId = driver_id
    GROUP BY ra.Year, c.Name;
END;
$$ LANGUAGE plpgsql;