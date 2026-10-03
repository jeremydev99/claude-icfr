"""화면 일러스트 생성 — synapvideo(사내 AI 이미지) `POST /images` 로 `manifest.ts` 의 슬롯을 만든다.

**API 키는 이 파일이나 저장소에 두지 않는다**(CLAUDE.md §5, synapvideo 안내서 §8). 이 PC 의 Windows 자격 증명
관리자에서 읽는다:
    서비스 `icfr-image-api` / 사용자 `api_key`   (svk_… 키)
    서비스 `icfr-image-api` / 사용자 `base_url`  (https://video.synap.co.kr/api/v1)
교체: python -c "import keyring; keyring.set_password('icfr-image-api','api_key','<키>')"

synapvideo 규칙(GET /guide·/policy — 판이 바뀌면 다시 읽는다):
- 견적이 자동 승인 금액(policy.cost.autoApproveKrw) 이하면 만들자마자 생성된다. 넘으면 **이 스크립트는 승인하지 않고 멈춘다**
  — 사람이 금액을 보고 승인해야 한다(--approve 를 줄 때만 승인 호출).
- 요청자 이메일(user.email) 필수(정책 defaultRequester 가 비어 있음) — --email 또는 기본값.
- 모든 응답의 X-Guide-Version·X-Policy-Version 을 기억해 두었다가(~/.icfr/synapvideo_versions.json) 바뀌면 다시 읽고 알린다.

사용:
    python scripts/gen_illustrations.py --me                     # 연결·한도 확인
    python scripts/gen_illustrations.py                          # 없는 슬롯만
    python scripts/gen_illustrations.py login-hero --variants 3  # 지정 슬롯 후보 3장(_v1.._v3) → 골라 <slot>.webp 로
출력: frontend/src/assets/illustrations/<slot>.webp (긴 변 최대 1200px, 품질 86)
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path

import keyring
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "frontend" / "src" / "components" / "illustration" / "manifest.ts"
OUT = ROOT / "frontend" / "src" / "assets" / "illustrations"
STATE = Path.home() / ".icfr" / "synapvideo_versions.json"
SERVICE = "icfr-image-api"
DEFAULT_EMAIL = "ynjun@synapsoft.co.kr"
ASPECTS = {"portrait": "4:5", "landscape": "16:9", "wide": "21:9", "square": "1:1"}
MAX_EDGE = 1200

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class SynapVideo:
    def __init__(self) -> None:
        self.key = keyring.get_password(SERVICE, "api_key")
        self.base = (keyring.get_password(SERVICE, "base_url") or "").rstrip("/")
        if not self.key or not self.base:
            sys.exit("자격 증명 관리자에 icfr-image-api (api_key·base_url) 가 없습니다")
        self.h = {"Authorization": f"Bearer {self.key}"}
        self.versions = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
        self.policy: dict = {}

    def _check_versions(self, r: requests.Response) -> None:
        g, p = r.headers.get("X-Guide-Version"), r.headers.get("X-Policy-Version")
        changed = []
        STATE.parent.mkdir(parents=True, exist_ok=True)
        if g and g != self.versions.get("guide"):
            changed.append(f"안내서 {self.versions.get('guide')} → {g}")
            guide = requests.get(f"{self.base}/guide", headers=self.h, timeout=60).text
            (STATE.parent / "synapvideo_guide.md").write_text(guide, encoding="utf-8")
            self.versions["guide"] = g
        if p and p != self.versions.get("policy"):
            changed.append(f"원칙 {self.versions.get('policy')} → {p}")
            self.policy = requests.get(f"{self.base}/policy", headers=self.h, timeout=60).json()
            self.versions["policy"] = p
        if changed:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(self.versions), encoding="utf-8")
            print("· synapvideo 갱신 감지 —", ", ".join(changed), f"(최신 안내서: {STATE.parent / 'synapvideo_guide.md'})")

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        r = requests.request(method, self.base + path, json=body, headers=self.h, timeout=180)
        self._check_versions(r)
        j = r.json()
        if not r.ok:
            e = j.get("error", {})
            raise RuntimeError(f"{r.status_code} {e.get('code')}: {e.get('message')}")
        return j

    def load_policy(self) -> dict:
        if not self.policy:
            self.policy = self.call("GET", "/policy")
        return self.policy

    def download(self, url: str) -> bytes:
        r = requests.get(url, headers=self.h, timeout=120)
        r.raise_for_status()
        return r.content


def load_manifest() -> tuple[str, dict[str, dict]]:
    """manifest.ts 를 정규식으로 읽는다 — TS 를 실행하지 않고 문자열 리터럴만 뽑는다."""
    src = MANIFEST.read_text(encoding="utf-8")
    style_m = re.search(r"export const STYLE =\s*((?:'[^']*'\s*\+?\s*)+)", src)
    style = "".join(re.findall(r"'([^']*)'", style_m.group(1))) if style_m else ""
    slots = {}
    for m in re.finditer(r"'([a-z-]+)':\s*\{(.*?)\n  \},", src, re.S):
        body = m.group(2)
        aspect = re.search(r"aspect:\s*'(\w+)'", body).group(1)
        prompt = "".join(re.findall(r"'([^']*)'", body.split("prompt:", 1)[1]))
        slots[m.group(1)] = {"aspect": aspect, "prompt": prompt}
    return style, slots


def save_webp(raw: bytes, path: Path) -> int:
    im = Image.open(io.BytesIO(raw))
    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "WEBP", quality=86, method=6)
    return path.stat().st_size


def generate(sv: SynapVideo, name: str, prompts: list[str], aspect: str, email: str, approve: bool) -> list[bytes]:
    p = sv.call("POST", "/images", {"prompts": prompts, "aspect": aspect, "title": f"[ICFR] 화면 일러스트 {name}",
                                    "user": {"email": email}})
    pid = p["id"]
    auto = int(sv.load_policy()["cost"]["autoApproveKrw"])
    poll = int(sv.policy.get("behavior", {}).get("pollIntervalSec", 4))
    deadline = time.time() + 900
    while True:
        st = sv.call("GET", f"/projects/{pid}")
        quotes = st.get("pendingQuotes") or []
        if quotes:
            q = quotes[0]
            if int(q["totalKrw"]) > auto and not approve:
                raise RuntimeError(f"견적 {q['totalKrw']}원 > 자동 승인 {auto}원 — 사람 승인 필요(--approve, 프로젝트 {pid})")
            if approve:
                sv.call("POST", f"/quotes/{q['id']}/approve", {"user": {"email": email}, "expectedKrw": q["totalKrw"]})
        shots = (st.get("storyboard") or {}).get("shots") or []
        done = [s for s in shots if s.get("status") == "succeeded" and s.get("result")]
        failed = [s for s in shots if s.get("status") == "failed"]
        if shots and len(done) + len(failed) == len(shots) and st.get("stage") not in ("generating",):
            print(f"  프로젝트 {pid} · 비용 {st.get('cost', {}).get('spentKrw')}원 · 성공 {len(done)} 실패 {len(failed)}")
            return [sv.download(s["result"]["url"]) for s in done]
        if time.time() > deadline:
            raise RuntimeError(f"시간 초과(프로젝트 {pid}, stage={st.get('stage')})")
        time.sleep(poll)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slots", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--variants", type=int, default=1, help="슬롯당 후보 수(1~4)")
    ap.add_argument("--email", default=DEFAULT_EMAIL, help="요청자(비용 기록) 이메일")
    ap.add_argument("--approve", action="store_true", help="자동 승인 금액을 넘는 견적도 승인(사람이 금액을 확인한 뒤에만)")
    ap.add_argument("--me", action="store_true")
    a = ap.parse_args()
    sv = SynapVideo()
    if a.me:
        print(sv.call("GET", "/me"))
        pol = sv.load_policy()
        print("자동 승인", pol["cost"]["autoApproveKrw"], "· 이번 달 남은 금액", pol["usage"]["remainingThisMonthKrw"])
        return
    style, slots = load_manifest()
    targets = a.slots or [s for s in slots if a.all or not (OUT / f"{s}.webp").exists()]
    n = max(1, min(4, a.variants))
    for name in targets:
        spec = slots[name]
        try:
            imgs = generate(sv, name, [f"{style}. {spec['prompt']}"] * n, ASPECTS[spec["aspect"]], a.email, a.approve)
        except Exception as e:  # 한 슬롯 실패가 전체를 멈추지 않게
            print(f"ERR {name}: {e}")
            continue
        for i, raw in enumerate(imgs, start=1):
            out = OUT / (f"{name}.webp" if n == 1 else f"{name}_v{i}.webp")
            print(f"OK  {out.name}  {save_webp(raw, out) // 1024}KB")


if __name__ == "__main__":
    main()
