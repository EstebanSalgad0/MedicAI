-- Una base de datos por microservicio (patrón database-per-service).
-- Ningún servicio lee la base de otro: se comunican solo por API.
CREATE DATABASE agendamiento;
CREATE DATABASE recordatorios;
CREATE DATABASE derivacion;
CREATE DATABASE medicamentos;
CREATE DATABASE analytics;
