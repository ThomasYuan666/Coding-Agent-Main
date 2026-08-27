from agent.loop import run_session


if __name__ == "__main__":
    try:
        run_session()
    except KeyboardInterrupt:
        print("\n已退出。")
