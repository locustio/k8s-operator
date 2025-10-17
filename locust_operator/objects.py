import shlex
from typing import TypedDict

from kubernetes import client

MASTER_P1_PORT_NAME = "master-p1"
MASTER_P2_PORT_NAME = "master-p2"
MASTER_WEB_PORT_NAME = "master-web"
LOCUST_BASE_PATH = "/home/locust"


class ServicePort(TypedDict):
    name: str
    port: int
    target_port: int | str


def exists(read) -> bool:
    try:
        read()
        return True
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return False
        raise


def ensure(create, read, patch, desired):
    # TODO: validate if the existing resource owned by the CR before patching
    try:
        read()
        return patch(desired)
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return create(desired)
        raise


def build_configmap(
    *, name: str, filename: str, content: str, labels: dict[str, str]
) -> client.V1ConfigMap:
    return client.V1ConfigMap(
        metadata=client.V1ObjectMeta(
            labels=labels,
            name=name,
        ),
        data={filename: content},
    )


def build_service(
    *,
    name: str,
    labels: dict[str, str],
    selector: dict[str, str],
    ports: list[ServicePort],
    type: str = "ClusterIP",
) -> client.V1Service:
    return client.V1Service(
        metadata=client.V1ObjectMeta(
            name=name,
            labels=labels,
        ),
        spec=client.V1ServiceSpec(
            type=type,
            selector=selector,
            ports=[client.V1ServicePort(**port) for port in ports],
        ),
    )


def get_configmap_volume(
    cm_name: str, volume_name: str = "locustfile"
) -> tuple[client.V1Volume, client.V1VolumeMount]:
    volume = client.V1Volume(
        name=volume_name,
        config_map=client.V1ConfigMapVolumeSource(name=cm_name),
    )

    volume_mount = client.V1VolumeMount(
        name=volume_name,
        mount_path=LOCUST_BASE_PATH,
        read_only=True,
    )

    return volume, volume_mount


def build_master_job(
    *,
    name: str,
    image: str,
    args: str,
    env: dict,
    cm_name: str | None,
    labels: dict,
    pod_annotations: dict,
    pod_labels: dict,
    pod_resources: dict,
    image_pull_policy: str | None,
    image_pull_secrets: list[dict[str, str]] | None,
) -> client.V1Job:
    if cm_name is not None:
        volume, volume_mount = get_configmap_volume(cm_name)
    else:
        volume, volume_mount = None, None

    container = client.V1Container(
        name="locust-master",
        image=image,
        image_pull_policy=image_pull_policy,
        args=["--master", *shlex.split(args)],
        ports=[
            client.V1ContainerPort(container_port=5557, name=MASTER_P1_PORT_NAME),
            client.V1ContainerPort(container_port=5558, name=MASTER_P2_PORT_NAME),
            client.V1ContainerPort(container_port=8089, name=MASTER_WEB_PORT_NAME),
        ],
        env=[client.V1EnvVar(**env_var) for env_var in env],
        volume_mounts=[volume_mount],
        resources=client.V1ResourceRequirements(**pod_resources),
    )

    pod_meta = client.V1ObjectMeta(labels=pod_labels, annotations=pod_annotations)
    pod_spec = client.V1PodSpec(
        restart_policy="Never",
        containers=[container],
        volumes=[volume],
        image_pull_secrets=image_pull_secrets,
    )

    job = client.V1Job(
        metadata=client.V1ObjectMeta(
            name=name,
            labels=labels,
        ),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(metadata=pod_meta, spec=pod_spec),
            ttl_seconds_after_finished=0,
            parallelism=1,
        ),
    )
    return job


def build_worker_job(
    *,
    name: str,
    image: str,
    args: str,
    env: dict,
    master_svc: str,
    worker_count: int,
    cm_name: str | None,
    labels: dict,
    pod_annotations: dict,
    pod_labels: dict,
    pod_resources: dict,
    image_pull_policy: str | None,
    image_pull_secrets: list[dict[str, str]] | None,
) -> client.V1Job:
    if cm_name is not None:
        volume, volume_mount = get_configmap_volume(cm_name)
    else:
        volume, volume_mount = None, None

    container = client.V1Container(
        name="locust-worker",
        image=image,
        image_pull_policy=image_pull_policy,
        args=["--worker", "--master-host", master_svc, *shlex.split(args)],
        env=[client.V1EnvVar(**env_var) for env_var in env],
        volume_mounts=[volume_mount],
        resources=client.V1ResourceRequirements(**pod_resources),
    )

    pod_meta = client.V1ObjectMeta(labels=pod_labels, annotations=pod_annotations)
    pod_spec = client.V1PodSpec(
        restart_policy="OnFailure",
        containers=[container],
        volumes=[volume],
        image_pull_secrets=image_pull_secrets,
    )

    job = client.V1Job(
        metadata=client.V1ObjectMeta(
            name=name,
            labels=labels,
        ),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(metadata=pod_meta, spec=pod_spec),
            ttl_seconds_after_finished=0,
            parallelism=worker_count,
        ),
    )
    return job
