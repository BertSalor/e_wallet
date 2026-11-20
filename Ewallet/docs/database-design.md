# Database design
SQLite schema is in `backend/database/schema.sql`. Tables: users, user_profiles, accounts, categories, transactions, budgets, notes, password_vault, user_settings and notifications. User-owned records carry `user_id` foreign keys and are filtered by the authenticated session.
