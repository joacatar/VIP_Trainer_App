import base64

from ct_training_tracker.components.paste_image import decode_pasted_payload


def test_decode_pasted_payload_from_dict() -> None:
    raw = b"fake-png-bytes"
    payload = {
        "mime_type": "image/png",
        "filename": "shot.png",
        "data_base64": base64.b64encode(raw).decode("ascii"),
    }
    image = decode_pasted_payload(payload)
    assert image is not None
    assert image.filename == "shot.png"
    assert image.mime_type == "image/png"
    assert image.content == raw


def test_decode_pasted_payload_rejects_empty() -> None:
    assert decode_pasted_payload(None) is None
    assert decode_pasted_payload({}) is None
    assert decode_pasted_payload("not-a-data-url") is None
