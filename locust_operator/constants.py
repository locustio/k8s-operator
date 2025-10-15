GROUP = "locust.cloud"
VERSION = "v1"
API_VERSION = GROUP + "/" + VERSION

KIND = "LocustTest"
PLURAL = "locusttests"
LOCUST_TEST_RESOURCE = f"{PLURAL}.{VERSION}.{GROUP}"

ANNOTATION_PREFIX = f"operator.{GROUP}"
