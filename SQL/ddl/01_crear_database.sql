IF NOT EXISTS (
    SELECT 1
    FROM sys.databases
    WHERE name='GoldFiscal'
)
BEGIN
    CREATE DATABASE GoldFiscal;
END;