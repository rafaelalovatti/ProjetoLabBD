-- Criar tabela USERS para autenticação de usuários
-- Justificativa: Armazena credenciais de login para os três tipos de usuários (Administrador, Escuderia, Piloto),
-- com senhas hasheadas usando SCRAM-SHA-256 para segurança e IdOriginal para vincular a escuderias ou pilotos.
CREATE TABLE USERS (
    Userid SERIAL PRIMARY KEY,               -- Identificador único do usuário
    Login TEXT NOT NULL UNIQUE,             -- Login único (ex.: admin, mclaren_c, hamilton_d)
    Password TEXT NOT NULL,                 -- Senha hasheada com SCRAM-SHA-256
    Tipo TEXT NOT NULL CHECK (Tipo IN ('Administrador', 'Escuderia', 'Piloto')), -- Tipo de usuário
    IdOriginal INTEGER NOT NULL             -- Referência ao ConstructorId ou DriverId (0 para admin)
);

-- Criar tabela Users_Log para auditoria de acessos
-- Justificativa: Registra todos os logins no sistema, associando o Userid à data e hora do acesso,
-- permitindo auditoria de atividades conforme exigido.
CREATE TABLE Users_Log (
    LogId SERIAL PRIMARY KEY,               -- Identificador único do log
    Userid INTEGER REFERENCES USERS(Userid), -- Referência ao usuário que fez login
    LoginTime TIMESTAMP NOT NULL            -- Data e hora do login
);

-- Inserir usuário administrador
-- Justificativa: Cria o usuário 'admin' com senha hasheada para acesso total ao sistema.
INSERT INTO USERS (Login, Password, Tipo, IdOriginal)
VALUES ('admin', crypt('admin', gen_salt('bf')), 'Administrador', 0);