import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.video_production_agent import VideoProductionAgent

agent = VideoProductionAgent()
t0 = time.time()
result = agent.execute(
    title="Creator Growth Systems",
    script=(
        "Most creators do not struggle with ideas. They struggle with the system that keeps them consistent. "
        "Here is a simple framework you can repeat every week. First, pick one clear goal for your content. "
        "Second, produce one useful piece around that goal. Third, review what your audience responds to and "
        "refine your next attempt. Consistency comes from a process you can maintain, not from chasing every trend. "
        "Start with one small action today and document what happens. Over a few weeks you will see which ideas "
        "actually connect with people. Then double down on the ones that do. That is the whole playbook."
    ),
    platform="Instagram",
    captions=["Hook", "Explain", "Framework", "CTA"],
)
for key, value in result.items():
    print(key, "=", value)
print("ELAPSED", round(time.time() - t0, 1))
