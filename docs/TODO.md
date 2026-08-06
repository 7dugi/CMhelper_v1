# 개발 로드맵 및 백로그 (TODO)

## P0: CRM + 카카오 발송 안정화
- [x] 수동 기반 카카오톡 예약 발송 처리 구현 (`main`)
- [ ] [FEATURE BRANCH ONLY] 에이전트 V4.1 로직(Heartbeat, Recovery, Retry) `main` 병합 검토
- [ ] [FEATURE BRANCH ONLY] 다중 Agent 스트레스 테스트 (Atomic Lock 동시성 검증)
- [ ] pytest 기반 단위 테스트 및 API 통합 테스트 코드 작성
- [ ] 카카오톡 버전별 호환성 테스트 및 DPI 125% / 150% 편차 검증

## P1: 운영 안정성 
- [ ] 카나리아 테스트(Canary Test) 자동화 파이프라인 구축
- [ ] Remote Config 기반 카카오톡 UI 식별자 백엔드 배포 연동
- [ ] Agent 버전 확인 및 Auto-Update 런처 기획

*참고: Agent 상시 실행 모드, Windows 시작 시 자동 실행, Windows Service 지원, 무인 예약 발송 기능은 현재 제품 범위에서 제외됨.*

## P2: Sales Funnel + Stage History + Loss Reason
- [ ] `Opportunity` 기반 영업 파이프라인 (Lead -> Quote -> Contract) 칸반 보드 개발
- [ ] 퍼널 전환율(Conversion Rate) 대시보드 개발
- [ ] Loss Reason (이탈 사유) 데이터화 및 집계 통계 뷰 개발
- [ ] 기존 `Customer` 단일 테이블 데이터 정규화 마이그레이션

## P3: Recipe / Template
- [ ] 업종/차종/고객군별 대응 가능한 템플릿(Template) 마스터 관리자 기능
- [ ] Best Practice 영업 로직을 담은 `SalesRecipe` 연결 기능
- [ ] 단일 고객에 대한 `OpportunityRecipeHistory` (템플릿 A/B 테스트 이력) 기능

## P4: Inventory / Product
- [ ] 렌터카사, 리스사 금융 상품(Product) 메타데이터 연동(또는 수동 관리 어드민)
- [ ] 실시간 재고(Inventory) 데이터 파싱 및 매핑
- [ ] 차종+재고+조건 매칭 통합 검색 뷰 개발

## P5: AI Insight
- [ ] 고객 상담 내용을 비식별 요약 메타데이터(`ConsultationInsight`)로 변환 파이프라인 개발
- [ ] 원문 데이터 보안 처리 및 즉시 폐기/격리 아키텍처 연동
- [ ] AI 기반 최적 상품 추천 어시스턴트 기능

## P6: Customer Portal
- [ ] 고객(계약자) 전용 웹 뷰(Contract Access) 독립 배포 환경 구축
- [ ] 만기 알림, 차량 반납/인수 잔존가치 시뮬레이션 프론트엔드
- [ ] 재계약 유도 다음 차량 추천 기능

## P7: 금융사/OEM용 Aggregated Analytics
- [ ] 식별 불가능한 거시적 집계 데이터(차종별 선호 업종, 금융상품 전환율 등)를 제조사/금융사용으로 제공하는 별도 어드민
