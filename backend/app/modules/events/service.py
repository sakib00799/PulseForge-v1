import hashlib


def create_event_fingerprint(service_id: object, event_type: str) -> str:
    normalized_type = event_type.strip().upper()
    value = f"{service_id}:{normalized_type}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
