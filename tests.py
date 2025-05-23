import pytest
from bson import ObjectId
from fastapi import HTTPException

from main import validate_object_id, serialize_doc, Product


def test_validate_valid_object_id():
    oid = "5f9d1b3b9c9d6e1d9c9d6e1d"
    assert isinstance(validate_object_id(oid), ObjectId)


def test_validate_invalid_object_id():
    with pytest.raises(HTTPException) as exc_info:
        validate_object_id("invalid")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid ObjectId"


def test_serialize_doc():
    doc = {"_id": ObjectId(), "name": "Milk"}
    serialized = serialize_doc(doc)
    assert isinstance(serialized["_id"], str)


def test_product_validation_success():
    product = Product(name="Milk", price=99.99)
    assert product.name == "Milk"
    assert product.price == 99.99


def test_product_empty_name_raises_error():
    with pytest.raises(ValueError):
        Product(name="   ", price=99.99)


def test_product_pattern_rejects_non_alpha():
    with pytest.raises(ValueError):
        Product(name="Milk123", price=99.99)