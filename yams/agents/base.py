
class Agent:
  """
  Collects and reports information on that which is monitored.

  This could be a system agent to monitor processor and memory utilization or it could be a service agent to monitor external service availability.
  """

  def configure(self, agent_configuration:dict) -> bool:
    """
    Configures the agent using the provided details.

    Indicates whether the agent was configured successfully, also indicating monitoring readiness.
    """
    raise NotImplementedError("The abstract Agent cannot be configured.")

  def collect(self) -> bool:
    """
    Collects the monitored information to be reported.

    Indicates whether the monitoried information was collected successfully.
    """
    raise NotImplementedError("The abstract Agent cannot collect data.")

  def report(self) -> bool:
    """
    Reports the collected information.
    
    Indicates whether the reporting was completed successfully.
    """
    raise NotImplementedError("The abstract Agent cannot report collected data.")
