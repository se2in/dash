import subprocess
import os
from datetime import datetime
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run(cmd: str, allow_fail: bool = False):
    print(f"[RUN] {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=BASE_DIR,
        text=True
    )
    if result.returncode != 0 and not allow_fail:
        raise RuntimeError(f"명령 실행 실패: {cmd}")
    return result.returncode

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # 1) 대시보드 데이터 업데이트
        run(f'"{sys.executable}" update_dashboard.py')

        # 2) 변경 파일 추가
        run("git add .")

        # 3) 커밋
        commit_cmd = f'git commit -m "dashboard auto update: {now}"'
        commit_result = run(commit_cmd, allow_fail=True)

        if commit_result != 0:
            print("[INFO] 커밋할 변경사항이 없을 수 있습니다.")

        # 4) GitHub로 푸시
        run("git push origin main")

        print("[DONE] 자동 업데이트 및 GitHub push 완료")

    except Exception as e:
        print(f"[ERROR] {e}")

    input("엔터를 누르면 종료합니다...")

if __name__ == "__main__":
    main()
