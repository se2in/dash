import subprocess
import os
from datetime import datetime
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def wait_before_exit():
    if sys.stdin.isatty():
        input("엔터를 누르면 종료합니다...")


def run(cmd: str, allow_fail: bool = False):
    print(f"\n[RUN] {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=BASE_DIR,
        text=True,
        capture_output=True
    )

    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())

    if result.returncode != 0 and not allow_fail:
        raise RuntimeError(f"명령 실행 실패: {cmd}")

    return result


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        print("=" * 60)
        print(f"[INFO] 작업 폴더: {BASE_DIR}")
        print(f"[INFO] 파이썬 실행파일: {sys.executable}")
        print("=" * 60)

        # 0) 현재 git 저장소 위치 확인
        run("git rev-parse --show-toplevel")
        run("git fetch origin", allow_fail=True)

        # 1) 대시보드 데이터 업데이트
        run(f'"{sys.executable}" update_dashboard.py')

        # 2) 어떤 파일이 변경됐는지 먼저 확인
        print("\n[CHECK] update_dashboard.py 실행 후 변경 파일 확인")
        status_before_add = run("git status --short", allow_fail=True)

        if not status_before_add.stdout.strip() and not status_before_add.stderr.strip():
            print("[INFO] 현재 변경된 파일이 없습니다.")
        else:
            print("[INFO] 위 목록이 실제 변경된 파일입니다.")

        # 3) 변경 파일 추가
        run("git add .")

        # 4) add 후 다시 상태 확인
        print("\n[CHECK] git add 후 상태 확인")
        run("git status --short", allow_fail=True)

        # 5) 커밋
        commit_cmd = f'git commit -m "dashboard auto update: {now}"'
        commit_result = run(commit_cmd, allow_fail=True)

        commit_output = (commit_result.stdout or "") + "\n" + (commit_result.stderr or "")
        if commit_result.returncode != 0:
            if "nothing to commit" in commit_output.lower() or "nothing added to commit" in commit_output.lower():
                print("[INFO] 커밋할 변경사항이 없습니다.")
                print("[INFO] 이 경우는 보통 아래 둘 중 하나입니다.")
                print("       1) 실제 파일 저장이 안 됨")
                print("       2) 다른 폴더의 파일을 수정함")
                wait_before_exit()
                return
            else:
                raise RuntimeError("git commit 중 오류가 발생했습니다.")

        # 6) 마지막 커밋 확인
        print("\n[CHECK] 마지막 커밋")
        run("git log -1 --stat")

        # 7) GitHub로 푸시
        push_result = run("git push origin main", allow_fail=True)
        push_output = (push_result.stdout or "") + "\n" + (push_result.stderr or "")
        if push_result.returncode != 0 and (
            "fetch first" in push_output.lower()
            or "non-fast-forward" in push_output.lower()
            or "rejected" in push_output.lower()
        ):
            print("\n[INFO] 원격 main에 새 커밋이 있어 먼저 병합 후 다시 푸시합니다.")
            run("git pull --no-edit origin main")
            run("git push origin main")
        elif push_result.returncode != 0:
            raise RuntimeError("git push 중 오류가 발생했습니다.")

        print("\n[DONE] 자동 업데이트 및 GitHub push 완료")

    except Exception as e:
        print(f"\n[ERROR] {e}")

    wait_before_exit()


if __name__ == "__main__":
    main()
