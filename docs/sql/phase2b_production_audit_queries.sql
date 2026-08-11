-- ==============================================================================
-- PHASE 2B: PRODUCTION SUPABASE READ-ONLY AUDIT QUERIES
-- ==============================================================================
-- 
-- 본 쿼리들은 Production Supabase SQL Editor에서 실행하여
-- Customer-Contract 1:N 마이그레이션을 위한 사전 검증 데이터를 수집하기 위해 작성되었습니다.
-- 모든 쿼리는 READ-ONLY(SELECT)이며, Production 데이터를 수정하지 않습니다.
-- 
-- 실행 후 결과를 복사하여 제공해주시면 PHASE 2B 검증을 완료할 수 있습니다.
-- ==============================================================================

-- 1. Total Customer count
SELECT 'Total Customers' AS metric, COUNT(*) AS count FROM customers;

-- 2. company_id별 customer count
SELECT 'By Company' AS metric, company_id, COUNT(*) AS count FROM customers GROUP BY company_id;

-- 3. assigned_user_id별 customer count
SELECT 'By Assigned User' AS metric, assigned_user_id, COUNT(*) AS count FROM customers GROUP BY assigned_user_id;

-- 4. Field별 non-null / non-empty count
SELECT 
    COUNT(*) FILTER (WHERE contract_car IS NOT NULL AND contract_car != '') AS contract_car_count,
    COUNT(*) FILTER (WHERE months IS NOT NULL) AS months_legacy_count,
    COUNT(*) FILTER (WHERE contract_date IS NOT NULL AND contract_date != '') AS contract_date_count,
    COUNT(*) FILTER (WHERE contract_months IS NOT NULL) AS contract_months_count,
    COUNT(*) FILTER (WHERE expiry_date IS NOT NULL AND expiry_date != '') AS expiry_date_count,
    COUNT(*) FILTER (WHERE capital IS NOT NULL AND capital != '') AS capital_count,
    COUNT(*) FILTER (WHERE product_type IS NOT NULL AND product_type != '') AS product_type_count,
    COUNT(*) FILTER (WHERE supplies_work IS NOT NULL AND supplies_work != '') AS supplies_work_count,
    COUNT(*) FILTER (WHERE dealer_info IS NOT NULL AND dealer_info != '') AS dealer_info_count,
    COUNT(*) FILTER (WHERE estimate_image IS NOT NULL AND estimate_image != '') AS estimate_image_count,
    COUNT(*) FILTER (WHERE sent_quotes IS NOT NULL AND sent_quotes::text != '[]' AND sent_quotes::text != 'null') AS sent_quotes_count
FROM customers;

-- 5. insurance_active 값 분포
SELECT 'insurance_active' AS metric, insurance_active, COUNT(*) AS count FROM customers GROUP BY insurance_active;

-- 6. ACTUAL SUPABASE DATA QUALITY AUDIT (Anomalies Count)
SELECT
    (SELECT COUNT(*) FROM customers WHERE company_id IS NULL) AS company_id_is_null,
    (SELECT COUNT(*) FROM customers WHERE assigned_user_id IS NULL) AS assigned_user_id_is_null,
    (SELECT COUNT(*) FROM customers c LEFT JOIN companies co ON c.company_id = co.id WHERE co.id IS NULL) AS invalid_company_fk,
    (SELECT COUNT(*) FROM customers c LEFT JOIN users u ON c.assigned_user_id = u.id WHERE u.id IS NULL) AS invalid_user_fk,
    (SELECT COUNT(*) FROM customers c JOIN users u ON c.assigned_user_id = u.id WHERE c.company_id != u.company_id) AS cross_tenant_mismatch,
    (SELECT COUNT(*) FROM customers WHERE contract_car IS NOT NULL AND contract_car != '' AND (contract_date IS NULL OR contract_date = '')) AS car_without_date,
    (SELECT COUNT(*) FROM customers WHERE contract_date IS NOT NULL AND contract_date != '' AND (contract_car IS NULL OR contract_car = '')) AS date_without_car,
    (SELECT COUNT(*) FROM customers WHERE contract_date IS NOT NULL AND contract_date != '' AND (contract_months IS NULL OR contract_months <= 0)) AS date_without_months,
    (SELECT COUNT(*) FROM customers WHERE contract_months IS NOT NULL AND contract_months > 0 AND (contract_date IS NULL OR contract_date = '')) AS months_without_date,
    (SELECT COUNT(*) FROM customers WHERE expiry_date IS NOT NULL AND expiry_date != '' AND (contract_date IS NULL OR contract_date = '')) AS expiry_without_date,
    (SELECT COUNT(*) FROM customers WHERE contract_date IS NOT NULL AND contract_date != '' AND expiry_date IS NOT NULL AND expiry_date != '' AND contract_date > expiry_date) AS date_greater_than_expiry,
    (SELECT COUNT(*) FROM customers WHERE contract_months <= 0) AS invalid_negative_months,
    (SELECT COUNT(*) FROM customers WHERE contract_months > 120) AS suspiciously_large_months;

-- 7. RE-CALCULATE BACKFILL ELIGIBILITY
-- Eligibility Rule: 의미 있는 계약 필드(car, date, months, expiry, capital, product_type) 중 하나라도 존재하는 고객
WITH eligible AS (
    SELECT id
    FROM customers
    WHERE (contract_car IS NOT NULL AND contract_car != '')
       OR (contract_date IS NOT NULL AND contract_date != '')
       OR (contract_months IS NOT NULL AND contract_months > 0)
       OR (expiry_date IS NOT NULL AND expiry_date != '')
       OR (capital IS NOT NULL AND capital != '')
       OR (product_type IS NOT NULL AND product_type != '')
)
SELECT 
    (SELECT COUNT(*) FROM customers) AS production_total_customers,
    (SELECT COUNT(*) FROM eligible) AS production_backfill_eligible,
    (SELECT COUNT(*) FROM customers) - (SELECT COUNT(*) FROM eligible) AS production_no_contract_data;

-- 8. EXPIRY LOGIC RE-VERIFY
-- Check if stored expiry_date matches (contract_date + contract_months) logic
-- (PostgreSQL DATE calculations)
SELECT 
    id,
    contract_date,
    contract_months,
    expiry_date AS stored_expiry_date,
    TO_CHAR((contract_date::DATE + (contract_months || ' months')::INTERVAL), 'YYYY-MM-DD') AS calculated_expiry_date
FROM customers
WHERE contract_date IS NOT NULL AND contract_date != ''
  AND contract_months IS NOT NULL AND contract_months > 0
  AND expiry_date != TO_CHAR((contract_date::DATE + (contract_months || ' months')::INTERVAL), 'YYYY-MM-DD')
LIMIT 10;
