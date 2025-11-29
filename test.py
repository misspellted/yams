
from yams.agents.system import System, LinuxSystem

agent:System = LinuxSystem()

if agent.configure({}):
  if agent.collect():
    agent.report()
