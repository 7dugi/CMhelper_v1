# CMhelper 데이터 모델

## 1. 구현된 모델 [IMPLEMENTED]

- **FieldDefinition**
- **Customer**
- **Consultation**
- **MessageTask**
  - 구현된 필드: id, customer_id, message_text, image_url, status, created_at, scheduled_at
  - 구현된 상태값: pending, sent, failed

## 2. 향후 모델 [PLANNED] / [PROPOSED]

- **상태 머신**: PROCESSING, RECOVERY, RESERVED, CANCELLED
- **작업 관리 필드**: locked_by, heartbeat_at, retry_count, error_code
- **영업 관리**: Opportunity, SalesStageHistory, LossReason, Quote, Contract
- **콘텐츠 및 재고**: Template, Recipe, Vehicle, Product, Inventory
- **분석 및 확장**: ConsultationInsight, ContractAccess
