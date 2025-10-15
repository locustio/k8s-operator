from typing import Annotated, Literal, Optional
from pydantic import BaseModel, BeforeValidator, Field, model_validator


class AnnotationsMixin:
    annotations: Optional[dict[str, str]] = None


class LabelsMixin:
    labels: Optional[dict[str, str]] = None


class EnvVar(BaseModel):
    name: str
    value: str = ""


class LocalObjectReference(BaseModel):
    name: str


class Resources(BaseModel):
    requests: Optional[dict[str, str]] = None
    limits: Optional[dict[str, str]] = None


class PodSpec(BaseModel, AnnotationsMixin, LabelsMixin):
    resources: Optional[Resources] = None


class LocustfileInline(BaseModel):
    filename: str = "locustfile.py"
    content: str


class LocustfileSpec(BaseModel):
    inline: Optional[LocustfileInline] = None
    configMap: Optional[LocalObjectReference] = None

    @model_validator(mode="after")
    def _only_one(self):
        if self.inline is not None and self.configMap is not None:
            raise ValueError("Provide exactly one of `locustfile.inline` or `locustfile.configMap`")
        return self


def _parse_args(args):
    import shlex
    if args is None:
        return None
    if isinstance(args, str):
        return shlex.split(args)
    
    raise TypeError("`args` must be a string")

class LocustTestSpec(BaseModel, AnnotationsMixin, LabelsMixin):
    image: str = "locustio/locust:latest"
    workers: int = Field(ge=1, default=1)
    args: Annotated[list[str], BeforeValidator(_parse_args)] = []
    env: list[EnvVar] = []

    imagePullPolicy: Optional[Literal["Always", "IfNotPresent", "Never"]] = None
    imagePullSecrets: Optional[list[LocalObjectReference]] = None

    master: Optional[PodSpec] = None
    worker: Optional[PodSpec] = None

    locustfile: Optional[LocustfileSpec] = None


class LocustTestStatus(BaseModel):
    state: Optional[str] = None
    fail_ratio: Optional[str] = None
    total_rps: Optional[str] = None
    user_count: Optional[str] = None
    worker_count: Optional[str] = None
