"""화면 일러스트 생성 — `frontend/src/components/illustration/manifest.ts` 의 슬롯·프롬프트로 이미지를 만든다.

**API 키는 이 파일이나 저장소에 두지 않는다**(CLAUDE.md §5). 이 PC 의 Windows 자격 증명 관리자에서 읽는다:
    서비스 `icfr-image-api` / 사용자 `api_key`   (키)
    서비스 `icfr-image-api` / 사용자 `base_url`  (게이트웨이 주소 — 비밀은 아니지만 키와 함께 둔다)
등록·교체는 python -c "import keyring; keyring.set_password('icfr-image-api','api_key','<키>')" 로 한다.

호출 형식은 OpenAI 호환 이미지 API(`POST {base_url}/images/generations`, 응답 `data[0].b64_json` 또는 `url`)를
기본으로 한다. 게이트웨이 형식이 다르면 `call_api()` 만 고친다.

사용:
    python scripts/gen_illustrations.py                 # 없는 슬롯만 생성
    python scripts/gen_illustrations.py login-hero      # 지정 슬롯만(덮어쓰기)
    python scripts/gen_illustrations.py --all --variants 2   # 전부, 슬롯당 후보 2장(_v1, _v2 로 저장 → 골라서 이름 변경)
출력: frontend/src/assets/illustrations/<slot>.webp (긴 변 최대 1200px, 품질 86)
"""
from __future__ import annotations

import argparse
import base64
import io
import re
import sys
from pathlib import Path

import keyring
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "frontend" / "src" / "components" / "illustration" / "manifest.ts"
OUT = ROOT / "frontend" / "src" / "assets" / "illustrations"
SERVICE = "icfr-image-api"
SIZES = {"portrait": "1024x1536", "landscape": "1536x1024", "wide": "1536x1024", "square": "1024x1024"}
MAX_EDGE = 1200


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


def creds() -> tuple[str, str]:
    key = keyring.get_password(SERVICE, "api_key")
    base = keyring.get_password(SERVICE, "base_url")
    if not key:
        sys.exit("API 키가 자격 증명 관리자에 없습니다 (icfr-image-api / api_key)")
    if not base:
        sys.exit("게이트웨이 주소가 없습니다 — keyring.set_password('icfr-image-api','base_url','https://…/v1')")
    return key, base.rstrip("/")


def call_api(key: str, base: str, prompt: str, size: str, model: str | None) -> bytes:
    body = {"prompt": prompt, "size": size, "n": 1}
    if model:
        body["model"] = model
    r = requests.post(f"{base}/images/generations", json=body, timeout=300,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    d = r.json()["data"][0]
    if d.get("b64_json"):
        return base64.b64decode(d["b64_json"])
    return requests.get(d["url"], timeout=120).content


def save_webp(raw: bytes, path: Path) -> int:
    im = Image.open(io.BytesIO(raw))
    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "WEBP", quality=86, method=6)
    return path.stat().st_size


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slots", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--variants", type=int, default=1)
    ap.add_argument("--model", default=None)
    a = ap.parse_args()
    style, slots = load_manifest()
    key, base = creds()
    targets = a.slots or [s for s in slots if a.all or not (OUT / f"{s}.webp").exists()]
    for name in targets:
        spec = slots[name]
        prompt = f"{style}. {spec['prompt']}"
        for v in range(1, a.variants + 1):
            out = OUT / (f"{name}.webp" if a.variants == 1 else f"{name}_v{v}.webp")
            try:
                size = save_webp(call_api(key, base, prompt, SIZES[spec["aspect"]], a.model), out)
                print(f"OK  {out.name}  {size // 1024}KB")
            except Exception as e:  # 한 장 실패가 전체를 멈추지 않게
                print(f"ERR {name} v{v}: {e}")


if __name__ == "__main__":
    main()
