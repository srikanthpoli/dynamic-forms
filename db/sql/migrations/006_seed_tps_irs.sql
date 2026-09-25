-- Demo TPS implementation requests for the first TPS workspace screen.
-- Run after 005_add_tps_ir_workflow.sql.
-- Format: YYYYMMDD_sequence, for example 20260924_101.

INSERT INTO tps_irmain (
    ir_number, customer_name, uen, first_name, last_name, tin, address,
    status, priority, onboarding_type, risk_rating, notes
)
VALUES
(
    '20260924_101', 'Northstar Trading Pte Ltd', '201912345K', 'Alicia', 'Tan',
    'T1234567A', '12 Marina View, Singapore', 'active', 'high',
    'Commercial onboarding', 'medium', 'Initial commercial account setup.'
),
(
    '20260924_102', 'BluePeak Logistics Pte Ltd', '202045678M', 'Daniel', 'Lim',
    'S7654321B', '80 Robinson Road, Singapore', 'draft', 'normal',
    'Commercial onboarding', 'low', 'Awaiting client information.'
),
(
    '20260924_103', 'Evergreen Manufacturing Ltd', '199801234Z', 'Michelle', 'Wong',
    'F2468135N', '1 Jurong Pier Road, Singapore', 'submitted', 'normal',
    'Periodic review', 'high', 'Submitted for relationship manager review.'
)
ON CONFLICT (ir_number) DO NOTHING;
