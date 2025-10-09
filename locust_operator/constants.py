GROUP = "locust.cloud"
VERSION = "v1"
API_VERSION = GROUP + "/" + VERSION

KIND = "LocustTest"
PLURAL = "locusttests"

FINALIZER = f"{PLURAL}.finalizers.{GROUP}"