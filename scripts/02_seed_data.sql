-- EduTrack Seed Data
-- Run this AFTER 01_create_tables.sql

-- Sample Curriculum: Nigerian Biology (Grade 10)
INSERT INTO curricula (
    id,
    country,
    country_code,
    jurisdiction_level,
    grade,
    subject,
    status,
    confidence_score,
    source_url,
    source_authority
) VALUES (
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'Nigeria',
    'NG',
    'national',
    'SS1',  -- Senior Secondary 1
    'Biology',
    'active',
    0.95,
    'https://nerdc.gov.ng/curriculum',
    'Nigerian Educational Research and Development Council'
);

-- Competencies for Nigerian Biology SS1
INSERT INTO competencies (curriculum_id, title, description, order_index) VALUES
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 
 'Cell Division', 
 'Students will understand the processes of mitosis and meiosis, including the stages and significance of each type of cell division.',
 1),

('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 
 'Genetics and Heredity', 
 'Students will explain the principles of inheritance, including Mendelian genetics, dominant and recessive traits, and genetic variations.',
 2),

('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 
 'Ecology and Environment', 
 'Students will describe ecosystem components, food chains, energy flow, and the impact of human activities on the environment.',
 3),

('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 
 'Plant Biology', 
 'Students will identify plant structures and functions, including photosynthesis, respiration, and reproduction in flowering plants.',
 4),

('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 
 'Animal Biology', 
 'Students will explain animal classification, body systems, and physiological processes including digestion, circulation, and excretion.',
 5);

-- Sample Curriculum: Canadian Math (Grade 9)
INSERT INTO curricula (
    id,
    country,
    country_code,
    jurisdiction_level,
    jurisdiction_name,
    grade,
    subject,
    status,
    confidence_score,
    source_url,
    source_authority
) VALUES (
    'b2c3d4e5-f6a7-8901-bcde-f12345678901',
    'Canada',
    'CA',
    'state',
    'Ontario',
    '9',
    'Mathematics',
    'active',
    0.98,
    'https://www.dcp.edu.gov.on.ca/en/curriculum',
    'Ontario Ministry of Education'
);

-- Competencies for Ontario Math Grade 9
INSERT INTO competencies (curriculum_id, title, description, order_index) VALUES
('b2c3d4e5-f6a7-8901-bcde-f12345678901', 
 'Linear Relations', 
 'Students will represent linear relations graphically, algebraically, and numerically, and understand slope and y-intercept concepts.',
 1),

('b2c3d4e5-f6a7-8901-bcde-f12345678901', 
 'Algebraic Expressions', 
 'Students will simplify, evaluate, and manipulate algebraic expressions including polynomials and solve linear equations.',
 2),

('b2c3d4e5-f6a7-8901-bcde-f12345678901', 
 'Geometry and Measurement', 
 'Students will solve problems involving perimeter, area, surface area, and volume of composite 2D and 3D shapes.',
 3);

-- Verify data
SELECT 'Curricula count: ' || COUNT(*) FROM curricula;
SELECT 'Competencies count: ' || COUNT(*) FROM competencies;
