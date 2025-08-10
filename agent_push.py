# launcher that runs the new v7 agent without changing Procfile or Railway settings
import agent

if __name__ == "__main__":
    agent.main_loop()