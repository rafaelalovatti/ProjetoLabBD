-- Habilitar extensão earth_distance
-- Justificativa: Necessária para cálculos geográficos no Relatório 2 (distância entre cidades e aeroportos).
CREATE EXTENSION IF NOT EXISTS earth_distance;
CREATE EXTENSION IF NOT EXISTS cube;

-- Índice para Relatório 2 (aeroportos próximos a cidades)
-- Justificativa: Otimiza a busca por cidades em GeoCities15K e cálculos de distância em Airports.
CREATE INDEX idx_geocities_name ON GeoCities15K(Name); -- Acelera buscas por nome da cidade
CREATE INDEX idx_airports_location ON Airports USING GIST (
    ll_to_earth(LatDeg, LongDeg)
); -- Suporta cálculos geográficos com earth_distance

-- Índice para Relatório 4 (vitórias de escuderias)
-- Justificativa: Melhora a performance ao filtrar resultados por ConstructorId e Position.
CREATE INDEX idx_results_constructor_position ON Results(ConstructorId, Position);

-- Índice para Relatório 6 (pontos de pilotos por ano)
-- Justificativa: Otimiza junções e filtros por DriverId e RaceId, e buscas por ano em Races.
CREATE INDEX idx_results_driver_year ON Results(DriverId, RaceId);
CREATE INDEX idx_races_year ON Races(Year);