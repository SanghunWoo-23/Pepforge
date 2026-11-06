# Pepforge V6.0.0 — Windows 통합 설치·빌드 및 Science Engine 가이드

## 실행 파일은 하나

Windows에서 **`INSTALL_BUILD_TOOLS_AND_BUILD.bat`**를 실행하면 메뉴가 표시됩니다.

| 선택 | 수행 작업 | 준비물 |
| --- | --- | --- |
| 1 기본 빌드 | 별도 `.build_venv`에 빌드 도구 설치 → PyInstaller EXE → Inno Setup 설치 파일 | Windows 10/11, Python 3.11/3.12 권장, 네트워크, Inno Setup(없으면 winget 설치 시도) |
| 2 통합 구성 | **1번을 완료한 뒤** WSL2에 Ubuntu/Miniforge가 없으면 설치 시도 → Science 설치·검사 | 1번 준비물 + 관리자 승인/재부팅/최초 Ubuntu 사용자 설정이 필요할 수 있음 |
| 3 Science만 | Ubuntu/Miniforge 준비 및 WSL2 Science 엔진 설치·검증 | 인터넷, Windows 관리자 승인 및 재부팅이 필요할 수 있음 |
| 4 Science 검사 | **설치 없이** 기존 WSL2 환경의 OpenFE·OpenMM·OpenFF·PyMBAR 등 검사 | 기존 `pepforge-science` 환경 |
| 5 종료 | 아무 작업 없이 종료 | 없음 |

자동화/터미널:

```bat
INSTALL_BUILD_TOOLS_AND_BUILD.bat --build
INSTALL_BUILD_TOOLS_AND_BUILD.bat --all
INSTALL_BUILD_TOOLS_AND_BUILD.bat --science
INSTALL_BUILD_TOOLS_AND_BUILD.bat --verify-science
```

`--all`은 **Windows 빌드 성공 뒤 Science 설치에 실패하면 전체 성공으로 표시하지 않습니다.** `--build`는 과학 엔진을 설치하지 않습니다. 메뉴는 사용자 선택 없이는 다운로드/설치를 시작하지 않습니다.

## Ubuntu가 없는 PC에서도 시작하기 (NEW)

**Windows에서 `INSTALL_BUILD_TOOLS_AND_BUILD.bat`를 실행해 메뉴 2 또는 3을 선택하세요.**
Ubuntu가 설치되어 있지 않으면 자동으로 Microsoft 공식 명령 `wsl.exe --install -d Ubuntu`를 시도합니다.
이 동작은 **사용자가 Science 설치 메뉴를 선택한 경우에만** 실행하며, 관리자 권한이 없으면 Windows UAC 승인 창을 요청합니다. 메뉴 4(검사 전용)는 운영체제를 설치하지 않습니다.

1. WSL 자체가 없다면 Windows 관리자 권한이 필요합니다. 설치기가 **Windows UAC 관리자 승인 창을 자동 요청**합니다. 거절하거나 회사 관리 정책으로 거부되면 오류로 종료합니다. 대안으로 관리자 PowerShell에서 `wsl --install -d Ubuntu`를 실행할 수 있습니다. 사용자 승인 없이 권한을 우회하지 않습니다.
2. Windows의 가상화 기능을 활성화하는 과정에서 **재부팅이 필요할 수 있습니다.** 그런 경우 설치기는 완료를 가장하지 않고 중단합니다.
3. 처음 설치한 **Ubuntu를 시작하고 Linux 사용자명/비밀번호 생성**을 완료합니다.
4. 같은 `INSTALL_BUILD_TOOLS_AND_BUILD.bat`를 재실행하고 **3번 (Science only)**을 선택합니다. Ubuntu가 이미 있다면 해당 배포판을 사용합니다. 다른 Linux 배포판이 기본값이어도 **Ubuntu를 명시적으로 선택**합니다.
5. Ubuntu에 Miniforge가 없으면 **공식 배포 URL에서 SHA-256이 고정된 Miniforge를 설치**합니다. 사용자의 일반 Linux 홈 `~/miniforge3/`를 사용하며 글로벌 Windows Python을 바꾸지 않습니다.
6. `pepforge-science` Conda 환경을 만들거나 업데이트한 뒤 OpenFE·OpenMM·OpenFF·PyMBAR와 CLI를 검사합니다. 패키지 설치 실패 시 성공으로 표시하지 않습니다.

