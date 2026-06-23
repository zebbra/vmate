import logging
from dataclasses import dataclass

from kubernetes import client, config as k8s_config
from kubernetes.client.exceptions import ApiException

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class VmagentPod:
    name: str
    pod_ip: str
    node: str

    @property
    def targets_url(self) -> str:
        return f"http://{self.pod_ip}:{settings.vmagent_port}/api/v1/targets"


def load_k8s_config() -> None:
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()


def discover_pods() -> list[VmagentPod]:
    v1 = client.CoreV1Api()
    try:
        pods = v1.list_namespaced_pod(
            namespace=settings.namespace,
            label_selector=settings.label_selector,
        )
    except ApiException as e:
        logger.error("k8s pod discovery failed: %s", e)
        return []

    result = []
    for pod in pods.items:
        phase = pod.status.phase
        pod_ip = pod.status.pod_ip
        if phase != "Running" or not pod_ip:
            continue
        result.append(
            VmagentPod(
                name=pod.metadata.name,
                pod_ip=pod_ip,
                node=pod.spec.node_name or "",
            )
        )

    logger.debug("discovered %d vmagent pods", len(result))
    return result
