"""
텔레그램 MTProto 세션 생성 스크립트

사용 흐름
---------
1. 가상환경 활성화 후 `pip install -r requirements.txt` 수행
2. `python tele_setup.py --config config.yml --profile <name>` 실행
3. 안내에 따라 `api_id`, `api_hash`, 전화번호, 채널 핸들 등을 입력
4. SMS 인증 코드(및 2FA 비밀번호)를 입력하면 세션 파일 생성 및 설정 자동 갱신
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

try:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
except ImportError as exc:  # pragma: no cover
    print(
        "Telethon 패키지를 찾을 수 없습니다. 먼저 다음 명령을 실행하세요:\n"
        "  pip install telethon\n",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


@dataclass
class TelegramProfile:
    api_id: int
    api_hash: str
    phone_number: str
    channel_identifier: str
    session_path: Path
    tg_cred_id: str  # 텔레그램 자격증명 ID (예: "1", "ONE", "MAIN")
    env_path: Optional[Path] = None


def normalize_tg_cred_id(tg_cred_id: str) -> str:
    """텔레그램 자격증명 ID를 환경변수에 사용 가능한 형태로 정규화."""
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", tg_cred_id.strip())
    cleaned = cleaned.strip("_")
    return cleaned.upper() or "1"


def load_config_profile(config_path: Optional[Path], profile_name: Optional[str]) -> dict[str, Any]:
    """`config.yml`에서 profile에 해당하는 텔레그램 설정을 반환합니다."""
    if not config_path:
        return {}

    if not config_path.exists():
        print(f"[WARN] config 파일을 찾을 수 없습니다: {config_path}", file=sys.stderr)
        return {}

    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    sources = config.get("telegram_sources") or []
    if not sources:
        return {}

    if profile_name:
        for src in sources:
            if str(src.get("name")) == profile_name:
                return src
        print(f"[WARN] config.yml에서 profile '{profile_name}'을 찾을 수 없어 첫 번째 항목을 사용합니다.", file=sys.stderr)

    return sources[0]


def prompt_value(prompt: str, default: Optional[str] = None, secret: bool = False) -> str:
    """사용자로부터 값을 입력받습니다. 기본값이 있으면 안내에 표기합니다."""
    suffix = f" [{default}]" if default else ""
    message = f"{prompt}{suffix}: "
    while True:
        if secret:
            value = getpass(message)
        else:
            value = input(message).strip()

        if not value and default is not None:
            return default
        if value:
            return value
        print("값을 입력해주세요.")


def build_profile(args: argparse.Namespace, config_path: Optional[Path] = None) -> TelegramProfile:
    """환경 변수, config, 사용자 입력을 조합해 TelegramProfile을 완성합니다."""
    load_dotenv()  # .env 파일이 있으면 로드

    # config_path가 제공되지 않으면 args.config에서 생성
    if config_path is None and args.config:
        try:
            config_path = Path(args.config).resolve()
            if not config_path.exists():
                config_path = None
        except Exception:
            config_path = None
    
    config_profile = load_config_profile(config_path, args.profile)
    if not isinstance(config_profile, dict):
        config_profile = {}

    # 텔레그램 자격증명 ID 결정: config에서 가져오거나 사용자 입력
    tg_cred_id = config_profile.get("tg_cred_id")
    if not tg_cred_id:
        # 기존 자격증명이 있는지 확인 (환경변수에서)
        existing_creds = []
        for key in os.environ.keys():
            if key.startswith("TG_CRED_") and key.endswith("_API_ID"):
                cred_id = key.replace("TG_CRED_", "").replace("_API_ID", "")
                existing_creds.append(cred_id.lower())
        
        if existing_creds:
            print(f"[INFO] 기존 자격증명 발견: {', '.join(existing_creds)}")
            tg_cred_id = prompt_value(
                "설정에 저장할 자격증명 구분용 이름 (숫자 또는 이름, 예: 1, ONE, MAIN)",
                default=existing_creds[0] if len(existing_creds) == 1 else None,
            )
        else:
            tg_cred_id = prompt_value(
                "설정에 저장할 자격증명 구분용 이름 (숫자 또는 이름, 예: 1, ONE, MAIN)",
                default="1",
            )
    
    cred_slug = normalize_tg_cred_id(tg_cred_id)
    
    # 환경변수에서 자격증명 정보 로드 (TG_CRED_<ID>_* 형태만 사용)
    env_api_id = os.environ.get(f"TG_CRED_{cred_slug}_API_ID")
    env_api_hash = os.environ.get(f"TG_CRED_{cred_slug}_API_HASH")
    env_phone = os.environ.get(f"TG_CRED_{cred_slug}_PHONE")
    env_channel = config_profile.get("channel_id")
    session_dir = os.environ.get("TELEGRAM_SESSION_DIR", "secrets/telegram_sessions")

    # 환경변수에서만 로드 (config.yml에 직접 기입하지 않음)
    api_id_source = env_api_id
    api_hash = env_api_hash
    phone_number = env_phone
    channel_identifier = env_channel

    while True:
        api_id_input = prompt_value(
            "Telegram api_id",
            default=str(api_id_source) if api_id_source is not None else None,
        )
        try:
            api_id = int(api_id_input)
            break
        except ValueError:
            print("api_id는 정수여야 합니다.")

    api_hash = prompt_value("Telegram api_hash", default=api_hash)
    phone_number = prompt_value("전화번호(+국가코드 포함)", default=phone_number)
    channel_identifier = prompt_value(
        "수집할 채널/그룹 식별자(@handle 또는 초대 링크)",
        default=channel_identifier,
    )

    # .env 파일 경로 찾기: config.yml과 같은 디렉토리 또는 프로젝트 루트
    env_path = None
    if config_path and config_path.exists():
        env_path_candidate = config_path.parent / ".env"
        if env_path_candidate.exists():
            env_path = env_path_candidate
    
    # config_path가 없거나 .env를 찾지 못한 경우 프로젝트 루트에서 찾기
    if not env_path:
        project_root = Path.cwd()
        env_path_candidate = project_root / ".env"
        if env_path_candidate.exists():
            env_path = env_path_candidate
        else:
            # .env 파일이 없으면 프로젝트 루트에 생성할 경로 설정
            env_path = env_path_candidate

    # 세션 파일은 자격증명별로 하나만 생성
    if config_profile.get("session_file"):
        session_path = Path(str(config_profile["session_file"]))
    else:
        session_path = Path(session_dir) / f"tg_cred_{tg_cred_id.lower()}.session"

    session_path = session_path.expanduser().resolve()
    session_path.parent.mkdir(parents=True, exist_ok=True)

    return TelegramProfile(
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone_number,
        channel_identifier=channel_identifier,
        session_path=session_path,
        tg_cred_id=tg_cred_id,
        env_path=env_path,
    )


async def generate_session(profile: TelegramProfile) -> bool:
    """
    Telethon을 이용해 세션 파일을 생성하거나 갱신합니다.
    
    참고: Telethon 세션 파일은 일반적으로 만료되지 않습니다. 하지만 다음 경우 재인증이 필요할 수 있습니다:
    - 장기간(수개월~수년) 사용하지 않은 경우
    - Telegram 비밀번호를 변경한 경우
    - Telegram이 보안상의 이유로 세션을 무효화한 경우
    - 세션 파일이 손상된 경우
    
    Returns:
        bool: 세션이 이미 존재하고 인증되어 있으면 True, 새로 생성했으면 False
    """
    print(f"[INFO] 세션 파일 위치: {profile.session_path}")
    
    # 세션 파일이 이미 존재하는지 확인
    session_exists = profile.session_path.exists()
    if session_exists:
        print(f"[INFO] 세션 파일이 이미 존재합니다: {profile.session_path}")
    
    client = TelegramClient(str(profile.session_path), profile.api_id, profile.api_hash)

    async with client:
        try:
            # 세션 인증 상태 확인
            is_authorized = await client.is_user_authorized()
        except Exception as e:
            # 세션 파일이 손상되었거나 문제가 있는 경우
            print(f"[WARN] 세션 파일 확인 중 오류가 발생했습니다: {e}")
            print("[INFO] 세션 파일을 재생성합니다.")
            is_authorized = False
        
        if is_authorized:
            if session_exists:
                print("[INFO] 이미 인증된 세션입니다. 새로운 인증이 필요하지 않습니다.")
                print("[INFO] config.yml과 .env 파일만 업데이트합니다.")
            else:
                print("[INFO] 세션 파일이 생성되었고 인증이 완료되었습니다.")
            return True

        # 세션이 만료되었거나 인증되지 않은 경우 재인증
        if session_exists:
            print("[WARN] 세션 파일이 존재하지만 인증이 만료되었거나 무효화되었습니다.")
            print("[INFO] 재인증을 진행합니다.")
        
        print(f"[INFO] {profile.phone_number} 번호로 인증 코드를 전송합니다.")
        await client.send_code_request(profile.phone_number)
        code = prompt_value("수신한 5자리(또는 6자리) 코드").replace(" ", "")

        try:
            await client.sign_in(profile.phone_number, code)
        except SessionPasswordNeededError:
            password = getpass("2단계 인증 비밀번호를 입력하세요: ")
            await client.sign_in(password=password)

        print(f"[SUCCESS] 세션 생성/갱신 완료 → {profile.session_path}")
        print("        이제 MTProto 수집기를 실행하면 추가 인증 없이 메시지를 수집할 수 있습니다.")
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="텔레그램 MTProto 세션 생성 도우미")
    parser.add_argument(
        "--config",
        help="텔레그램 설정이 포함된 config.yml 경로 (예: config.yml)",
    )
    parser.add_argument(
        "--profile",
        help="config.yml 내부에서 사용할 텔레그램 소스 이름 (예: Crypto News Channel)",
    )
    return parser.parse_args()


def update_config_file(
    config_path: Optional[Path],
    original_profile: dict[str, Any],
    args: argparse.Namespace,
    profile: TelegramProfile,
) -> None:
    """세션 생성 후 config.yml을 최신 정보로 갱신합니다."""
    # config_path가 없으면 프로젝트 루트에서 config.yml 찾기
    if not config_path:
        project_root = Path.cwd()
        config_candidate = project_root / "config.yml"
        if config_candidate.exists():
            config_path = config_candidate
            print(f"[INFO] config.yml을 자동으로 찾았습니다: {config_path}")
        else:
            print("[WARN] config.yml 경로가 제공되지 않았고 프로젝트 루트에서도 찾을 수 없어 설정 파일 업데이트를 건너뜁니다.")
            print(f"[INFO] 다음 명령으로 config.yml 경로를 지정하세요: python tele_setup.py --config config.yml")
            return

    if not config_path.exists():
        print(f"[WARN] config 파일을 찾을 수 없어 생성할 수 없습니다: {config_path}")
        return

    try:
        with config_path.open("r", encoding="utf-8") as fh:
            config_data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        print(f"[ERROR] config 파일을 읽는 중 오류가 발생했습니다: {exc}", file=sys.stderr)
        return

    sources = config_data.get("telegram_sources")
    if sources is None:
        sources = []
        config_data["telegram_sources"] = sources

    target_index = None
    profile_name = args.profile or original_profile.get("name") or profile.channel_identifier
    
    # profile_name이 없으면 channel_identifier를 기본값으로 사용
    if not profile_name:
        profile_name = profile.channel_identifier
        print(f"[INFO] profile 이름이 제공되지 않아 채널 식별자를 사용합니다: {profile_name}")

    # 기존 항목 찾기: name 또는 channel_id로 매칭
    if profile_name:
        for idx, entry in enumerate(sources):
            entry_name = str(entry.get("name", ""))
            entry_channel = str(entry.get("channel_id", ""))
            if entry_name == profile_name or entry_channel == profile.channel_identifier:
                target_index = idx
                print(f"[INFO] 기존 항목을 찾았습니다: 인덱스 {idx}, 이름 '{entry_name}'")
                break

    # 기존 항목이 없으면 새 항목으로 추가
    if target_index is None:
        print(f"[INFO] 새로운 항목으로 추가합니다: {profile_name}")
        updated_entry = {}
        target_index = len(sources)  # 추가할 위치
    else:
        # 기존 항목 업데이트
        updated_entry = dict(sources[target_index])
        print(f"[INFO] 기존 항목을 업데이트합니다: 인덱스 {target_index}")

    # 항목 정보 업데이트
    updated_entry["name"] = profile_name
    updated_entry["auth_method"] = "mtproto"
    updated_entry["channel_id"] = profile.channel_identifier
    updated_entry["tg_cred_id"] = profile.tg_cred_id
    
    # 세션 파일 경로를 프로젝트 루트 기준 상대 경로로 변환
    try:
        project_root = config_path.parent.resolve()
        session_path_resolved = profile.session_path.resolve()
        try:
            session_file_relative = session_path_resolved.relative_to(project_root)
            updated_entry["session_file"] = str(session_file_relative).replace("\\", "/")  # Windows 경로 구분자 통일
        except ValueError:
            # 프로젝트 루트 외부에 있으면 절대 경로 사용 (경고 출력)
            print(f"[WARN] 세션 파일이 프로젝트 루트 외부에 있어 절대 경로를 사용합니다: {profile.session_path}")
            updated_entry["session_file"] = str(profile.session_path)
    except Exception as e:
        # 경로 변환 실패 시 절대 경로 사용
        print(f"[WARN] 세션 파일 경로 변환 실패: {e}, 절대 경로를 사용합니다.")
        updated_entry["session_file"] = str(profile.session_path)

    if target_index == len(sources):
        # 새 항목 추가
        sources.append(updated_entry)
    else:
        # 기존 항목 업데이트
        sources[target_index] = updated_entry

    try:
        with config_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(config_data, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)
        print(f"[INFO] config 파일이 업데이트되었습니다 → {config_path}")
        print(f"[INFO] 업데이트된 항목: name='{updated_entry.get('name')}', channel_id='{updated_entry.get('channel_id')}', tg_cred_id='{updated_entry.get('tg_cred_id')}'")
    except yaml.YAMLError as exc:
        print(f"[ERROR] config 파일을 저장하는 중 오류가 발생했습니다: {exc}", file=sys.stderr)
    except Exception as exc:
        print(f"[ERROR] config 파일 저장 중 예상치 못한 오류: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()


def update_env_file(profile: TelegramProfile) -> None:
    """필요한 경우 .env 파일에 텔레그램 자격증명 값을 기록하거나 안내한다."""
    cred_slug = normalize_tg_cred_id(profile.tg_cred_id)
    
    # env_path가 설정되지 않았으면 프로젝트 루트에 생성
    env_path = profile.env_path
    if not env_path:
        env_path = Path.cwd() / ".env"
    
    # .env 파일 읽기 (존재하지 않으면 빈 리스트)
    lines = []
    if env_path.exists():
        print(f"[INFO] .env 파일을 업데이트합니다 → {env_path}")
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        print(f"[INFO] .env 파일을 생성합니다 → {env_path}")
    
    # 기존 키-값 쌍 파싱
    kv_map: dict[str, str] = {}
    for line in lines:
        if line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        kv_map[key.strip()] = value.strip()

    def set_value(key: str, value: str) -> None:
        kv_map[key] = value

    # 자격증명 기반 환경변수 저장
    set_value(f"TG_CRED_{cred_slug}_API_ID", str(profile.api_id))
    set_value(f"TG_CRED_{cred_slug}_API_HASH", profile.api_hash)
    set_value(f"TG_CRED_{cred_slug}_PHONE", profile.phone_number)
    set_value("TELEGRAM_SESSION_DIR", str(profile.session_path.parent))

    # .env 파일 재구성
    output_lines = []
    existing_keys = set()
    
    # 기존 라인 처리 (주석과 빈 라인 유지)
    for line in lines:
        if line.strip().startswith("#") or "=" not in line:
            output_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in kv_map:
            output_lines.append(f"{key}={kv_map[key]}")
            existing_keys.add(key)
        else:
            output_lines.append(line)

    # 새로운 키-값 쌍 추가
    for key, value in kv_map.items():
        if key not in existing_keys:
            output_lines.append(f"{key}={value}")

    # 파일 저장
    env_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    print(f"[INFO] .env 파일 갱신 완료 (자격증명 ID: {profile.tg_cred_id})")


def main() -> None:
    args = parse_args()
    
    # config_path 처리: None이면 None으로 유지, 있으면 절대 경로로 변환
    config_path = None
    if args.config:
        try:
            config_path = Path(args.config).resolve()
            if not config_path.exists():
                print(f"[WARN] config 파일을 찾을 수 없습니다: {config_path}", file=sys.stderr)
                config_path = None
        except Exception as exc:
            print(f"[WARN] config 경로 처리 중 오류: {exc}", file=sys.stderr)
            config_path = None
    
    config_obj = load_config_profile(config_path, args.profile)
    if not isinstance(config_obj, dict):
        config_obj = {}
    profile = build_profile(args, config_path)

    try:
        session_already_exists = asyncio.run(generate_session(profile))
        
        # config.yml과 .env 파일 업데이트 (세션이 이미 있어도 설정 파일은 업데이트 필요)
        if session_already_exists:
            print("\n[INFO] 세션이 이미 존재하므로 설정 파일만 업데이트합니다.")
        
        update_config_file(
            config_path,
            config_obj,
            args,
            profile,
        )
        update_env_file(profile)
        
        if session_already_exists:
            print("\n[SUCCESS] 설정 파일 업데이트 완료!")
            print("        세션 파일이 이미 존재하므로 MTProto 수집기를 바로 사용할 수 있습니다.")
    except KeyboardInterrupt:
        print("\n[INFO] 작업이 취소되었습니다.")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[ERROR] 세션 생성 중 오류가 발생했습니다: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

