# CMhelper Development Harness V1

## 1. 목적
여러 AI Agent가 CMhelper를 안전하게 개발할 수 있도록 돕는 기반 구조(Harness)입니다.

## 2. Architecture
USER -> Codex Remote -> ORCHESTRATOR -> Agents (Senior, Implementer, Designer) -> Adapters

## 3. Source of Truth
CMhelper의 장기적인 기준은 Git Repository입니다. `governance.py`를 통해 명시적인 문서를 로드하여 검증합니다.

## 4. Agent Roles & Implementer Tool Boundary
- **Senior Agent**: 계획 수립 및 리뷰
- **Implementer Agent**: 실제 코드 구현
- **Designer Agent**: 향후 UI/UX 설계 확장

### Implementer Tool Boundary
1. Implementer는 trusted workspace 내부 파일을 built-in file tools로 읽고 수정합니다.
2. Implementer는 shell/git/rg/pytest/npm/MCP/Vercel을 직접 실행하지 않습니다.
3. Git/Test/Build Evidence는 Harness `EvidenceExecutor`가 수집합니다.
4. AI-generated arbitrary command는 실행하지 않습니다.
5. Codex Senior가 승인한 Mutation Scope(`allowed_mutation_paths`) 밖의 파일 변경은 허용하지 않습니다.
6. Codex Review + Validation + PassGate가 모두 PASS한 뒤 `READY_TO_COMMIT` 상태가 됩니다.
7. 실제 Commit/Push는 User Approval 이후 단계입니다.

## 5. Provider Adapter 구조
특정 모델과 강결합을 피하기 위해 Adapter 패턴을 사용합니다. (Codex, Antigravity 등)
Adapter는 각 CLI의 샌드박스 정책(read-only, 프로젝트 루트 강제)을 통제합니다.

## 6. H1 IMPLEMENTED (Executable Skeleton)
현재 H1은 다음을 구조적으로 구현(Skeleton)했습니다:
- Governance 문서 로딩 및 Traversal 차단 (governance.py)
- TaskState 기반 State Machine 및 허용 변이 규칙 제어 (state_machine.py)
- Evidence 기반 데이터 구조 모델링 (models.py)
- Review Loop Guard (no-progress, oscillation, autonomous limit) 구조화 (orchestrator.py)
- Risk Gate 분류 로직 및 Approval 연동 구조 (approval.py)
- Pass Gate 검증 (orchestrator.py)
- CLI 안전 옵션을 강제하는 Command Builder (codex_adapter.py, antigravity_adapter.py)
- JSON 기반 Audit Logger 뼈대 (audit_logger.py)
- Provider Factory를 통한 동적 교체 기반 (factory.py)
- Agent Prompt 문서화 규칙 마련 (prompts/*.md)

## 7. H2 PLANNED (NOT ENABLED IN H1)
다음 항목들은 아직 **실제 실행되지 않으며(NOT ENABLED)**, H2에서 구현될 예정입니다:
- **Actual AI execution**: AI 서브프로세스의 자동 실행(Subprocess/MCP) 미작동. (현재는 DRY_RUN=True)
- **Discord network calls**: Webhook 네트워크 전송 미작동.
- **Vercel deployment**: 실제 Preview 배포 호출 미작동.
- **Browser QA execution**: 브라우저 자동화 실행 스크립트 미작동.
- **Supabase write**: MCP를 통한 자동 쓰기 미지원 (문서상 read-only 강제).
- **Git commit automation**: 커밋 자동화 미작동.

## 8. 롤아웃 및 안전장치
모든 Adapter는 `DRY_RUN=True` 설정에서 외부 연동을 억제하며, 루프에 빠지더라도 `MAX_AUTONOMOUS_REVIEW_ITERATIONS` 제한에 따라 사용자 결정 모드로 진입합니다.

## 9. 참고 사항
- 본 문서는 CMhelper 개발 하네스의 기본 구조 및 안전 실행 가이드라인을 정의합니다.

