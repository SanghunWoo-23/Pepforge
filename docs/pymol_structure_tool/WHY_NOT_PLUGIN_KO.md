# 왜 PyMOL 플러그인이 아닌가?

초기에는 PyMOL 플러그인 형태도 고려했지만, 최종 v1.0.0에서는 독립형 builder + PyMOL PML 출력 방식으로 고정했다.

이유:

1. PyMOL 설치 상태와 버전에 덜 의존한다.
2. Colab/conda/CLI/batch 실행이 쉽다.
3. PyMOL이 없어도 SDF/PDB/JSON/report를 생성할 수 있다.
4. 결과 파일을 GitHub에 올리기 쉽다.
5. PyMOL은 구조 확인용 viewer로만 두는 편이 유지보수에 유리하다.

따라서 이 프로젝트는 PyMOL plugin이 아니라 **PyMOL-ready modified peptide structure builder**이다.
