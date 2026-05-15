# Prompts 폴더

이 폴더는 Claude Code 실행용 작업 명령 파일을 보관합니다.

## 명명 규칙

`{프로젝트}_{개발분야}_{번호}_{YYYYMMDD}.md`

예: `ICFR_setup_1_20260515.md`, `ICFR_backend_1_20260601.md`

## 사용 방법

claude.ai에서 토론된 결과를 담은 작업 명령 파일을 이 폴더에 두고,
Claude Code에 다음과 같이 호출합니다:

```
prompts/ICFR_setup_1_20260515.md 대로 작업해줘
```

자세한 운영 규칙은 레포 루트의 `CLAUDE.md` 섹션 7 참조.
