# Future Billing Architecture

This document outlines the architectural direction for future CMhelper SaaS billing and plan enforcement.

## Core Principle: Decoupling Plans from Application Logic

**DO NOT hardcode plan names in the application business logic.**

Bad Example:
```python
if company.plan == "PRO":
    allow_marketing()
```

Instead, the architecture separates responsibilities into three distinct layers:
1. **RBAC (Role-Based Access Control)**
2. **Feature Entitlements**
3. **Usage Quotas**

A "Plan" (e.g., FREE, PRO, BUSINESS) is merely a template or a bundle of Entitlements and Quotas assigned to a Company.

---

## 1. RBAC (Role-Based Access Control)

RBAC answers the question:
> *"What can this user do within their organization?"*

This is based on the user's role, independent of the company's billing plan.

- **OWNER**: Full administrative control over the company workspace, user management, and company-wide data access.
- **USER**: Limited access, typically restricted to their own assigned data and basic operations.

---

## 2. Feature Entitlements

Entitlements answer the question:
> *"Is this company allowed to use this specific feature?"*

Application logic should check for specific feature flags rather than plan names.

Examples of Entitlements:
- `basic_crm`: bool
- `excel_upload`: bool
- `kakao_messaging`: bool
- `marketing`: bool
- `inventory_alerts`: bool
- `advanced_reporting`: bool

Future Code Example:
```python
if not has_feature(company, "marketing"):
    raise PermissionDenied("Marketing features are not included in your current plan.")
```

---

## 3. Usage Quotas

Quotas answer the question:
> *"How much of this feature is this company allowed to use?"*

Quotas enforce numerical limits on specific resources over a given period (e.g., monthly).

Examples of Quotas:
- `kakao_messages_per_month`: int
- `customer_limit`: int
- `user_limit`: int

Future Code Example:
```python
if not check_quota(company, "kakao_messages_per_month", increment=1):
    raise QuotaExceeded("Monthly Kakao message limit reached.")
```

---

## Plan Examples (Conceptual)

These are illustrative examples of how plans map to entitlements and quotas. **These are not actual product policies and are subject to change.**

### FREE Plan
- `basic_crm` = true
- `kakao_messaging` = true
- `kakao_messages_per_month` = 100
- `marketing` = false

### PRO Plan
- `basic_crm` = true
- `kakao_messaging` = true
- `kakao_messages_per_month` = 1000
- `marketing` = true
- `inventory_alerts` = false

### BUSINESS Plan
- `basic_crm` = true
- `kakao_messaging` = true
- `kakao_messages_per_month` = 5000
- `marketing` = true
- `inventory_alerts` = true
- `advanced_reporting` = true

## Future Implementation Notes

- **Database**: A `subscriptions` or `company_limits` table will need to be introduced to store the active entitlements and quotas for each `company_id`.
- **Middleware**: A centralized dependency or middleware should be responsible for fetching and evaluating these limits during API requests.
- **Current Phase**: In the current phase, no billing enforcement, payment gateway integration, or schema migration is implemented. This document serves solely as the architectural blueprint for future development.
