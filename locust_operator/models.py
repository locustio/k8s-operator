from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class EnvVar(BaseModel):
    name: str
    value: str = ""

class Resources(BaseModel):
    master: Optional[Dict] = None
    worker: Optional[Dict] = None

class ServiceCfg(BaseModel):
    type: str = Field(default="ClusterIP", pattern="^(ClusterIP|NodePort|LoadBalancer)$")

class MasterPorts(BaseModel):
    p1: int = 5557
    p2: int = 5558

class LocustfileSpec(BaseModel):
    filename: str = "locustfile.py"
    content: str

class LocustTestSpec(BaseModel):
    image: str = "locustio/locust:2.31.5"
    workerImage: Optional[str] = None
    workers: int = Field(ge=1)
    host: Optional[str] = None
    extraArgs: List[str] = []
    env: List[EnvVar] = []
    resources: Optional[Resources] = None
    service: ServiceCfg = ServiceCfg()
    locustfile: Optional[LocustfileSpec] = None
    webPort: int = 8089
    masterPorts: MasterPorts = MasterPorts()

class LocustTestStatus(BaseModel):
    phase: Optional[str] = None
    masterService: Optional[str] = None
    message: Optional[str] = None