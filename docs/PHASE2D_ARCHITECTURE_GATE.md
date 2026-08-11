# Phase 2D Architecture Gate: Contract Read Path Migration

This document outlines the architectural decisions and constraints for the upcoming Phase 2D, which involves moving the Frontend/API read paths from the legacy Customer fields to the new Contract entity.

## 1. Customer List View
- **Constraint:** The overall `contracts` array MUST NOT be included or fully loaded for each customer in the list view to prevent N+1 query performance issues and payload bloating.
- **Future Design:** If contract data is needed in the list view, it should be designed as a separate aggregate/summary projection (e.g., `contract_count`, `latest_contract`, `nearest_expiry`).

## 2. Customer Detail View
- **Constraint:** The Customer Detail view is the appropriate place to fetch and display the full list of contracts associated with a specific customer.
- **Action:** Update the detail API endpoint and frontend components to fetch and render the `contracts` array.

## 3. Expiry Dashboard
- **Constraint:** The current Expiry Dashboard relies on legacy fields.
- **Future Design:** It must transition to querying the `contracts` table and its `expiry_date` index instead of the `customers` table.

## 4. Legacy Field Retention (Phase 2D/E)
- **Constraint:** Legacy contract fields in the `customers` table MUST NOT be deleted during Phase 2D.
- **Action:** These fields will remain for logical rollback capabilities and will only be safely dropped in a later phase (Phase 2E) after the new read paths have been stabilized and proven in production.

## 5. Follow-Up Production Maintenance
- **Constraint:** Production is currently missing indexes for `company_id`, `customer_id`, and `assigned_user_id` on the `contracts` table.
- **Action:** Evaluate and schedule a small maintenance migration to create these indexes before Phase 2D read paths hit production to ensure optimal query performance for the new Contract views.