> 완전 무인으로 Windows 재부팅·관리자 승인·Ubuntu 최초 계정 생성을 처리할 수는 없습니다. 이 세 단계는 Windows/Ubuntu 보안 절차입니다. WSL2가 준비된 후의 Miniforge 및 Science 패키지 설치는 자동화되어 있습니다.

명령 예시:

```bat
INSTALL_BUILD_TOOLS_AND_BUILD.bat --science
INSTALL_BUILD_TOOLS_AND_BUILD.bat --verify-science
```

**Windows에서 직접 Science Python CLI를 호출할 때:**

```bat
python INSTALL_SCIENCE_ENGINES.py --via-wsl --install --bootstrap-wsl
```

Ubuntu 안에서 별도로 설치하려면:

```bash
python3 INSTALL_SCIENCE_ENGINES.py --install
python3 INSTALL_SCIENCE_ENGINES.py --verify-only
```

Miniforge 다운로드는 conda-forge 공식 릴리스 **26.7.2-1**을 사용하며, x86_64/aarch64 배포 파일의 SHA-256을 확인하고 일치할 때만 실행합니다. 인터넷 연결이 필요합니다. 해당 CPU 아키텍처에 대한 패키지 가용성은 Conda solver가 별도로 확인합니다.

## 설치 내용과 버전 정책

- Science Conda 환경: `pepforge-science` (Windows 빌드 환경 `.build_venv`와 분리)
- `openfe`, `openmm`, `openff-toolkit`, `openmmforcefields`, `ambertools`, `pymbar`, `rdkit`, `mdanalysis` (conda-forge)
- OpenFE가 지원하지 않는 OpenMM 8.3.0은 solver 사양에서 제외. 다른 버전은 OpenFE 및 conda-forge의 현재 호환 관계에 따라 선택합니다.
- 이미 `pepforge-science` 환경이 있으면 **create 대신 install/update** 실행. 마지막에는 Python 모듈 import, OpenFE CLI 존재와 OpenMM 플랫폼 목록을 검사합니다.
- 로그: 실행 폴더의 `SCIENCE_ENGINE_INSTALL.log`, 보고서: `SCIENCE_ENGINE_INSTALL_REPORT.json` (Git 제외 대상).

Ubuntu/Linux 터미널에서 직접 실행할 경우 아래 명령을 사용할 수 있습니다. 이 Python 파일은 **내부 엔진**이며 Windows에서 별도 Science BAT를 실행할 필요가 없습니다.

```bash
python3 INSTALL_SCIENCE_ENGINES.py                 # 설치 계획만 보기
python3 INSTALL_SCIENCE_ENGINES.py --install       # 설치 및 검사
python3 INSTALL_SCIENCE_ENGINES.py --verify-only   # 기존 환경 검사
```

설치 이후 연구 CLI를 직접 사용하려면 Ubuntu 셸에서 `micromamba activate pepforge-science` 또는 `conda activate pepforge-science`로 환경을 활성화하세요.

## 반드시 구분할 제한 사항

- **Windows EXE에 OpenFE가 포함되지는 않습니다.** Science 엔진은 WSL2의 독립 환경에 설치됩니다. Windows GUI ↔ WSL2 실행 자동 연결/전체 ABFE 파이프라인이 실측 완료된 것은 아닙니다.
- `VERIFIED`는 패키지 import 및 명령 사용 가능 여부의 검사입니다. 비천연 잔기 Force Field 파라미터 검증, 생산 MD의 충분한 샘플링, ABFE convergence, 실험 ΔG_bind 예측 정확도를 뜻하지 않습니다.
- GPU를 자동으로 사용한다고 가정하지 마세요. WSL2 CUDA 드라이버/장치 및 OpenMM 플랫폼을 별도로 확인해야 합니다. CPU 사용 가능 여부 역시 대상 컴퓨터에서 확인하세요.
- 오류가 발생한 경우 보고서의 `status`와 전체 로그를 확인하세요. 실패와 과학적 미검증을 성공으로 표시하지 않습니다.

참조: [OpenFE Installation](https://docs.openfree.energy/en/latest/installation.html) · [Pepforge README](README.md) · [README_KO](README_KO.md)
