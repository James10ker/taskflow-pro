-- Demo-only accounts kept compatible with the upstream README.
-- Passwords are stored as BCrypt hashes, never as plaintext.
INSERT INTO users (email, password_hash, display_name, role, avatar_color)
VALUES ('admin@taskflow.pro', '$2b$10$ujSVsZzsNcL8IAyMgCO.LOFpEpJ/aNbRTN1L.psRoZmWP0rTtKoD.', 'Amina Hassan', 'admin', '#7c3aed');

INSERT INTO users (email, password_hash, display_name, role, avatar_color)
VALUES ('member@taskflow.pro', '$2b$10$2gvhk/rg9ZCaRFCeGj9OVekiHYnmxdE19sspgezOS8V.0wO.u0cya', 'Omar Saeed', 'member', '#0ea5e9');
