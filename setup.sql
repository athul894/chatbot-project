-- Run this ONCE in MySQL to create the database
-- Then visit http://localhost:5000/init-db to populate tables

CREATE DATABASE IF NOT EXISTS chatbot_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE chatbot_db;

-- Tables are auto-created by database.py init_db()
-- Just run this file to create the database, then hit /init-db

-- If you want to manually reset everything:
-- DROP TABLE IF EXISTS conversation_log, pending_queries, patterns, intents, course_fees;