-- Função para sincronizar USERS com Constructors
-- Justificativa: Garante que a tabela USERS seja atualizada automaticamente quando uma escuderia
-- é inserida, atualizada ou excluída, respeitando chaves estrangeiras em tabelas dependentes.
CREATE OR REPLACE FUNCTION sync_constructor_user()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        BEGIN
            INSERT INTO USERS (Login, Password, Tipo, IdOriginal)
            VALUES (
                NEW.ConstructorRef || '_c',
                crypt(NEW.ConstructorRef, gen_salt('bf')),
                'Escuderia',
                NEW.ConstructorId
            );
        EXCEPTION
            WHEN unique_violation THEN
                RAISE EXCEPTION 'Usuário com login % já existe', NEW.ConstructorRef || '_c';
                RETURN NULL; -- Cancela a inserção em Constructors
        END;
    ELSIF TG_OP = 'UPDATE' THEN
        UPDATE USERS
        SET Login = NEW.ConstructorRef || '_c',
            Password = crypt(NEW.ConstructorRef, gen_salt('bf'))
        WHERE IdOriginal = NEW.ConstructorId AND Tipo = 'Escuderia';
    ELSIF TG_OP = 'DELETE' THEN
        -- Verificar dependências antes de deletar
        IF EXISTS (
            SELECT 1 FROM Results WHERE ConstructorId = OLD.ConstructorId
            UNION
            SELECT 1 FROM Qualifying WHERE ConstructorId = OLD.ConstructorId
        ) THEN
            RAISE EXCEPTION 'Escuderia % não pode ser excluída devido a registros dependentes', OLD.ConstructorRef;
        ELSE
            DELETE FROM USERS WHERE IdOriginal = OLD.ConstructorId AND Tipo = 'Escuderia';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER constructor_user_trigger
AFTER INSERT OR UPDATE OR DELETE ON Constructors
FOR EACH ROW EXECUTE FUNCTION sync_constructor_user();

-- Função para sincronizar USERS com Driver
-- Justificativa: Garante que a tabela USERS seja atualizada automaticamente quando um piloto
-- é inserido, atualizado ou excluído, respeitando chaves estrangeiras.
CREATE OR REPLACE FUNCTION sync_driver_user()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        BEGIN
            INSERT INTO USERS (Login, Password, Tipo, IdOriginal)
            VALUES (
                NEW.DriverRef || '_d',
                crypt(NEW.DriverRef, gen_salt('bf')),
                'Piloto',
                NEW.DriverId
            );
        EXCEPTION
            WHEN unique_violation THEN
                RAISE EXCEPTION 'Usuário com login % já existe', NEW.DriverRef || '_d';
                RETURN NULL; -- Cancela a inserção em Driver
        END;
    ELSIF TG_OP = 'UPDATE' THEN
        UPDATE USERS
        SET Login = NEW.DriverRef || '_d',
            Password = crypt(NEW.DriverRef, gen_salt('bf'))
        WHERE IdOriginal = NEW.DriverId AND Tipo = 'Piloto';
    ELSIF TG_OP = 'DELETE' THEN
        -- Verificar dependências antes de excluir
        IF EXISTS (
            SELECT 1 FROM Results WHERE DriverId = OLD.DriverId
            UNION
            SELECT 1 FROM Qualifying WHERE DriverId = OLD.DriverId
            UNION
            SELECT 1 FROM DriverStandings WHERE DriverId = OLD.DriverId
            UNION
            SELECT 1 FROM LapTimes WHERE DriverId = OLD.DriverId
            UNION
            SELECT 1 FROM PitStops WHERE DriverId = OLD.DriverId
        ) THEN
            RAISE EXCEPTION 'Piloto % não pode ser excluído devido a registros dependentes', OLD.DriverRef;
        ELSE
            DELETE FROM USERS WHERE IdOriginal = OLD.DriverId AND Tipo = 'Piloto';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER driver_user_trigger
AFTER INSERT OR UPDATE OR DELETE ON Driver
FOR EACH ROW EXECUTE FUNCTION sync_driver_user();