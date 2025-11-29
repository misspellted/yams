
from .base import Agent

import subprocess, time, json

class Ipu:
  """
  An instruction processing unit of a system (a 'processor' reported by /proc/cpuinfo on Linux).
  """
  def __init__(self):
    self.index:int = None
    self.physical_id:int = None
    self.vendor_id:str = None
    self.name:str = None
    self.family:int = None
    self.model:int = None
    self.stepping:int = None
    self.microcode:str = None
    self.frequency_khz:float = None

def proc_cpuinfo_ipus() -> list[Ipu]:
  units:list[Ipu] = []

  # Each 'block' of lines reported by /proc/cpuinfo is for one "processor" (logical cores/threads, it appears -- not physical).
  ipu = Ipu()

  for cpu_info_line in subprocess.run(["cat", "/proc/cpuinfo"], stdout=subprocess.PIPE).stdout.decode("utf-8").split("\n"):
    _ = cpu_info_line.strip()

    # Still in the same 'block' of lines for a processor reported from /proc/cpuinfo
    if 0 < len(_):
      # print(_)
      parts = [__.strip() for __ in _.split(":")]
      # print(parts)

      if 1 < len(parts):
        if parts[0] == "processor":
          ipu.index = int(parts[1])
        elif parts[0] == "physical id":
          ipu.physical_id = int(parts[1])
        elif parts[0] == "vendor_id":
          ipu.vendor_id = parts[1]
        elif parts[0] == "model name":
          ipu.name = parts[1]
        elif parts[0] == "cpu family":
          ipu.family = int(parts[1])
        elif parts[0] == "model":
          ipu.model = int(parts[1])
        elif parts[0] == "stepping":
          ipu.stepping = int(parts[1])
        elif parts[0] == "microcode":
          ipu.microcode = parts[1]
        elif parts[0] == "cpu MHz": # Normalize to kHz
          ipu.frequency_khz = float(parts[1]) * 1_000

    # An empty line indicates the end of the 'block' of lines, so save the instance and reset for the next 'block' (if there is more).
    else:
      # print(f"Index: {ipu.index}")
      # print(f"Vendor: {ipu.vendor_id}")
      # print(f"Name: {ipu.name}")
      # print(f"Family: {ipu.family}")
      # print(f"Model: {ipu.model}")
      # print(f"Stepping: {ipu.stepping}")
      # print(f"Microcode: {ipu.microcode}")
      # print(f"Frequency: {ipu.frequency_khz}")

      # But the end of the /proc/cpuinfo output has 2 empty lines, so account for that!
      if ipu.index is not None:
        units.append(ipu)
      
      # Still reset, even on the ending "extra" empty line.
      ipu = Ipu()

  return units

class IpuTimes:
  def __init__(self, index:int, times:list[int]):
    self.index:int = index
    self.user_mode:int = times[0]
    self.user_mode_positive_nice:int = times[1]
    self.kernel_mode:int = times[2]
    self.idle:int = times[3]
    self.io_wait:int = times[4]
    self.hardware_interrupts:int = times[5]
    self.software_interrupts:int = times[6]
    self.guest:int = times[7]
    self.guest_with_nice:int = times[8]
    self.total:int = sum(times)

  def utilization(self) -> float:
    """
    Computes the utilization percentage of the processor: 1 - (total time - idle time) / total time.
    """
    return 1 - (self.total - self.idle) / self.total

def proc_stat_ipu_times() -> list[IpuTimes]:
  unit_times:list[IpuTimes] = []

  for proc_stat_cpu_line in [line.strip() for line in subprocess.run(["cat", "/proc/stat"], stdout=subprocess.PIPE).stdout.decode("utf-8").split("\n") if line.startswith("cpu")]:
    # Utilization is the quantity of total time spent by the cpu minus the time spent idle, divided by the total time spent by the cpu.
    # `cat /proc/stat` output for a CPU contains nine "time" fields after the component identifier (cpu, cpu0, cpu1, ...), of which the fourth (index:3) is idle time.
    # At least, that is the field that is returned on Arch Linux 6+ ^_^.
    # print(f"proc_stat_cpu_utilization({proc_stat_cpu_line})...")
    fields:list[str] = proc_stat_cpu_line.split(" ")
    component = fields[0]
    index = -1 if len(component) == len("cpu") else int(component[len("cpu"):]) # Use a negative value to indicate the 'overall' processor `cpu  ` line.
    unit_times.append(IpuTimes(index, [int(time_field) for time_field in fields[-9:]])) # The `cpu  ` line introduces an emtpy field because of the two spaces utilized.

  return unit_times

