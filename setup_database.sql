-- AICC 프로젝트 MySQL 데이터베이스 설정 스크립트
-- 사용법: mysql -u root -p < setup_database.sql

-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS aicc_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 데이터베이스 사용
USE aicc_db;

-- 사용자 생성 (선택사항 - 보안을 위해 권장)
-- CREATE USER IF NOT EXISTS 'aicc_user'@'localhost' IDENTIFIED BY 'your_secure_password';
-- GRANT ALL PRIVILEGES ON aicc_db.* TO 'aicc_user'@'localhost';
-- FLUSH PRIVILEGES;

-- 테이블은 애플리케이션 시작 시 자동으로 생성됩니다.
-- (SQLAlchemy의 Base.metadata.create_all()에 의해)

-- 확인
SHOW DATABASES;
SELECT 'Database aicc_db created successfully!' AS Status;

