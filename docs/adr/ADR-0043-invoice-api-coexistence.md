# ADR-0043: 운영 서버에서 세금계산서 웹DB(invoice-api)와 공존

- 상태: 채택 (2026-10-15)
- 결정자: 마스터

## 배경

세금계산서 웹DB API(invoice-api)는 별도 레포·별도 스택이지만 ICFR 운영 서버와 도메인을 함께 쓴다.
공개 경로는 `https://icfr.synap.co.kr/invoice-api/` 이다.

## 결정

1. `/invoice-api/` 경로는 invoice-api 스택이 쓴다. ICFR 쪽은 `infra/nginx/icfr.conf` 443 블록의
   `include /etc/nginx/invoice-api/location*.conf;` 한 줄만 갖는다. 글롭이라 파일이 없으면 아무 일도 하지 않는다.
2. invoice-api 의 컨테이너(compose 프로젝트 `invoice-api`), 설정(`/etc/invoice-api`, `/etc/nginx/invoice-api`,
   `/etc/nginx/conf.d/invoice-api-zone.conf`), 데이터(`/data/invoice-api`)는 ICFR 작업에서 수정·삭제하지 않는다.
   반대 방향도 같다.
3. ICFR `deploy.yml` 은 `docker compose -f docker-compose.prod.yml up -d` 만 하고 `--remove-orphans`·`down` 을
   쓰지 않는다. 이 성질을 유지한다. ICFR 은 `-p` 를 지정하지 않아 compose 프로젝트 이름이 러너 작업 디렉터리에서
   정해지지만, 프로젝트가 달라 invoice-api 컨테이너는 대상이 아니다.
4. 이미지 정리 단계는 `ghcr.io/jeremydev99/claude-icfr/*` 만 대상으로 한다. 공개 이미지(postgres 등)는
   invoice-api 와 공유하므로 지우지 않는다.

## 결과

- 서버 nginx 설정 갱신 후 `nginx -t` 와 reload 를 거친다. ICFR 의 `/`·`/api/` 동작은 바뀌지 않는다.
- invoice-api location 안에 `add_header` 를 두면 서버 블록의 보안 헤더가 상속되지 않는다 — invoice-api 쪽 책임.
