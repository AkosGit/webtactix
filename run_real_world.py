import asyncio
from pathlib import Path
from webtactix.core.schemas import TaskSpec
from webtactix.browser.playwright_session import PlaywrightConfig, PlaywrightSession
from webtactix.core.semantic_tree import SemanticTree
from webtactix.llm.presets import preset_mistral
from webtactix.llm.openai_compat import OpenAICompatClient
from webtactix.agents.constraint_agent import ConstraintAgent
from webtactix.agents.data_agent import DataExtractionAgent
from webtactix.workflows.execute import Executor
from webtactix.agents.planner_agent import PlannerAgent
from webtactix.agents.decision_agent import DecisionAgent
from webtactix.runner.experiment_runner import ExperimentRunner, RunnerConfig
from webtactix.runner.recorder import Recorder

REAL_WORLD_TASKS = [
    TaskSpec(
        dataset="real_world",
        task_id=1,
        intent="Find me the cheapest men sport shoes for size 38 with reviews of at least 4.1",
        start_url="https://www.temu.com"
    ),
    TaskSpec(
        dataset="real_world",
        task_id=2,
        intent="Find the birth date of Albert Einstein",
        start_url="https://en.wikipedia.org"
    ),
    TaskSpec(
        dataset="real_world",
        task_id=3,
        intent="Search for the most starred repository for 'browser automation' in python",
        start_url="https://github.com"
    ),
    TaskSpec(
        dataset="real_world",
        task_id=4,
        intent="Find the top story and get its title",
        start_url="https://news.ycombinator.com"
    ),
    TaskSpec(
        dataset="real_world",
        task_id=5,
        intent="Search for a wireless mouse under $20",
        start_url="https://www.amazon.com"
    ),
    TaskSpec(
        dataset="real_world",
        task_id=6,
        intent="Find a stay in Paris for next weekend for 2 guests",
        start_url="https://www.airbnb.com"
    ),
    TaskSpec(
        dataset="real_world",
        task_id=7,
        intent="Find the top voted answer for 'how to reverse a string in python'",
        start_url="https://stackoverflow.com"
    ),
    TaskSpec(
        dataset="real_world",
        task_id=8,
        intent="Get the headline of the main front-page news article",
        start_url="https://www.nytimes.com"
    ),
    TaskSpec(
        dataset="real_world",
        task_id=9,
        intent="Find the director of 'The Matrix' (1999)",
        start_url="https://www.imdb.com"
    ),
    TaskSpec(
        dataset="real_world",
        task_id=10,
        intent="Find the highest rated pizza place in San Francisco",
        start_url="https://www.yelp.com"
    ),
]

import os
import glob
import subprocess

async def run_task(task: TaskSpec, cdp_url: str):
    print(f"\n================= [STARTING TASK {task.task_id}] =================")
    print("Cleaning up Chrome processes and lock files...")
    subprocess.run(["pkill", "-9", "-f", "Google Chrome"], capture_output=True)
    
    lock_pattern = "/Users/akos/Library/Application Support/Google/Chrome/Singleton*"
    for f in glob.glob(lock_pattern):
        try:
            os.remove(f)
        except Exception:
            pass

    sess = PlaywrightSession(PlaywrightConfig(cdp_url=cdp_url, headless=False))
    tree = SemanticTree()
    
    runner_cfg = RunnerConfig(llm_type="mistral")
    llm = OpenAICompatClient(preset_mistral(key_num=0))
    
    rec = Recorder(
        base_dir=Path("record"),
        task=task,
        model_name="magistral-medium-2509",
    )
    
    meta = {
        "max_rounds": 40,
        "max_parallel": 1,
        "table_max_rows": 10,
        "llm_type": "magistral-medium-2509",
        "key_num": 0,
        "dataset": "real_world"
    }
    rec.write_meta(meta=meta)
    
    print(f"\n================= [STARTING TASK {task.task_id}] =================")
    print(f"intent: {task.intent}")
    print(f"url:    {task.start_url}")
    
    cons_agent = ConstraintAgent(llm=llm, task=task)
    constraints = await cons_agent.run()
    rec.write_task_info(task, constraints=constraints)
    
    extractor = DataExtractionAgent(task=task, llm=llm, tree=tree, sess=sess, rec=rec)
    executor = Executor(sess=sess, tree=tree, rec=rec, data_agent=extractor, evaluator=None)
    
    planner = PlannerAgent(llm=llm, q=task.intent, constraints=constraints, tree=tree, rec=rec)
    decision = DecisionAgent(
        llm=llm,
        q=task.intent,
        constraints=constraints,
        executor=executor,
        tree=tree,
        sess=sess,
        rec=rec,
    )
    
    runner = ExperimentRunner(sess=sess, tree=tree, planner=planner, decision=decision, task=task, rec=rec)
    
    import time
    start_time = time.time()
    res = await runner.run(
        start_url=task.start_url,
        storage_state=None,
        geolocation=None,
    )
    elapsed_time = time.time() - start_time
    
    print("\n================= [TASK RESULT] =================")
    print(f"task_id: {task.task_id}")
    print(f"status:  {res.status}")
    print(f"answer:  {res.answer}")
    print(f"time:    {elapsed_time:.2f} seconds")
    print("=================================================\n")
    return res

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run WebTactix real-world tasks.")
    parser.add_argument("--url", type=str, help="The starting URL for the custom task.")
    parser.add_argument("--intent", type=str, help="The task description/intent.")
    parser.add_argument("--network-idle-timeout", type=int, default=10000, help="Timeout in ms for network idle (default: 10000)")
    parser.add_argument("--layout-stable-timeout", type=int, default=6000, help="Timeout in ms for layout stability (default: 6000)")
    args = parser.parse_args()

    import subprocess
    import os
    
    os.environ["NETWORK_IDLE_TIMEOUT"] = str(args.network_idle_timeout)
    os.environ["LAYOUT_STABLE_TIMEOUT"] = str(args.layout_stable_timeout)
    
    # Run the setup script to clone the profile
    script_path = os.path.join(os.path.dirname(__file__), "setup_profile.sh")
    subprocess.run(["bash", script_path], check=True)
    
    cdp_url = None
    if args.url and args.intent:
        custom_task = TaskSpec(
            dataset="custom",
            task_id=999,
            intent=args.intent,
            start_url=args.url
        )
        try:
            await run_task(custom_task, cdp_url)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Custom task failed with error: {e}")
    else:
        for task in REAL_WORLD_TASKS:
            try:
                await run_task(task, cdp_url)
            except Exception as e:
                print(f"Task {task.task_id} failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