class System(Agent):
  """
  An agent monitoring a local system.
  """
  def __init__(self):
    Agent.__init__(self)
    self.collections:list[dict] = []
    self.collecting:dict = None

  def configure(self, agent_configuration:dict) -> bool:
    # For now, there's no additional configuration required. Maybe different platforms may need specific configuration?
    return True

  def on_name_collected(self, hostname:str):
    if self.collecting is not None:
      self.collecting["name"] = hostname

  def collect_name(self):
    raise NotImplementedError("The abstract System agent cannot collect the system name.")

  def on_ipus_collected(self, ipus:list[Ipu]):
    if self.collecting is not None and 0 < len(ipus):
      # Capture the details of the central processing unit(s).
      self.collecting["cpu"] = {}

      # And grab the individual "instruction processing unit(s)" to which utilization can be ascribed individually.
      self.collecting["ipu"] = {}

      # Calculate the average frequency for each processor.
      pid_frequency_khz_sums:dict[int, tuple[int, float]] = {ipu.physical_id: (0, 0.0) for ipu in ipus}

      for ipu in ipus:
        pid = ipu.physical_id

        if pid not in self.collecting["cpu"]:
          self.collecting["cpu"][pid] = {}

        self.collecting["cpu"][pid]["vendor"] = ipu.vendor_id
        self.collecting["cpu"][pid]["family"] = ipu.family
        self.collecting["cpu"][pid]["model"] = ipu.model
        self.collecting["cpu"][pid]["stepping"] = ipu.stepping
        self.collecting["cpu"][pid]["microcode"] = ipu.microcode
        self.collecting["cpu"][pid]["name"] = ipu.name

        idx = ipu.index

        if idx not in self.collecting["ipu"]:
          self.collecting["ipu"][idx] = {}

        self.collecting["ipu"][idx]["cpu"] = pid
        self.collecting["ipu"][idx]["frequency_khz"] = ipu.frequency_khz
        count, sum = pid_frequency_khz_sums[pid]
        sum += ipu.frequency_khz
        pid_frequency_khz_sums[pid] = (count + 1, sum)

      for pid, frequency_khz_sum in pid_frequency_khz_sums.items():
        count, sum = pid_frequency_khz_sums[pid]
        self.collecting["cpu"][pid]["frequency_khz_avg"] = sum/count

  def collect_processor_details(self):
    """
    Collects the specifications of processor(s) in the system.
    """
    raise NotImplementedError("The abstract System agent cannot collect the system processor specifications.")

  def on_ipu_times_collected(self, ipu_times:list[IpuTimes]):
    if self.collecting is not None and 0 < len(ipu_times):
      for ipu_time in ipu_times:
        idx = ipu_time.index
        utl = ipu_time.utilization()

        if idx < 0:
          pid = -idx - 1 # Get back to zero-index for physical processor id.

          if pid not in self.collecting["cpu"]:
            self.collecting["cpu"][pid] = {}

          self.collecting["cpu"][pid]["utilization"] = utl
        
        else:
          if idx not in self.collecting["ipu"]:
            self.collecting["ipu"][idx] = {}

          self.collecting["ipu"][idx]["utilization"] = utl

  def collect_processor_utilization(self):
    """
    Collects the utilization of processor(s) in the system.
    """
    raise NotImplementedError("The abstract System agent cannot collect the system processor utilization.")

  def collect(self) -> bool:
    self.collecting:dict = {}

    successful:bool = True # Assume the colleciton will be successful, but in the collection effort(s), this should be negated accordingly.

    try:
      self.collecting["debut_ns"] = time.time_ns()

      self.collect_name()
      self.collect_processor_details()
      self.collect_processor_utilization()

      self.collecting["arret_ns"] = time.time_ns()
    except Exception as e:
      successful = False
      # print(f"{e}")

    if successful:
      self.collections.append(self.collecting)

    return successful

  def report(self) -> bool:
    successful:bool = True # Assume the reporting will be successful, but again, in the reporting effort(s), negate when needed.

    # For now, there is no receiver for the reports, so only print the last report to the output stream, if there is one.
    if 0 < len(self.collections):
      print(json.dumps(self.collections[-1], indent=2)) # Make it pretty-readable with indentation.

    return successful

class LinuxSystem(System):
  """
  An agent monitoring a Linux-like system, with access to /proc/cpuinfo, /proc/stat, and likely others in the future.
  """
  def __init__(self):
    System.__init__(self)

  def configure(self, agent_configuration:dict) -> bool:
    # No additional configuration at this time.
    return System.configure(self, agent_configuration)

  def collect_name(self):
    self.on_name_collected(subprocess.run(["hostname"], stdout=subprocess.PIPE).stdout.decode("utf-8").split("\n")[0])

  def collect_processor_details(self):
    self.on_ipus_collected(proc_cpuinfo_ipus())

  def collect_processor_utilization(self):
    self.on_ipu_times_collected(proc_stat_ipu_times())
