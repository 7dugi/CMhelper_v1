# CMhelper Project Guidelines (Master AI Directives)

## Project Goal & Target Audience
- **Target:** B2B SaaS (Software as a Service) subscription model for New Car Salespeople (Car Managers).
- **Core Value:** Stability, reliability, and error resilience are the most critical factors. Users will pay for a seamless, fully automated experience without unexpected crashes or manual interventions.

## AI Forbidden Rules (AI 절대 금지 행동)
1. **No Guessing Refactoring:** 작동하는 코드를 추측으로 리팩토링하지 말 것.
2. **No Unapproved Structural Changes:** 사용자 승인 없이 기존 구조를 대규모 변경하지 말 것.
3. **No Undocumented Structures:** 문서와 다른 구조를 임의로 생성하지 말 것.
4. **No Environment Variable Leakage:** 환경변수(`.env`)를 콘솔에 직접 출력하거나 로그로 남기지 말 것.
5. **No Optimization that Breaks Features:** 작동 중인 기능을 최적화 명목으로 임의 변경하지 말 것.
6. **No Code Omission:** 코드를 제어하거나 제안할 때 가독성을 이유로 `// 기존 코드 동일` 등으로 생략하지 말 것. 파일 수정 시 전체 코드를 온전하게 출력하라.
7. **No Unapproved Dependency Upgrades:** 사용자의 명시적 승인 없이 `pip install --upgrade` 등으로 라이브러리 버전을 올리지 마라.

## Technical Requirements (B2B Level Stability)
1. **Never use blind coordinate clicks (Blind State Automation)**. Always use dynamic methods (UIAutomation / pywinauto) to locate elements. OpenCV is a fallback.
2. **OpenCV Environment Standardization:** When using OpenCV, assume Windows Display Scaling (DPI) 100%. Lower matching thresholds (e.g., 0.8) to account for Dark Mode or resolution differences.
3. **State Validation (Cross-checking):** Never assume a macro action succeeded. For example, if pasting text, read the clipboard or input box back to verify it was written correctly. 
4. **Timeout & Max Retry Policy:** 모든 상태 검증 및 요소 대기(Wait)에는 반드시 최대 대기 시간(Timeout, 예: 5초)과 최대 재시도 횟수(Max Retry, 예: 3회)를 명시하라. 이를 초과하면 무한 대기하지 말고 예외(Exception)를 상위 프로세스로 던져라.
5. **Clipboard Conflict Prevention:** 클립보드(pyperclip)를 사용할 때는 OS 충돌 방지를 위해 복사/붙여넣기 전후로 미세한 지연 시간(`time.sleep(0.1)`)을 부여하고, UI 검증으로 더블 체크하라.
6. **Kakao Automation Safety:** 
   - 한 번의 실패로 전체 발송을 중단하지 않는다. 실패 고객은 Retry Queue에 넣는다.
   - 발송 결과는 SUCCESS, FAILED, SKIPPED 로 구분한다.
   - 현재 고객과 다음 고객의 컨텍스트(이름, 메시지)가 절대 섞이지 않도록 격리한다.
7. **Resilience to Popups:** Anticipate unexpected popups (like KakaoTalk image send prompts) and always handle them safely.

## Log & Privacy Policy (보안 및 로그 정책)
- **Allowed to Log:** 발송 성공, 발송 실패, 시스템 에러 코드.
- **Forbidden to Log:** 고객의 전체 전화번호, 전체 이름, 주고받은 메시지 전문, 개인정보 원문(PII). 임시 데이터는 즉시 폐기하라.
- **Test Data Rule:** 테스트 코드 작성 및 실행 시에는 무조건 가짜 데이터(예: 홍길동, 010-0000-0000)만 사용하며, 실제 운영 데이터는 단 1건도 테스트에 유입시키지 않는다.
- **Code Protection:** Ensure proprietary macro logic (source code) is designed to avoid exposure of sensitive automation strategies. 

## Testing Policy & Definition of Done
- 기능 추가 시 반드시 1) 정상 시나리오 2) 실패 시나리오 3) 예외 시나리오 3가지를 모두 테스트한다. ("실행해보면 될 것 같다"는 기준 미달)
- [ ] 코드 작성 완료 및 3가지 시나리오 테스트/예외 처리 완료
- [ ] 로컬 테스트 및 빌드(PyInstaller) 성공 확인
- [ ] 개인정보 로깅 없음 확인
- [ ] 문서(`CURRENT_STATUS.md`, `CHANGELOG.md`, `RELEASE.md`) 업데이트 완료
- [ ] Git 커밋 완료

## Incident Severity (장애 등급)
- **P1:** 서비스 전체 중단 (즉시 롤백 권장)
- **P2:** 핵심 기능 장애
- **P3:** 일부 기능 오류
- **P4:** 단순 UI/UX 문제

When writing or modifying code for this project, always prioritize these guidelines over quick hacks.

## Third-party Dependency Policy

카카오톡 등 외부 애플리케이션에 대한 의존성 리스크를 항상 고려한다.

- UI 식별자는 중앙 관리(Remote Config)를 우선한다.
- 카나리아 테스트를 통해 업데이트 영향을 조기 탐지한다.
- UIA 실패 시 Fallback 경로(OpenCV)를 유지한다.
- Agent Auto Update 체계를 유지한다.
