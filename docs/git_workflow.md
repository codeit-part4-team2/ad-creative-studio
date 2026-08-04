# GitHub PR 절차별 체크리스트

담당: 박재철 (초안) — 전원 숙지 필수

작업 브랜치(`feature/*`)의 변경분을 `main`(또는 `develop`)에 안전하게 합치는 표준 절차입니다.
PR은 결국 **다른 사람의 동의를 받는 과정**이므로, 코드와 PR 설명을 항상 남이 이해하기 쉽게 정돈해주세요.

흐름: **feature 브랜치 생성 → 커밋 → PR 제출 → 리뷰/논의 → main으로 merge**

> 📖 공식 가이드: [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow)

---

## 1단계. 로컬에서 최신화 & 충돌 해결

> 충돌은 **main을 내 브랜치로 merge하는 순간** 드러납니다. "충돌 확인"은 merge 이후 단계라는 뜻입니다.
> **원칙: 내 작업과 기존 승인된 내역 사이의 충돌은 내가 해결한다. 리뷰어에게 떠넘기지 않는다.**

1. **자신의 작업물을 모두 commit**
   - ⚠️ 노트북(`.ipynb`)은 commit 전 **출력 셀이 제거**됐는지 확인 (`nbstripout`). 안 하면 CI의 `Notebook Sanity Check`가 실패합니다.
   ```bash
   git add -A
   git commit -m "작업 내용 요약"
   ```

2. **main(또는 develop) 브랜치를 최신 상태로 갱신**
   ```bash
   git checkout main
   git pull origin main
   git checkout -          # 내 작업 브랜치로 복귀
   ```

3. **main의 최신 내용을 내 브랜치로 merge** (PR 없이 로컬에서 가능)
   ```bash
   git merge main
   ```

4. **충돌(conflict)이 있으면 해결.** 없으면 다음 단계로.
   - 📖 [명령줄에서 충돌 해결하기](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/addressing-merge-conflicts/resolving-a-merge-conflict-using-the-command-line)

5. **push** (해야 GitHub 서버에 반영됨)
   ```bash
   git push origin <내-브랜치명>
   ```

---

## 2단계. PR 생성 (GitHub 웹)

6. 저장소 웹 페이지 → 상단 **Pull requests → New pull request**

7. **base = `main`**, **compare = 내 브랜치** 지정 후 PR 생성

8. PR 서식([템플릿](../.github/pull_request_template.md))에 **무엇을 했는지 / 어떻게 동작을 확인하는지** 기술하고,
   **Reviewers**에서 리뷰어를 수동 지정 후 제출
   - ℹ️ 지금은 수동 지정 — 나중에 `CODEOWNERS` 도입 시 자동 배정 예정
   - 📖 [Pull request 생성하기](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request)

9. 제출 후 **디스코드로 리뷰어에게 PR 요청 알림**

---

## 3단계. 리뷰 & 병합

10. 리뷰어가 PR 확인 후 필요한 부분에 **댓글로 피드백**

11. 작업자가 **내(작업) 브랜치에 수정 커밋을 push** — 같은 브랜치라 PR에 자동 반영됨

12. 작업자가 수정 사실을 리뷰어에게 알리고, 리뷰어는 확인 후 **Resolve conversation**

13. **승인(Approve) + CI 통과** 확인 후 작업자가 **Merge**
    - branch protection상 *승인 1개 이상 + CI 통과* 전에는 Merge 버튼이 비활성화됩니다
    - ✅ 병합 방식은 **Squash and merge** 권장 — 노트북 실험 커밋 여러 개가 main 히스토리를 오염시키지 않도록
    - 🧹 병합 후 **해당 브랜치 삭제**(Delete branch)
    - 📖 [Pull request 병합하기](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request)

---

## 한눈 요약

| 단계 | 위치 | 핵심 |
|---|---|---|
| 1 | 로컬 | commit → main 최신화 → merge → 충돌 해결 → push |
| 2 | 웹 | New PR → base=main/compare=내 브랜치 → 서식+리뷰어 → 제출 → 디스코드 알림 |
| 3 | 웹 | 리뷰 피드백 → 수정 push(자동 반영) → 승인+CI → **Squash merge** → 브랜치 삭제 |

---

## GitHub 설정 규칙 (branch protection)

아래는 **인프라 담당(김재헌) 또는 팀장(안은남)이 세팅**해야 하는 항목입니다. `Settings → Branches → Add branch ruleset`:

- Branch name pattern: `main`
- ✅ Require a pull request before merging
- ✅ Require approvals — 최소 1개
- ✅ Require status checks to pass — `.github/workflows/test.yml`의 `pytest` job (Notebook Sanity Check 포함) 필수로 지정
- ✅ Require conversation resolution before merging
- Bypass 목록에 팀장(안은남) 추가 — 환경변수 세팅, 긴급 변경사항 반영용
